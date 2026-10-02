import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from personas import list_personas
from reporting import build_report_pdf


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
REPORT_PATH = OUTPUT_DIR / "final_report.json"
MAX_AUDITS_PER_SESSION = 5

if "audit_count" not in st.session_state:
    st.session_state["audit_count"] = 0


for secret_name in ("GROQ_API_KEY", "GEMINI_API_KEY"):
    if not os.getenv(secret_name):
        try:
            secret_value = st.secrets.get(secret_name)
        except (FileNotFoundError, KeyError):
            secret_value = None

        if secret_value:
            os.environ[secret_name] = str(secret_value)


st.set_page_config(
    page_title="AI-powered Website Audit",
    page_icon=":mag:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.title("AI-powered Website Audit")
st.caption(
    "See how a customer persona experiences your website, identify conversion "
    "friction, and leave with a focused test plan."
)
st.caption(
    f"Audits used this session: {st.session_state['audit_count']} / "
    f"{MAX_AUDITS_PER_SESSION}"
)

persona_options = list_personas()
business_types = [
    "B2B SaaS",
    "D2C Ecommerce Brand",
    "B2C SaaS",
]

url = st.text_input(
    "Website URL",
    placeholder="https://example.com",
)

selected_business_type = st.selectbox(
    "Business type",
    business_types,
)

filtered_personas = [
    persona
    for persona in persona_options
    if persona["segment"] == selected_business_type
]
persona_labels = {
    persona["name"]: persona["id"]
    for persona in filtered_personas
}

with st.form("audit_form"):
    selected_label = st.selectbox("Customer persona", list(persona_labels))
    submitted = st.form_submit_button("Run audit", type="primary")

if submitted:
    if not url.startswith(("https://", "http://")):
        st.error("Enter a complete URL beginning with http:// or https://.")
    elif st.session_state["audit_count"] >= MAX_AUDITS_PER_SESSION:
        st.error(
            "This session has reached its limit of 5 audits. "
            "Start a new authorized session to continue."
        )
    else:
        st.session_state["audit_count"] += 1
        command = [
            sys.executable,
            str(PROJECT_DIR / "app.py"),
            "--url",
            url.strip(),
            "--persona",
            persona_labels[selected_label],
        ]

        with st.status("Running website audit...", expanded=False) as status:
            result = subprocess.run(
                command,
                cwd=str(PROJECT_DIR),
                capture_output=True,
                text=True,
                timeout=180,
            )
            audit_output = result.stdout or result.stderr
            # Forward child-process output to Streamlit Cloud's app logs.
            print(audit_output, flush=True)
            st.code(audit_output, language="text")

            audit_log_path = OUTPUT_DIR / "audit_log.jsonl"
            if audit_log_path.exists():
                log_lines = audit_log_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if log_lines:
                    latest_event = json.loads(log_lines[-1])
                    st.caption(
                        "Latest audit log: "
                        f"{latest_event.get('timestamp_ist')} IST | "
                        f"{latest_event.get('status')} | "
                        f"{latest_event.get('url')}"
                    )

            if result.returncode == 0 and REPORT_PATH.exists():
                status.update(label="Audit complete", state="complete")
                st.session_state["report"] = json.loads(
                    REPORT_PATH.read_text(encoding="utf-8")
                )
            else:
                status.update(label="Audit failed", state="error")
                st.error(result.stderr or "The audit did not produce a report.")

report = st.session_state.get("report")

if report:
    st.divider()
    st.caption("Audit result")
    st.write(
        f"**URL:** {report.get('url', '-')}  "
        f"\n\n**Persona:** {report.get('persona', {}).get('name', '-')}"
    )
    scores = report.get("scores", {})
    st.metric(
        "Overall conversion readiness",
        scores.get("conversion_readiness", "-"),
    )
    st.caption(
        "A combined 0-100 score across five website experience areas. "
        "Higher means fewer evidence-backed friction signals were identified."
    )

    st.subheader("Score breakdown")
    st.caption(
        "Each section is scored out of 20. These scores prioritize audit evidence; "
        "they are not conversion or revenue forecasts."
    )
    breakdown = report.get("score_breakdown", [])
    definitions = report.get("score_definitions", {})
    score_columns = st.columns(len(breakdown) or 1)

    for column, item in zip(score_columns, breakdown):
        with column:
            column.metric(item.get("name", "Section"), item.get("score", "-"))
            column.caption(definitions.get(item.get("name"), "Evidence-based section score."))

    st.subheader("What to test next")
    for insight in report.get("actionable_insights", []):
        with st.container(border=True):
            st.caption(f"Priority {insight['priority']}")
            st.markdown(f"**{insight['action']}**")
            st.write(insight["evidence"])

    st.subheader("Recommended next step")
    next_step = report.get("recommended_next_step", {})
    st.markdown(f"### {next_step.get('offer', 'A/B test or CRO program')}")
    st.write(next_step.get("reason", "Validate the top hypotheses with real visitor data."))

    st.caption(report.get("disclaimer", ""))
    st.download_button(
        "Download report JSON",
        data=json.dumps(report, indent=2, ensure_ascii=False),
        file_name="cro-opportunity-report.json",
        mime="application/json",
    )
    st.download_button(
        "Download report PDF",
        data=build_report_pdf(report),
        file_name="cro-opportunity-report.pdf",
        mime="application/pdf",
    )
