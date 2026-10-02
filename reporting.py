import json


def _as_dict(value):
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}

    return {}


def _top_actions(simulation_analysis, cro_analysis):
    actions = []

    for action in simulation_analysis.get("recommended_actions", []):
        if not isinstance(action, dict) or not action.get("action"):
            continue

        actions.append({
            "priority": action.get("priority", len(actions) + 1),
            "action": action["action"],
            "evidence": action.get("reason", "Simulation-backed hypothesis."),
            "source": "simulated_customer_journey",
        })

    for finding in cro_analysis.get("findings", []):
        if len(actions) >= 2:
            break
        if not isinstance(finding, dict) or not finding.get("recommendation"):
            continue

        recommendation = finding["recommendation"]
        if any(item["action"] == recommendation for item in actions):
            continue

        actions.append({
            "priority": len(actions) + 1,
            "action": recommendation,
            "evidence": finding.get("interpretation") or "Website audit finding.",
            "source": "website_audit",
        })

    if len(actions) == 1:
        patterns = simulation_analysis.get("key_patterns", [])
        issue = patterns[0].get("issue") if patterns else "the highest-priority conversion hypothesis"
        actions.append({
            "priority": 2,
            "action": f"Run a focused A/B test for {issue.lower()}.",
            "evidence": (
                "This is a validation hypothesis based on the simulated journey; "
                "measure the primary conversion event before drawing conclusions."
            ),
            "source": "validation_recommendation",
        })

    if not actions:
        actions = [
            {
                "priority": 1,
                "action": "Confirm the primary conversion event and establish its current baseline.",
                "evidence": "The audit has no reliable conversion baseline, so impact cannot be validated yet.",
                "source": "measurement_recommendation",
            },
            {
                "priority": 2,
                "action": "Run a focused A/B test on the first high-impact customer friction identified by the audit.",
                "evidence": "Use the audit hypothesis to define the first experiment and measure the primary conversion event.",
                "source": "validation_recommendation",
            },
        ]

    return sorted(actions, key=lambda action: action["priority"])[:2]


def build_client_report(url, persona, simulation_analysis, cro_analysis=None):
    """Create a short client-facing report from existing audit outputs."""

    analysis = _as_dict(cro_analysis)
    scorecard = simulation_analysis.get("scorecard", {})
    actions = _top_actions(simulation_analysis, analysis)

    return {
        "report_type": "CRO opportunity snapshot",
        "url": url,
        "persona": {
            "id": persona.get("id"),
            "name": persona.get("name"),
            "segment": persona.get("segment"),
            "role": persona.get("role"),
        },
        "scores": {
            "conversion_readiness": scorecard.get("conversion_readiness_score"),
            "cro_opportunity": scorecard.get("cro_opportunity_score"),
        },
        "score_breakdown": scorecard.get("dimensions", []),
        "score_definitions": {
            "Value clarity": "Can visitors quickly understand what is being offered and why it matters?",
            "Conversion path": "Can visitors find and complete the main action without confusion?",
            "Trust and risk reduction": "Does the page provide enough proof and reassurance to move forward?",
            "Journey friction": "How much unnecessary effort, confusion, or distraction appears in the journey?",
            "Evaluation clarity": "Can visitors judge price, fit, process, and next steps confidently?",
        },
        "summary": analysis.get("overall_summary") or simulation_analysis.get(
            "overall_decision", "unknown"
        ),
        "actionable_insights": actions,
        "recommended_next_step": scorecard.get("recommended_next_step", {}),
        "disclaimer": scorecard.get(
            "disclaimer",
            "This report is based on website evidence and simulated behavior.",
        ),
    }
