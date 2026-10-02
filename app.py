import argparse
import shutil

from constants import URL

import json
from pathlib import Path
from reporting import build_client_report
from audit_logging import log_audit_event

from personas import (
    DEFAULT_PERSONA_ID,
    get_persona,
    list_personas,
)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a CRO audit and one customer-persona simulation."
    )
    parser.add_argument(
        "--persona",
        default=DEFAULT_PERSONA_ID,
        help=(
            "Persona ID to simulate. Run with --list-personas to see "
            "available options."
        ),
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="Print available personas and exit.",
    )
    parser.add_argument(
        "--url",
        default=URL,
        help="Website URL to audit.",
    )
    return parser.parse_args()


ARGS = parse_args()

if ARGS.list_personas:
    print("Available personas:\n")
    for persona in list_personas():
        print(
            f"{persona['id']}: {persona['name']} "
            f"({persona['segment']} - {persona['role']})"
        )
    raise SystemExit(0)

SELECTED_PERSONA = get_persona(ARGS.persona)
TARGET_URL = ARGS.url


from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from ai import analyze_cro
from simulation_engine import (
    run_simulations,
    aggregate_simulations,
)


def clean_text(text):
    return " ".join(text.split())

def detect_sections(page):
    sections = []

    elements = page.locator(
        "section, header, main, footer"
    ).all()

    for index, element in enumerate(elements):

        try:
            text = clean_text(
                element.inner_text()
            )

            if not text:
                continue

            headings = []

            for heading in element.locator(
                "h1, h2, h3"
            ).all():

                heading_text = clean_text(
                    heading.inner_text()
                )

                if heading_text:
                    headings.append(heading_text)

            buttons = []

            for button in element.locator(
                "button, a"
            ).all():

                button_text = clean_text(
                    button.inner_text()
                )

                if button_text:
                    buttons.append(button_text)

            sections.append({
                "index": index,
                "headings": headings,
                "buttons": buttons,
                "text": text[:5000]
            })

        except Exception:
            continue

    return sections

def classify_section(section):
    text = (
        section["text"] + " " +
        " ".join(section["headings"]) + " " +
        " ".join(section["buttons"])
    ).lower()

    if section["index"] == 0:
        return "navigation"

    if any(
        phrase in text
        for phrase in [
            "predict what converts",
            "get started",
            "book a demo",
            "try for free"
        ]
    ) and section["index"] <= 2:
        return "hero"

    if any(
        phrase in text
        for phrase in [
            "trusted by",
            "backed by",
            "advised by",
            "customers",
            "users",
            "wayfair",
            "walmart",
            "gopro"
        ]
    ):
        return "social_proof"

    if any(
        phrase in text
        for phrase in [
            "how our model works",
            "how it works",
            "under the hood"
        ]
    ):
        return "how_it_works"

    if any(
        phrase in text
        for phrase in [
            "frequently asked",
            "faq",
            "common questions"
        ]
    ):
        return "faq"

    if any(
        phrase in text
        for phrase in [
            "pricing",
            "plans",
            "per month",
            "per year"
        ]
    ):
        return "pricing"

    if any(
        phrase in text
        for phrase in [
            "contact",
            "shipping address",
            "payment",
            "checkout"
        ]
    ):
        return "checkout"

    if any(
        phrase in text
        for phrase in [
            "get started",
            "book a demo",
            "try for free",
            "start free"
        ]
    ):
        return "cta"

    return "other"

