import json

from ai import call_groq, clean_json, compact_page_data


MAX_SIMULATION_INPUT_CHARS = 8000
MAX_SIMULATION_SECTIONS = 12
MAX_SIMULATION_OUTPUT_TOKENS = 1800


def _compact_journey_data(page_data):
    """Keep the highest-value page evidence within a fixed simulation budget."""

    compact_page = json.loads(
        compact_page_data(
            page_data,
            max_input_chars=MAX_SIMULATION_INPUT_CHARS,
        )
    )
    sections = compact_page.get("sections", [])

    priority_types = {
        "hero": 0,
        "pricing": 1,
        "cta": 2,
        "form": 3,
        "social_proof": 4,
        "faq": 5,
    }
    selected = sorted(
        enumerate(sections),
        key=lambda item: (
            priority_types.get(item[1].get("type"), 6),
            item[0],
        ),
    )[:MAX_SIMULATION_SECTIONS]
    selected.sort(key=lambda item: item[0])

    journey = []

    for _, section in selected:
        journey.append({
            "index": section.get("index"),
            "type": section.get("type"),
            "heading": str(
                section.get("heading") or section.get("title") or ""
            )[:240],
            "text": str(
                section.get("text")
                or section.get("description")
                or section.get("content")
                or ""
            )[:500],
            "ctas": section.get("ctas", [])[:3],
        })

    journey_data = {
        "url": compact_page.get("url"),
        "title": compact_page.get("title"),
        "description": compact_page.get("description"),
        "sections": journey,
    }

    serialized = json.dumps(
        journey_data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    while len(serialized) > MAX_SIMULATION_INPUT_CHARS and journey:
        journey.pop()
        serialized = json.dumps(
            journey_data,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return journey_data


def simulate_customer(page_data, persona, runs=3):

    journey_data = _compact_journey_data(page_data)
    sections = journey_data["sections"]

    results = []

    print(
        f"\nStarting simulation for: "
        f"{persona['name']}"
    )

    for run_number in range(1, runs + 1):

        print(
            f"\nRun {run_number}/{runs}"
        )

        print(
            "Sending compact customer journey "
            f"({len(sections)} sections) to Groq..."
        )

        prompt = f"""
You are simulating ONE realistic potential customer
visiting a website.

You are NOT a CRO consultant.

You are the customer.

PERSONA:

{json.dumps(persona, indent=2, ensure_ascii=False)}


WEBSITE JOURNEY:

{json.dumps(sections, indent=2, ensure_ascii=False)}


The sections are presented in the order the customer
encounters them.

Evaluate the entire journey from the customer's perspective.

Do not use information from a later section to justify
a decision that would not have been available earlier
in the journey.

For EACH section determine:

1. What the customer notices.
2. What the customer thinks.
3. What uncertainty or information gap exists.
4. Whether the customer continues, hesitates, or abandons.
5. What information they want next if they continue.

Then provide an overall journey outcome.

IMPORTANT:

- Do not invent information.
- Do not assume claims are true or false without evidence.
- Distinguish facts from assumptions.
- Do not give generic CRO advice.
- Behave like a realistic potential buyer.
- If something is unclear, say so.
- Do not call a CTA misleading or deceptive without direct evidence.
- Do not invent statistics or customer results.
- Keep decisions grounded in the supplied website content and persona.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "persona": {json.dumps(persona.get("name", "unknown"))},

    "run": {run_number},

    "journey": [
        {{
            "section_index": 0,

            "section_type":
                "navigation | hero | features | pricing | faq | cta | other",

            "what_i_notice": "...",

            "customer_thought": "...",

            "information_gap": "...",

            "decision":
                "continue | hesitate | abandon",

            "next_information_needed": "...",

            "reason": "...",

            "confidence":
                "high | medium | low"
        }}
    ],

    "overall_outcome":
        "continue | hesitate | abandon",

    "overall_reason": "...",

    "key_objections": [
        "..."
    ],

    "strongest_conversion_signal": "...",

    "confidence":
        "high | medium | low"
}}
"""

        response_text = call_groq(
            prompt,
            max_tokens=MAX_SIMULATION_OUTPUT_TOKENS
        )

        cleaned = clean_json(response_text)

        try:

            result = json.loads(cleaned)

        except json.JSONDecodeError:

            print(
                "Warning: Groq returned invalid JSON. "
                "Attempting to preserve raw response..."
            )

            result = {
                "persona": persona,
                "run": run_number,
                "raw_response": cleaned,
                "parse_error": True
            }

        results.append(result)

        if isinstance(result, dict):

            print(
                f"Simulation outcome: "
                f"{result.get('overall_outcome', 'unknown')}"
            )

    return {
        "persona": persona,
        "runs": results
    }
