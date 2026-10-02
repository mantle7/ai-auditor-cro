import json
import time
import re
import hashlib
from pathlib import Path

from groq import Groq
from constants import API_KEY


client = Groq(api_key=API_KEY)

MODEL = "openai/gpt-oss-120b"

# Fallback models, used only if the previous model fails.
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

MAX_RETRIES = 2

MAX_INPUT_CHARS = 12000
# Anchor the cache to the repository so CLI and Streamlit share one cache.
# This matches the existing output/cache directory used by the project.
CACHE_DIR = Path(__file__).resolve().parent / "output" / "cache"


def clean_json(text):
    """
    Remove markdown code fences if the model returns JSON
    wrapped inside ```json ... ```.
    """

    if not text:
        return text

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def _is_daily_token_limit(error_text):
    error_text = error_text.lower()

    return "tokens per day" in error_text or "tpd" in error_text


def _cache_path(prompt, max_tokens):
    cache_key = json.dumps(
        {
            "model": MODEL,
            "fallback_models": FALLBACK_MODELS,
            "max_tokens": max_tokens,
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def call_groq(prompt, max_tokens=1800, use_cache=True):
    """
    Generic Groq request.

    Tries the primary model first.
    If it fails after MAX_RETRIES, moves to the next fallback model.

    Used by:
    - CRO analysis
    - Customer simulation
    - Simulation aggregation
    """

    cache_path = _cache_path(prompt, max_tokens)

    if use_cache and cache_path.exists():
        print(
            "Using cached Groq response for unchanged audit input: "
            f"{cache_path.name}"
        )
        return cache_path.read_text(encoding="utf-8")

    models = [MODEL] + FALLBACK_MODELS
    last_error = None

    for model in models:

        for attempt in range(MAX_RETRIES):

            try:

                print(
                    f"Groq: {model} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )

                response = client.chat.completions.create(

                    model=model,

                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert conversion "
                                "rate optimization AI. "
                                "Follow the user's instructions "
                                "exactly. "
                                "Return only valid JSON when "
                                "JSON is requested."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],

                    temperature=0.2,

                    max_tokens=max_tokens,

                    response_format={
                        "type": "json_object"
                    }
                )

                print(
                    f"Groq response received using {model}."
                )

                response_text = clean_json(
                    response.choices[0].message.content
                )

                if use_cache:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(response_text, encoding="utf-8")

                return response_text

            except Exception as e:

                last_error = e

                error_text = str(e)

                print(
                    f"Groq request failed "
                    f"({model}, attempt "
                    f"{attempt + 1}/{MAX_RETRIES}): "
                    f"{error_text}"
                )

                if _is_daily_token_limit(error_text):
                    print(
                        "Groq daily token limit reached. "
                        "Stopping retries and model fallbacks."
                    )
                    raise

                if attempt < MAX_RETRIES - 1:

                    wait_time = 6 * (attempt + 1)

                    match = re.search(
                        r"try again in ([0-9.]+)s",
                        error_text
                    )

                    if match:

                        try:
                            wait_time = (
                                float(match.group(1)) + 1
                            )

                        except ValueError:
                            pass

                    print(
                        f"Retrying in "
                        f"{round(wait_time, 1)} seconds..."
                    )

                    time.sleep(wait_time)

        print(
            f"Model {model} exhausted its retries."
        )

        if model != models[-1]:

            print(
                "Switching to fallback model..."
            )

    raise last_error

def compact_page_data(page_data, max_input_chars=MAX_INPUT_CHARS):
    """
    Reduce website audit data before sending it to Groq.

    The crawler can produce a very large JSON object.
    We retain the information most useful for CRO analysis.
    """

    compact = {
        "url": str(page_data.get("url", ""))[:500],
        "title": str(page_data.get("title", ""))[:600],
        "description": str(page_data.get("description", ""))[:1000],
        "headings": [],
        "navigation": [],
        "sections": [],
        "ctas": [],
        "forms": [],
        "links": [],
    }

    headings = page_data.get("headings", [])

    if isinstance(headings, list):

        for heading in headings[:40]:

            if isinstance(heading, dict):

                compact["headings"].append({
                    "level": heading.get("level"),
                    "text": str(
                        heading.get("text", "")
                    )[:300]
                })

            else:

                compact["headings"].append(
                    str(heading)[:300]
                )

    navigation = page_data.get("navigation", [])

    if isinstance(navigation, list):

        for item in navigation[:30]:

            if isinstance(item, dict):

                compact["navigation"].append({
                    "text": str(
                        item.get("text", "")
                    )[:200],
                    "href": str(
                        item.get("href", "")
                    )[:300]
                })

            else:

                compact["navigation"].append(
                    str(item)[:300]
                )

    ctas = page_data.get("ctas", [])

    if isinstance(ctas, list):

        for cta in ctas[:40]:

            if isinstance(cta, dict):

                compact["ctas"].append({
                    "text": str(
                        cta.get("text", "")
                    )[:300],
                    "href": str(
                        cta.get("href", "")
                    )[:300],
                    "type": str(
                        cta.get("type", "")
                    )[:100]
                })

            else:

                compact["ctas"].append(
                    str(cta)[:300]
                )

    forms = page_data.get("forms", [])

    if isinstance(forms, list):

        for form in forms[:20]:

            if isinstance(form, dict):

                fields = form.get("fields", [])

                if not isinstance(fields, list):
                    fields = []

                compact["forms"].append({
                    "action": str(
                        form.get("action", "")
                    )[:300],
                    "method": str(
                        form.get("method", "")
                    )[:50],
                    "fields": fields[:20]
                })

            else:

                compact["forms"].append(
                    str(form)[:500]
                )

    links = page_data.get("links", [])

    if isinstance(links, list):

        for link in links[:60]:

            if isinstance(link, dict):

                compact["links"].append({
                    "text": str(
                        link.get("text", "")
                    )[:200],
                    "href": str(
                        link.get("href", "")
                    )[:300]
                })

            else:

                compact["links"].append(
                    str(link)[:300]
                )

    sections = page_data.get("sections", [])

    if isinstance(sections, list):

        for section in sections[:30]:

            if not isinstance(section, dict):
                continue

            compact_section = {
                "index": section.get("index"),
                "type": section.get("type"),
            }

            for key in [
                "heading",
                "title",
                "text",
                "description",
                "subheading",
                "content"
            ]:

                value = section.get(key)

                if value:

                    compact_section[key] = str(
                        value
                    )[:1200]

            section_ctas = section.get("ctas")

            if isinstance(section_ctas, list):

                compact_section["ctas"] = []

                for cta in section_ctas[:10]:

                    if isinstance(cta, dict):

                        compact_section["ctas"].append({
                            "text": str(
                                cta.get("text", "")
                            )[:200],
                            "href": str(
                                cta.get("href", "")
                            )[:250]
                        })

                    else:

                        compact_section["ctas"].append(
                            str(cta)[:200]
                        )

            images = section.get("images")

            if isinstance(images, list):

                compact_section["images"] = []

                for image in images[:10]:

                    if isinstance(image, dict):

                        compact_section["images"].append({
                            "alt": str(
                                image.get("alt", "")
                            )[:200],
                            "src": str(
                                image.get("src", "")
                            )[:250]
                        })

            compact["sections"].append(
                compact_section
            )

    result = json.dumps(
        compact,
        ensure_ascii=False,
        separators=(",", ":")
    )

    if len(result) > max_input_chars:

        compact["sections"] = compact["sections"][:20]

        for section in compact["sections"]:

            for key in [
                "text",
                "description",
                "content",
                "heading",
                "title",
                "subheading"
            ]:

                if key in section:

                    section[key] = str(
                        section[key]
                    )[:700]

        result = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":")
        )

    if len(result) > max_input_chars:

        compact["sections"] = compact["sections"][:12]
        compact["links"] = compact["links"][:30]
        compact["ctas"] = compact["ctas"][:25]

        result = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":")
        )

    # Enforce a real payload ceiling even when non-section data is large.
    while len(result) > max_input_chars:
        if compact["links"]:
            compact["links"].pop()
        elif compact["navigation"]:
            compact["navigation"].pop()
        elif compact["ctas"]:
            compact["ctas"].pop()
        elif compact["headings"]:
            compact["headings"].pop()
        elif compact["forms"]:
            compact["forms"].pop()
        elif compact["sections"]:
            compact["sections"].pop()
        elif compact["description"]:
            compact["description"] = compact["description"][:-100]
        elif compact["title"]:
            compact["title"] = compact["title"][:-100]
        else:
            break

        result = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":")
        )

    return result


