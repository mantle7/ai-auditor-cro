import json

from ai import call_groq
from customer_simulation import simulate_customer
from scoring import build_scorecard

MAX_AGGREGATION_OUTPUT_TOKENS = 1100


# MVP: exactly ONE persona and ONE run.
DEFAULT_RUNS = 1


def _limit_text(value, limit):
    return str(value or "")[:limit]


def _normalize_aggregation(aggregated, total_runs, decision_summary):
    """Enforce facts that are known locally rather than trusting model output."""

    aggregated["total_runs"] = total_runs
    aggregated["decision_summary"] = decision_summary

    if aggregated.get("overall_decision") not in {
        "continue", "hesitate", "abandon", "mixed"
    }:
        aggregated["overall_decision"] = "unknown"

    # A single synthetic journey is never high-confidence evidence.
    if total_runs <= 1:
        aggregated["confidence"] = "low"
    elif aggregated.get("confidence") not in {"low", "medium", "high"}:
        aggregated["confidence"] = "low"

    for pattern in aggregated.get("key_patterns", []):
        if not isinstance(pattern, dict):
            continue

        try:
            frequency = int(pattern.get("frequency", 1))
        except (TypeError, ValueError):
            frequency = 1

        pattern["frequency"] = min(total_runs, max(1, frequency))

        if pattern.get("severity") not in {"high", "medium", "low"}:
            pattern["severity"] = "low"

    return aggregated


def run_simulations(page_data, personas, runs_per_persona=DEFAULT_RUNS):
    """
    MVP simulation engine:
    - Uses only the first persona.
    - Runs that persona exactly ONE time.
    - Each run sends the complete customer journey to Groq once.
    """

    if not personas:
        raise ValueError("No customer persona was supplied.")

    persona = personas[0]

    # Keep the MVP fixed to one persona and one run.
    runs_per_persona = DEFAULT_RUNS

    print("\n============================================================")
    print(f"Simulating: {persona['name']}")
    print("============================================================")

    result = simulate_customer(
        page_data,
        persona,
        runs=runs_per_persona,
    )

    return [result]


def _compact_simulation_results(simulation_results):
    """
    Extract only the information needed for cross-run aggregation.

    The full journeys are intentionally NOT sent to Groq here because they
    make the aggregation request unnecessarily large and can exceed the
    account's token limits.
    """

    compact = []

    for simulation in simulation_results:
        persona = simulation.get("persona", {})
        runs = simulation.get("runs", [])

        compact_runs = []

        for run in runs:
            if not isinstance(run, dict):
                continue

            section_patterns = []

            for section in run.get("journey", []):
                if not isinstance(section, dict):
                    continue

                section_patterns.append({
                    "section_index": section.get("section_index"),
                    "section_type": section.get("section_type"),
                    "decision": section.get("decision"),
                    "information_gap": _limit_text(
                        section.get("information_gap"), 240
                    ),
                    "reason": _limit_text(section.get("reason"), 280),
                })

            compact_runs.append({
                "run": run.get("run"),
                "overall_outcome": run.get("overall_outcome"),
                "overall_reason": _limit_text(run.get("overall_reason"), 350),
                "key_objections": [
                    _limit_text(item, 220)
                    for item in run.get("key_objections", [])[:5]
                ],
                "strongest_conversion_signal": _limit_text(
                    run.get("strongest_conversion_signal"), 240
                ),
                "confidence": run.get("confidence"),
                "section_patterns": section_patterns[:12],
            })

        compact.append({
            "persona": {
                "name": persona.get("name"),
                "role": persona.get("role"),
                "company": persona.get("company"),
                "goal": persona.get("goal"),
                "pain_points": persona.get("pain_points", []),
                "buying_concerns": persona.get("buying_concerns", []),
            },
            "runs": compact_runs,
        })

    return compact


