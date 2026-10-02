import json


SEVERITY_DEDUCTIONS = {
    "high": 6,
    "medium": 4,
    "low": 2,
}

DIMENSIONS = {
    "value_clarity": "Value clarity",
    "conversion_path": "Conversion path",
    "trust_and_risk": "Trust and risk reduction",
    "friction": "Journey friction",
    "evaluation_clarity": "Evaluation clarity",
}


def _as_analysis(cro_analysis):
    if isinstance(cro_analysis, dict):
        return cro_analysis

    if isinstance(cro_analysis, str):
        try:
            return json.loads(cro_analysis)
        except json.JSONDecodeError:
            return {}

    return {}


def _deduct(scores, dimension, amount, evidence, drivers):
    before = scores[dimension]
    scores[dimension] = max(0, scores[dimension] - amount)

    if scores[dimension] != before:
        drivers.append({
            "dimension": DIMENSIONS[dimension],
            "deduction": before - scores[dimension],
            "evidence": evidence,
        })


def _revenue_scenario(revenue_inputs):
    required = {
        "monthly_visitors",
        "baseline_conversion_rate",
        "average_conversion_value",
        "assumed_relative_lift_range",
    }

    if not isinstance(revenue_inputs, dict) or not required.issubset(revenue_inputs):
        return {
            "status": "requires_client_baseline",
            "message": (
                "Provide monthly visitors, baseline conversion rate, average "
                "conversion value, and an explicit assumed relative lift range."
            ),
        }

    try:
        visitors = float(revenue_inputs["monthly_visitors"])
        conversion_rate = float(revenue_inputs["baseline_conversion_rate"])
        conversion_value = float(revenue_inputs["average_conversion_value"])
        low_lift, high_lift = revenue_inputs["assumed_relative_lift_range"]
        low_lift = float(low_lift)
        high_lift = float(high_lift)
    except (TypeError, ValueError, IndexError):
        return {
            "status": "invalid_client_baseline",
            "message": "Revenue inputs must be valid numeric values.",
        }

    if conversion_rate > 1:
        conversion_rate /= 100
    if min(visitors, conversion_rate, conversion_value, low_lift, high_lift) < 0:
        return {
            "status": "invalid_client_baseline",
            "message": "Revenue inputs cannot be negative.",
        }

    baseline_monthly_value = visitors * conversion_rate * conversion_value

    return {
        "status": "hypothetical_client_scenario",
        "baseline_monthly_conversion_value": round(baseline_monthly_value, 2),
        "estimated_monthly_increment_range": {
            "low": round(baseline_monthly_value * low_lift, 2),
            "high": round(baseline_monthly_value * high_lift, 2),
        },
        "assumptions": {
            "monthly_visitors": visitors,
            "baseline_conversion_rate": conversion_rate,
            "average_conversion_value": conversion_value,
            "assumed_relative_lift_range": [low_lift, high_lift],
        },
        "disclaimer": (
            "This is a client-supplied scenario, not a predicted outcome. "
            "Validate it with analytics and experiments."
        ),
    }


def build_scorecard(
    page_data,
    simulation_summary,
    cro_analysis=None,
    revenue_inputs=None,
):
    """Create an explainable local score without another model request."""

    scores = {key: 20 for key in DIMENSIONS}
    drivers = []
    analysis = _as_analysis(cro_analysis)

    type_dimensions = {
        "messaging": "value_clarity",
        "conversion": "conversion_path",
        "trust": "trust_and_risk",
        "friction": "friction",
        "ux": "friction",
        "objection": "evaluation_clarity",
    }

    for finding in analysis.get("findings", []):
        if not isinstance(finding, dict):
            continue

        dimension = type_dimensions.get(finding.get("type"))
        if dimension:
            _deduct(
                scores,
                dimension,
                SEVERITY_DEDUCTIONS.get(finding.get("severity"), 2),
                finding.get("title") or finding.get("interpretation") or "CRO finding",
                drivers,
            )

    decision = simulation_summary.get("overall_decision")
    if decision == "abandon":
        _deduct(
            scores,
            "conversion_path",
            8,
            "The simulated customer abandoned the journey.",
            drivers,
        )
    elif decision == "hesitate":
        _deduct(
            scores,
            "conversion_path",
            4,
            "The simulated customer hesitated before converting.",
            drivers,
        )

    objections = " ".join(
        str(item) for item in simulation_summary.get("key_objections", [])
    ).lower()
    keyword_dimensions = {
        "pricing": "evaluation_clarity",
        "price": "evaluation_clarity",
        "demo": "conversion_path",
        "trial": "conversion_path",
        "cta": "conversion_path",
        "implementation": "friction",
        "integration": "friction",
        "trust": "trust_and_risk",
        "proof": "trust_and_risk",
        "roi": "value_clarity",
    }

    for keyword, dimension in keyword_dimensions.items():
        if keyword in objections:
            _deduct(
                scores,
                dimension,
                3,
                f"Simulated objection mentions {keyword}.",
                drivers,
            )

    readiness_score = sum(scores.values())
    severity_opportunity = sum(
        SEVERITY_DEDUCTIONS.get(
            finding.get("severity"),
            2,
        ) * 3
        for finding in analysis.get("findings", [])
        if isinstance(finding, dict)
    )
    simulation_opportunity = {
        "continue": 0,
        "hesitate": 12,
        "abandon": 25,
    }.get(decision, 5)
    objection_opportunity = min(
        20,
        len(simulation_summary.get("key_objections", [])) * 5,
    )
    opportunity_score = min(
        100,
        severity_opportunity + simulation_opportunity + objection_opportunity,
    )
    confidence = "low"
    if simulation_summary.get("total_runs", 0) > 1 and analysis.get("findings"):
        confidence = "medium"

    return {
        "method": "deterministic_evidence_score",
        "conversion_readiness_score": readiness_score,
        "cro_opportunity_score": opportunity_score,
        "revenue_readiness_score": readiness_score,
        "confidence": confidence,
        "dimensions": [
            {
                "name": DIMENSIONS[key],
                "score": score,
                "maximum": 20,
            }
            for key, score in scores.items()
        ],
        "evidence_drivers": drivers[:12],
        "score_interpretation": {
            "conversion_readiness": (
                "Higher means fewer evidence-backed friction signals were found."
            ),
            "cro_opportunity": (
                "Higher means more high-severity findings, objections, or "
                "simulated hesitation/abandonment were identified. It is not "
                "a probability, revenue forecast, or conversion uplift estimate."
            ),
            "components": {
                "website_finding_severity": severity_opportunity,
                "simulated_outcome": simulation_opportunity,
                "customer_objections": objection_opportunity,
            },
        },
        "revenue_opportunity_scenario": _revenue_scenario(revenue_inputs),
        "recommended_next_step": {
            "offer": "Run a focused A/B test or start a CRO program",
            "reason": (
                "Use the first insight as an A/B test hypothesis. If the site "
                "needs several coordinated changes, a CRO program can manage "
                "research, implementation, and experiment measurement."
            ),
            "scope": [
                "Confirm the baseline conversion event and current performance.",
                "Test the highest-priority insight against the current experience.",
                "Use a CRO program when multiple experiments need to be prioritized and executed.",
            ],
        },
        "disclaimer": (
            "Scores prioritize audit evidence and one simulated journey. They "
            "do not measure real visitor behavior or guarantee revenue impact."
        ),
    }
