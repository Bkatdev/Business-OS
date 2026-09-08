"""
Business OS Opportunity Scoring

Scoring principle:
- Never treat unknown website information as a confirmed weakness.
- Website-feature points are only awarded after a completed audit.
- Review strength can be scored independently because it comes from
  structured business data such as Google Places.

Current score: 100 possible points.
"""


def _value(business, key, default=None):
    """
    Safely read a value from either a sqlite Row or a dictionary.
    """
    try:
        value = business[key]
    except (KeyError, IndexError, TypeError):
        return default

    if value is None:
        return default

    return value


def opportunity_analysis(business):
    """
    Analyze one business and return its opportunity score,
    opportunity level, reasons, and audit state.

    Website weaknesses are scored only when the website audit
    successfully completed.
    """

    score = 0
    reasons = []

    reviews = int(_value(business, "reviews", 0) or 0)
    audit_status = str(
        _value(business, "audit_status", "not_audited") or "not_audited"
    ).lower()

    # ---------------------------------------------------------
    # REVIEW STRENGTH
    # ---------------------------------------------------------
    # A business with substantial reviews has evidence of real
    # customer demand and may be more valuable as a prospect.
    if reviews >= 100:
        score += 20
        reasons.append(
            ("Strong customer demand / review volume", 20)
        )

    # ---------------------------------------------------------
    # DO NOT GUESS ABOUT WEBSITE FEATURES
    # ---------------------------------------------------------
    if audit_status != "completed":
        return {
            "score": None,
            "level": "Pending Audit",
            "reasons": reasons,
            "audit_status": audit_status,
            "scorable": False,
        }

    # ---------------------------------------------------------
    # WEBSITE AUDIT SIGNALS
    # ---------------------------------------------------------

    online_booking = bool(
        _value(business, "online_booking", 0)
    )

    emergency_service = bool(
        _value(business, "emergency_service", 0)
    )

    website_chat = bool(
        _value(business, "website_chat", 0)
    )

    estimate_form = bool(
        _value(business, "estimate_form", 0)
    )

    # No real online booking detected
    if not online_booking:
        score += 25
        reasons.append(
            ("No actual online booking detected", 25)
        )

    # Emergency/high-intent service is valuable because missed
    # calls or slow responses can represent valuable jobs.
    if emergency_service:
        score += 20
        reasons.append(
            ("Emergency / high-intent service detected", 20)
        )

    # No website chat detected
    if not website_chat:
        score += 15
        reasons.append(
            ("No website chat detected", 15)
        )

    # No actual estimate/request form detected
    if not estimate_form:
        score += 20
        reasons.append(
            ("No online estimate form detected", 20)
        )

    # ---------------------------------------------------------
    # OPPORTUNITY LEVEL
    # ---------------------------------------------------------

    if score >= 70:
        level = "High"
    elif score >= 40:
        level = "Medium"
    else:
        level = "Low"

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "audit_status": audit_status,
        "scorable": True,
    }


# Backwards-compatible alias.
# Older Business OS code may still import analyze_business.
def analyze_business(business):
    return opportunity_analysis(business)