def aggregate_simulations(
    simulation_results,
    page_data=None,
    cro_analysis=None,
    revenue_inputs=None,
):
    """
    Aggregate the single simulation run.

    Only compact simulation conclusions are sent to Groq.

    The complete customer journey is retained in
    simulation_results.json but is not included in the aggregation request.
    """

    compact_results = _compact_simulation_results(simulation_results)

    # Calculate run counts locally so the summary cannot accidentally
    # return total_runs=0 or an inconsistent count.
    total_runs = 0

    decision_summary = {
        "continue": 0,
        "hesitate": 0,
        "abandon": 0,
    }

    for simulation in compact_results:
        for run in simulation.get("runs", []):
            total_runs += 1

            outcome = run.get("overall_outcome")

            if outcome in decision_summary:
                decision_summary[outcome] += 1

    compact_json = json.dumps(
        compact_results,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    prompt = f"""
You are analyzing customer simulation results for a CRO audit.

IMPORTANT RULES:

1. The simulation represents hypothetical customer behavior.
   It is NOT real visitor/user data.

2. Do not claim that a CRO change will definitely increase conversions,
   revenue, or engagement.

3. You may say that a change "may reduce friction", "addresses a recurring
   concern", or "could improve clarity", but do not present this as proven
   conversion uplift.

4. Do not introduce companies, statistics, claims, metrics, or other facts
   that are not present in the supplied simulation data or audited website
   data.

5. Distinguish between:
   - website evidence
   - simulated customer observations
   - CRO recommendations

6. Recommendations must be based on patterns found in the simulation.

7. Because there is only ONE simulation run, do NOT describe an issue as
   "recurring", "repeated", or "appearing across multiple runs".

8. Do not invent evidence to make a recommendation sound stronger.

9. Do not treat the simulation as statistically significant.

10. Do not claim that a single simulation proves that a website problem
    exists among real users.

There is exactly ONE customer persona and ONE simulation run.

IMPORTANT CONFIDENCE RULE:

Because this MVP currently uses only ONE simulation run:

- Never return "high" confidence.
- Use "low" confidence when conclusions are based primarily on a single
  simulated journey.
- Use "medium" only when multiple independent pieces of evidence within
  that single journey strongly support the same observation.
  
Analyze the available simulation and identify the most important observations.

Do NOT invent additional personas, customer data, analytics,
conversion rates, revenue, or statistical evidence.

IMPORTANT:

- This is a hypothesis about a customer journey, not real user data.
- Treat observations as simulation evidence, not confirmed real-world behavior.
- Do not give generic CRO advice.
- Keep recommendations specific to the supplied evidence.
- Do not repeat the complete journey in the output.
- Because there is only one run, use cautious language.
- "frequency" represents the number of simulation runs containing the issue.
- Do not imply that frequency represents real-world prevalence.

LOCAL RUN COUNT:
{total_runs}

LOCAL DECISION COUNTS:
{json.dumps(decision_summary, ensure_ascii=False)}

COMPACT SIMULATION DATA:
{compact_json}

Return ONLY valid JSON using exactly this structure:

{{
  "total_runs": {total_runs},

  "decision_summary": {json.dumps(
      decision_summary,
      ensure_ascii=False
  )},

  "overall_decision": "continue | hesitate | abandon | mixed",

  "confidence": "high | medium | low",

  "key_patterns": [
    {{
      "issue": "short description of an important issue",
      "frequency": 1,
      "severity": "high | medium | low",
      "evidence": "what the simulation showed"
    }}
  ],

  "key_objections": [
    "important objection from the simulation"
  ],

  "strongest_conversion_signals": [
    "positive conversion signal observed in the simulation"
  ],

  "recommended_actions": [
    {{
      "priority": 1,
      "action": "specific CRO action",
      "reason": "specific simulation evidence supporting this action"
    }}
  ]
}}
"""

    print("Aggregating compact simulations with Groq...")
    text = call_groq(prompt, max_tokens=MAX_AGGREGATION_OUTPUT_TOKENS)

    try:
        aggregated = json.loads(text)
    except json.JSONDecodeError:
        print("Warning: Groq aggregation returned invalid JSON.")
        aggregated = {
            "overall_decision": "unknown",
            "confidence": "low",
            "key_patterns": [],
            "key_objections": [],
            "strongest_conversion_signals": [],
            "recommended_actions": [],
            "raw_response": text,
            "parse_error": True,
        }

    aggregated = _normalize_aggregation(
        aggregated,
        total_runs,
        decision_summary,
    )
    aggregated["scorecard"] = build_scorecard(
        page_data or {},
        aggregated,
        cro_analysis=cro_analysis,
        revenue_inputs=revenue_inputs,
    )

    return aggregated