def analyze_cro(page_data):

    print(
        "Preparing compact website data for Groq..."
    )

    compact_data = compact_page_data(
        page_data
    )

    print(
        f"Website data size reduced to "
        f"{len(compact_data):,} characters."
    )

    prompt = f"""
Analyze this website as an expert conversion rate
optimization consultant.

Your job is NOT to praise the website.

Identify the most important potential:

- conversion friction
- messaging problems
- trust issues
- UX problems
- objections
- missed conversion opportunities

IMPORTANT RULES:

1. Only make claims supported by the supplied data.
2. Do not invent analytics or conversion data.
3. Clearly distinguish observations from hypotheses.
4. Prioritize issues that could materially affect conversion.
5. Do not give generic CRO advice.
6. Reference actual website copy when useful.
7. Focus on what a first-time potential customer experiences.
8. Never invent statistics, customer results, or validation.
9. Do not call something a confirmed conversion problem
   unless the supplied data supports that conclusion.
10. If something is only a hypothesis, explicitly say so.
11. Do not assume information that is not present.
12. Keep the number of findings focused on the most important issues.

Return ONLY valid JSON.

Required structure:

{{
    "overall_summary": "short summary",

    "findings": [
        {{
            "title": "short title",
            "severity": "high | medium | low",
            "type": "friction | messaging | trust | ux | objection | conversion",

            "evidence": [
                "direct evidence from the website"
            ],

            "interpretation": "what the evidence suggests",

            "hypothesis": "potential impact on the customer journey",

            "recommendation": "specific recommendation",

            "suggested_change": "specific copy or UX change if applicable",

            "confidence": "high | medium | low"
        }}
    ],

    "top_3_priorities": [
        "priority 1",
        "priority 2",
        "priority 3"
    ]
}}

WEBSITE DATA:

{compact_data}
"""

    response_text = call_groq(
        prompt,
        max_tokens=1800
    )

    response_text = clean_json(
        response_text
    )

    try:

        json.loads(response_text)

    except json.JSONDecodeError:

        print(
            "Warning: Groq returned invalid JSON."
        )

        start = response_text.find("{")
        end = response_text.rfind("}")

        if start != -1 and end != -1:

            candidate = response_text[
                start:end + 1
            ]

            try:

                json.loads(candidate)

                return candidate

            except json.JSONDecodeError:
                pass

        raise RuntimeError(
            "Groq returned invalid JSON."
        )

    return response_text
