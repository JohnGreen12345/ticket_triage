"""Triage engine — keyword matching, scoring, and deterministic ranking.

Pure functions with no HTTP or framework dependency.
Same input always produces the same output.
"""

from app.models import Recommendation

# ---------------------------------------------------------------------------
# Category definitions: keywords → (action, why)
# ---------------------------------------------------------------------------
CATEGORIES: dict[str, dict] = {
    "auth": {
        "keywords": [
            "login", "log in", "password", "reset", "locked", "sign in",
            "credential", "authentication", "sso", "mfa", "2fa", "otp",
            "token", "session", "expired",
        ],
        "actions": [
            {
                "action": "Verify account status and recent lockouts",
                "why": "Login failures after a reset often correlate with account lockouts or disabled accounts.",
            },
            {
                "action": "Check auth provider error logs for this user",
                "why": "The error may originate from the identity provider rather than the application itself.",
            },
            {
                "action": "Ask user for exact error code and timestamp",
                "why": "Pinpointing the time and code speeds up correlation across authentication systems.",
            },
        ],
    },
    "billing": {
        "keywords": [
            "charge", "invoice", "payment", "billing", "subscription",
            "refund", "credit", "price", "plan", "upgrade", "downgrade",
            "receipt", "overcharge", "double charge",
        ],
        "actions": [
            {
                "action": "Pull up billing history for this account",
                "why": "Reviewing recent transactions clarifies whether charges are duplicated or expected.",
            },
            {
                "action": "Verify subscription tier and renewal date",
                "why": "Billing issues often stem from tier mismatches or unexpected renewals.",
            },
            {
                "action": "Check payment gateway logs for declined or pending transactions",
                "why": "Gateway errors can cause phantom charges or failed payment notifications.",
            },
        ],
    },
    "performance": {
        "keywords": [
            "slow", "latency", "timeout", "loading", "performance", "lag",
            "hang", "freeze", "unresponsive", "speed", "delay", "crash",
            "down", "outage", "500", "error",
        ],
        "actions": [
            {
                "action": "Check service health dashboard and recent incidents",
                "why": "Slow responses may be caused by an ongoing incident or degraded service.",
            },
            {
                "action": "Review application logs around the reported time window",
                "why": "Correlating logs with the user's timeline can reveal bottlenecks or exceptions.",
            },
            {
                "action": "Ask user for browser, device, and network details",
                "why": "Client-side factors like browser version or network quality often contribute to perceived slowness.",
            },
        ],
    },
    "data": {
        "keywords": [
            "missing", "lost", "data", "deleted", "disappeared", "gone",
            "restore", "backup", "recovery", "corrupted", "wrong",
            "incorrect", "sync",
        ],
        "actions": [
            {
                "action": "Check recent data modification audit trail",
                "why": "Audit logs reveal whether data was deleted manually, by automation, or via sync conflict.",
            },
            {
                "action": "Verify backup availability and last successful snapshot",
                "why": "If data was recently lost, a backup restore may be the fastest resolution.",
            },
            {
                "action": "Ask user when data was last seen and what actions were taken",
                "why": "Narrowing the time window reduces the scope of investigation significantly.",
            },
        ],
    },
    "access": {
        "keywords": [
            "permission", "access", "denied", "forbidden", "role",
            "privilege", "unauthorized", "403", "invite", "share",
            "team", "admin",
        ],
        "actions": [
            {
                "action": "Review user role and permission assignments",
                "why": "Access errors are most commonly caused by missing or recently changed role assignments.",
            },
            {
                "action": "Check if a recent permissions policy change affects this user",
                "why": "Org-wide policy updates can silently revoke access for specific roles.",
            },
            {
                "action": "Verify the resource exists and is not restricted",
                "why": "The user may be requesting access to a resource that was archived or moved.",
            },
        ],
    },
}

# Fallback when no category matches at all
FALLBACK_ACTIONS: list[dict[str, str]] = [
    {
        "action": "Gather full reproduction steps from the user",
        "why": "Detailed steps allow support to classify and route the ticket accurately.",
    },
    {
        "action": "Search knowledge base for similar reported issues",
        "why": "A matching article may provide an immediate resolution or known workaround.",
    },
    {
        "action": "Escalate to Tier 2 with full context attached",
        "why": "When the issue does not match common patterns, early escalation avoids repeated back-and-forth.",
    },
]


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the lowercased text."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


def get_recommendations(
    title: str,
    description: str,
    top_n: int = 3,
) -> list[Recommendation]:
    """Return ranked recommendations for a support ticket.

    Deterministic: same input → same output every time.
    """
    combined_text = f"{title} {description}"

    # Score each category by keyword match count
    scored: list[tuple[str, int]] = []
    for cat_name, cat_data in CATEGORIES.items():
        matches = _count_keyword_matches(combined_text, cat_data["keywords"])
        if matches > 0:
            scored.append((cat_name, matches))

    # Sort by match count descending, then alphabetically for tie-breaking
    scored.sort(key=lambda x: (-x[1], x[0]))

    # Build recommendations from top-scoring categories
    recommendations: list[Recommendation] = []
    max_possible = max(
        (len(cat["keywords"]) for cat in CATEGORIES.values()), default=1
    )

    for cat_name, matches in scored:
        cat_data = CATEGORIES[cat_name]
        base_confidence = min(matches / max_possible, 0.95)

        for i, action_data in enumerate(cat_data["actions"]):
            if len(recommendations) >= top_n:
                break
            # Each successive action in a category gets slightly lower confidence
            confidence = round(base_confidence * (1 - i * 0.15), 2)
            confidence = max(confidence, 0.05)  # floor
            recommendations.append(
                Recommendation(
                    action=action_data["action"],
                    confidence=confidence,
                    why=action_data["why"],
                )
            )
        if len(recommendations) >= top_n:
            break

    # Fallback if nothing matched
    if not recommendations:
        for i, action_data in enumerate(FALLBACK_ACTIONS[:top_n]):
            confidence = round(0.40 * (1 - i * 0.15), 2)
            recommendations.append(
                Recommendation(
                    action=action_data["action"],
                    confidence=confidence,
                    why=action_data["why"],
                )
            )

    return recommendations[:top_n]