with sync_playwright() as p:
    chromium_path = (
        shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
    )
    launch_options = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }

    if chromium_path:
        launch_options["executable_path"] = chromium_path

    browser = p.chromium.launch(**launch_options)

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 900
        }
    )

    print(f"Auditing: {TARGET_URL}")
    log_audit_event(
        TARGET_URL,
        SELECTED_PERSONA,
        status="started",
    )

    try:
        page.goto(
            TARGET_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )
    except PlaywrightError as error:
        error_text = str(error)
        log_audit_event(
            TARGET_URL,
            SELECTED_PERSONA,
            status="failed",
            error=error_text,
        )
        print(
            f"Unable to access {TARGET_URL}. The website or local network "
            "blocked the browser request."
        )
        print(f"Playwright details: {error_text}")
        browser.close()
        raise SystemExit(1)

    # Allow JavaScript-rendered content to appear
    page.wait_for_timeout(2000)

    # --------------------------------------------------
    # BASIC PAGE INFORMATION
    # --------------------------------------------------

    title = page.title()

    meta_locator = page.locator(
        'meta[name="description"]'
    )

    if meta_locator.count() > 0:
        meta_description = meta_locator.first.get_attribute("content")
    else:
        meta_description = None

    # --------------------------------------------------
    # HEADINGS
    # --------------------------------------------------

    headings = []

    for element in page.locator("h1, h2, h3").all():
        tag = element.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

        text = clean_text(element.inner_text())

        if text:
            headings.append({
                "tag": tag,
                "text": text
            })

    # --------------------------------------------------
    # BUTTONS
    # --------------------------------------------------

    buttons = []

    for element in page.locator("button").all():
        text = clean_text(element.inner_text())

        if text:
            buttons.append({
                "text": text,
                "type": element.get_attribute("type"),
                "aria_label": element.get_attribute("aria-label")
            })

    # --------------------------------------------------
    # LINKS
    # --------------------------------------------------

    links = []

    for element in page.locator("a").all():
        text = clean_text(element.inner_text())
        href = element.get_attribute("href")

        if text or href:
            links.append({
                "text": text,
                "href": href
            })

    # --------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------

    navigation = []

    for element in page.locator("nav a").all():
        text = clean_text(element.inner_text())
        href = element.get_attribute("href")

        if text or href:
            navigation.append({
                "text": text,
                "href": href
            })

    # --------------------------------------------------
    # FORMS
    # --------------------------------------------------

    forms = []

    for form in page.locator("form").all():

        fields = []

        for field in form.locator(
            "input, textarea, select"
        ).all():

            fields.append({
                "tag": field.evaluate(
                    "(el) => el.tagName.toLowerCase()"
                ),
                "type": field.get_attribute("type"),
                "name": field.get_attribute("name"),
                "placeholder": field.get_attribute("placeholder"),
                "required": field.get_attribute("required") is not None
            })

        forms.append({
            "action": form.get_attribute("action"),
            "method": form.get_attribute("method"),
            "fields": fields
        })

    # --------------------------------------------------
    # IMAGES
    # --------------------------------------------------

    images = []

    for image in page.locator("img").all():

        images.append({
            "src": image.get_attribute("src"),
            "alt": image.get_attribute("alt"),
            "width": image.get_attribute("width"),
            "height": image.get_attribute("height")
        })

    # --------------------------------------------------
    # BODY TEXT
    # --------------------------------------------------

    body_text = clean_text(
        page.locator("body").inner_text()
    )

    page_sections = detect_sections(page)

    for section in page_sections:
        section["type"] = classify_section(section)

    # --------------------------------------------------
    # PAGE METRICS
    # --------------------------------------------------

    page_metrics = {
        "width": page.evaluate(
            "() => document.documentElement.scrollWidth"
        ),
        "height": page.evaluate(
            "() => document.documentElement.scrollHeight"
        ),
        "viewport_width": 1440,
        "viewport_height": 900
    }

    # --------------------------------------------------
    # CRO SIGNALS
    # --------------------------------------------------

    body_lower = body_text.lower()

    cro_signals = {
        "has_pricing_language": any(
            word in body_lower
            for word in [
                "pricing",
                "price",
                "plans",
                "cost"
            ]
        ),

        "has_demo_language": any(
            phrase in body_lower
            for phrase in [
                "book a demo",
                "request a demo",
                "schedule a demo",
                "get a demo",
                "demo"
            ]
        ),

        "has_trial_language": any(
            phrase in body_lower
            for phrase in [
                "free trial",
                "start trial",
                "try free",
                "try it free"
            ]
        ),

        "has_testimonial_language": any(
            phrase in body_lower
            for phrase in [
                "testimonial",
                "what our customers say",
                "customer story",
                "customers say"
            ]
        ),

        "has_social_proof_language": any(
            phrase in body_lower
            for phrase in [
                "trusted by",
                "used by",
                "companies use",
                "customers"
            ]
        ),

        "has_faq_language": any(
            phrase in body_lower
            for phrase in [
                "frequently asked",
                "faq",
                "common questions"
            ]
        )
    }

    # --------------------------------------------------
    # SCREENSHOT
    # --------------------------------------------------

    screenshot_path = OUTPUT_DIR / "homepage.png"

    page.screenshot(
        path=str(screenshot_path),
        full_page=True
    )

    # --------------------------------------------------
    # FINAL DATA STRUCTURE
    # --------------------------------------------------

    data = {
        "url": TARGET_URL,

        "page": {
            "title": title,
            "meta_description": meta_description,
            "metrics": page_metrics
        },

        "headings": headings,

        "navigation": navigation,

        "buttons": buttons,

        "links": links,

        "forms": forms,

        "images": images,

        "body_text": body_text,

        "sections": page_sections,

        "cro_signals": cro_signals,

        "screenshot": str(screenshot_path)
    }

    # --------------------------------------------------
    # SAVE JSON
    # --------------------------------------------------

    json_path = OUTPUT_DIR / "page_data.json"

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    browser.close()


print("Audit completed successfully.")
print(f"Data saved to: {json_path}")
print(f"Screenshot saved to: {screenshot_path}")
# 
print("Sending page data to Groq...")

analysis = analyze_cro(data)

analysis_path = OUTPUT_DIR / "cro_analysis.json"

with open(
    analysis_path,
    "w",
    encoding="utf-8"
) as file:
    file.write(analysis)

print(f"CRO analysis saved to: {analysis_path}")
# 
print("\nStarting customer simulations...")
print(
    f"Selected persona: {SELECTED_PERSONA['name']} "
    f"({SELECTED_PERSONA['id']})"
)

simulation_results = run_simulations(
    data,
    [SELECTED_PERSONA],
)

with open(
    "output/simulation_results.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        simulation_results,
        f,
        indent=2,
        ensure_ascii=False
    )

print(
    "Simulation results saved to: "
    "output/simulation_results.json"
)


aggregated = aggregate_simulations(
    simulation_results,
    page_data=data,
    cro_analysis=analysis,
)

with open(
    "output/simulation_analysis.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        aggregated,
        f,
        indent=2,
        ensure_ascii=False
    )

print(
    "Simulation analysis saved to: "
    "output/simulation_analysis.json"
)

final_report = build_client_report(
    TARGET_URL,
    SELECTED_PERSONA,
    aggregated,
    cro_analysis=analysis,
)

report_path = OUTPUT_DIR / "final_report.json"

with open(report_path, "w", encoding="utf-8") as file:
    json.dump(final_report, file, indent=2, ensure_ascii=False)

print(f"Client report saved to: {report_path}")
log_audit_event(
    TARGET_URL,
    SELECTED_PERSONA,
    status="completed",
    report_path=report_path,
)
