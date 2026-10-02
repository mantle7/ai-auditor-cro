PERSONAS = [
    {
        "id": "b2b_growth_lead",
        "segment": "B2B SaaS",
        "name": "Marketing Lead",
        "role": "Marketing / Growth lead",
        "company": "B2B SaaS company",
        "company_size": "100-500 employees",
        "goal": "Increase qualified demo requests and trial conversions.",
        "pain_points": ["Low website conversion rate", "Limited traffic for A/B testing", "Difficulty identifying why visitors abandon", "Pressure to demonstrate marketing ROI"],
        "buying_concerns": ["Accuracy", "Implementation effort", "Integration requirements", "Price", "Expected conversion improvement"],
        "desired_outcome": "Find the highest-priority conversion hypotheses quickly.",
    },
    {
        "id": "b2b_technical_evaluator",
        "segment": "B2B SaaS",
        "name": "Technical Buyer",
        "role": "Technical decision-maker",
        "company": "B2B SaaS company",
        "company_size": "50-250 employees",
        "goal": "Determine whether the product is credible, secure, and practical to integrate.",
        "pain_points": ["Too many tools", "Integration complexity", "Security concerns", "Limited engineering bandwidth"],
        "buying_concerns": ["Security", "Implementation requirements", "Integrations", "Data handling", "Technical credibility"],
        "desired_outcome": "Understand technical fit and implementation effort before involving the team.",
    },
    {
        "id": "b2b_budget_owner",
        "segment": "B2B SaaS",
        "name": "CEO / Founder",
        "role": "CEO / Founder",
        "company": "Early-stage B2B SaaS company",
        "company_size": "10-50 employees",
        "goal": "Increase revenue from existing website traffic without adding unnecessary tools.",
        "pain_points": ["Low traffic volume", "Low conversion rate", "Limited marketing resources", "Pressure to grow efficiently"],
        "buying_concerns": ["ROI", "Price", "Time to value", "Vendor credibility", "Contract commitment"],
        "desired_outcome": "See a credible path to value before committing budget.",
    },
    {
        "id": "consumer_saas_trial_user",
        "segment": "B2C SaaS",
        "name": "First-Time User",
        "role": "Independent professional",
        "company": "Self-employed",
        "company_size": "1",
        "goal": "Quickly decide whether a consumer software product solves a personal workflow problem.",
        "pain_points": ["Too many subscriptions", "Limited time to learn new software", "Unclear product differences", "Fear of surprise charges"],
        "buying_concerns": ["Free-trial terms", "Monthly price", "Ease of use", "Privacy", "Cancellation process"],
        "desired_outcome": "Start a low-risk trial and understand the value before paying.",
    },
    {
        "id": "b2c_saas_value_subscriber",
        "segment": "B2C SaaS",
        "name": "Value-Conscious Subscriber",
        "role": "Potential subscriber",
        "company": "Individual consumer",
        "company_size": "1",
        "goal": "Choose a useful subscription that feels worth paying for every month.",
        "pain_points": ["Subscription fatigue", "Unclear feature limits", "Hard-to-compare plans", "Uncertain long-term value"],
        "buying_concerns": ["Plan limits", "Monthly and annual pricing", "Cancellation", "Core feature access", "Ongoing usefulness"],
        "desired_outcome": "Select the right plan and feel confident keeping the subscription.",
    },
    {
        "id": "confused_first_time_shopper",
        "segment": "D2C Ecommerce Brand",
        "name": "Confused First-Time Shopper",
        "role": "First-time buyer",
        "company": "Consumer household",
        "company_size": "1",
        "goal": "Choose the right product confidently without spending too long researching.",
        "pain_points": ["Too many similar product options", "Unclear product differences", "Uncertainty about fit or suitability", "Fear of making the wrong purchase"],
        "buying_concerns": ["Which option is right for me", "Price", "Returns", "Shipping time", "Product quality"],
        "desired_outcome": "Understand the product, choose the right variant, and buy with confidence.",
    },
    {
        "id": "deal_comparison_shopper",
        "segment": "D2C Ecommerce Brand",
        "name": "Deal Comparison Shopper",
        "role": "Value-focused buyer",
        "company": "Consumer household",
        "company_size": "1",
        "goal": "Find the best overall value before purchasing.",
        "pain_points": ["Many competing stores", "Unclear discount terms", "Unexpected delivery costs", "Difficulty comparing bundles"],
        "buying_concerns": ["Total delivered price", "Discount legitimacy", "Bundle value", "Shipping costs", "Return policy"],
        "desired_outcome": "Complete a purchase knowing the offer is competitive and transparent.",
    },
    {
        "id": "trust_seeking_customer",
        "segment": "D2C Ecommerce Brand",
        "name": "Trust-Seeking Customer",
        "role": "Research-oriented shopper",
        "company": "Consumer household",
        "company_size": "1",
        "goal": "Verify product quality and brand credibility before sharing payment details.",
        "pain_points": ["Unknown brands", "Overstated marketing claims", "Unclear return process", "Concern about payment security"],
        "buying_concerns": ["Reviews", "Materials or ingredients", "Returns and refunds", "Customer support", "Payment security"],
        "desired_outcome": "Find enough evidence to trust the brand and purchase safely.",
    },
    {
        "id": "repeat_d2c_customer",
        "segment": "D2C Ecommerce Brand",
        "name": "Returning D2C Customer",
        "role": "Repeat buyer",
        "company": "Consumer household",
        "company_size": "1",
        "goal": "Reorder a familiar product quickly or discover a relevant complementary item.",
        "pain_points": ["Slow product discovery", "Out-of-stock items", "Complicated checkout", "Irrelevant recommendations"],
        "buying_concerns": ["Availability", "Reorder speed", "Loyalty value", "Delivery timing", "Checkout convenience"],
        "desired_outcome": "Complete a quick, low-friction repeat purchase.",
    },
]

DEFAULT_PERSONA_ID = "b2b_growth_lead"


def get_persona(persona_id):
    for persona in PERSONAS:
        if persona["id"] == persona_id:
            return persona

    available_ids = ", ".join(persona["id"] for persona in PERSONAS)
    raise ValueError(
        f"Unknown persona '{persona_id}'. Available personas: {available_ids}"
    )


def list_personas():
    return [
        {
            "id": persona["id"],
            "segment": persona["segment"],
            "name": persona["name"],
            "role": persona["role"],
        }
        for persona in PERSONAS
    ]
