import json
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


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


def build_report_pdf(report):
    """Render the client report as a portable PDF download."""

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SmallMuted",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=colors.HexColor("#667482"),
        leading=12,
    ))
    styles.add(ParagraphStyle(
        name="Action",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=4,
    ))

    persona = report.get("persona", {})
    scores = report.get("scores", {})
    story = [
        Paragraph("AI-powered Website Audit", styles["Title"]),
        Paragraph("CRO Opportunity Snapshot", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"<b>URL:</b> {report.get('url', '-')}", styles["Normal"]),
        Paragraph(
            f"<b>Persona:</b> {persona.get('name', '-')} ({persona.get('segment', '-')})",
            styles["Normal"],
        ),
        Spacer(1, 14),
        Paragraph("Overall conversion readiness", styles["Heading2"]),
        Paragraph(
            str(scores.get("conversion_readiness", "-")),
            styles["Title"],
        ),
        Spacer(1, 8),
    ]

    breakdown_rows = [["Section", "Score", "Definition"]]
    for item in report.get("score_breakdown", []):
        name = item.get("name", "Section")
        definition = report.get("score_definitions", {}).get(name, "Evidence-based section score.")
        breakdown_rows.append([name, f"{item.get('score', '-')} / 20", definition])

    breakdown = Table(breakdown_rows, colWidths=[1.55 * inch, 0.8 * inch, 4.6 * inch])
    breakdown.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17212b")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dee4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([breakdown, Spacer(1, 16)])

    story.append(Paragraph("What to test next", styles["Heading2"]))
    for insight in report.get("actionable_insights", []):
        story.extend([
            Paragraph(
                f"<b>{insight.get('priority', '')}. {insight.get('action', '')}</b>",
                styles["Action"],
            ),
            Paragraph(f"Evidence: {insight.get('evidence', '-')}", styles["Normal"]),
            Spacer(1, 8),
        ])

    next_step = report.get("recommended_next_step", {})
    story.extend([
        Paragraph("Recommended next step", styles["Heading2"]),
        Paragraph(f"<b>{next_step.get('offer', '-')}</b>", styles["Normal"]),
        Paragraph(next_step.get("reason", "-"), styles["Normal"]),
        Spacer(1, 12),
        Paragraph(report.get("disclaimer", ""), styles["SmallMuted"]),
    ])

    document.build(story)
    return buffer.getvalue()
