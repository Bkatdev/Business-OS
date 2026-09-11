"""Business OS v13 - evidence-backed prospect sales intelligence."""

from __future__ import annotations

from services.scoring import opportunity_analysis


def _bool(business, key):
    try:
        return bool(business[key])
    except (KeyError, IndexError, TypeError):
        return False


def _value(business, key, default=""):
    try:
        value = business[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def build_sales_brief(business):
    """Return sales guidance that never upgrades unknown evidence into fact."""
    analysis = opportunity_analysis(business)
    audit_status = str(_value(business, "audit_status", "not_audited") or "not_audited")
    completed = audit_status == "completed"

    pitch_points = []
    cautions = []
    discovery_questions = []

    reviews = int(_value(business, "reviews", 0) or 0)
    if reviews >= 100:
        pitch_points.append(
            "The business has substantial public review volume, so the conversation can focus on whether its website experience matches the strength of its reputation."
        )

    if not completed:
        cautions.append(
            "Website weaknesses are not scored until the public-site audit completes. Do not pitch missing features as facts yet."
        )
        return {
            "analysis": analysis,
            "recommended_plan": "Audit first",
            "plan_reason": "Business OS does not yet have enough website evidence to recommend a starting package responsibly.",
            "pitch_points": pitch_points,
            "cautions": cautions,
            "discovery_questions": [
                "What is the biggest problem with the current website today?",
                "How do new customers usually contact the business?",
            ],
            "next_action": "Complete the website audit before building the sales angle.",
            "complete_plan_note": "Complete automation requires owner discovery and is never prescribed from public web evidence alone.",
        }

    if not _bool(business, "estimate_form"):
        pitch_points.append(
            "No online estimate/quote form was detected in the pages Business OS inspected. Show the owner a clearer request path, while describing this only as 'not detected.'"
        )
    if not _bool(business, "online_booking"):
        pitch_points.append(
            "No actual online booking integration was detected. Ask whether scheduling is intentionally phone-based before proposing scheduling automation."
        )
    if not _bool(business, "website_chat"):
        pitch_points.append(
            "No website chat widget was detected. Treat this as a possible response-speed opportunity, not proof that the company misses leads."
        )
    if _bool(business, "emergency_service"):
        pitch_points.append(
            "Emergency/high-intent service language was detected. Fast intake and clear escalation may be valuable topics to discuss with the owner."
        )
    if _bool(business, "scheduling_mentioned"):
        pitch_points.append(
            "Appointment/scheduling language was detected. Ask how those requests are handled after a visitor expresses intent."
        )

    front_office_signal = (
        _bool(business, "emergency_service")
        or _bool(business, "scheduling_mentioned")
    ) and (
        not _bool(business, "estimate_form")
        or not _bool(business, "online_booking")
    )

    if front_office_signal:
        recommended_plan = "Front Office"
        plan_reason = (
            "The public site shows higher-intent service or scheduling signals plus an intake/booking gap. Lead with the website concept, then validate front-office workflow needs with the owner."
        )
    else:
        recommended_plan = "Website"
        plan_reason = (
            "The strongest evidence currently concerns the web experience. Start with the managed website offer and earn the right to discover deeper operational needs."
        )

    discovery_questions.extend(
        [
            "When someone submits a request or calls while you are busy, what happens next?",
            "How quickly do new inquiries usually receive a response?",
            "Who owns follow-up when an estimate has not been scheduled yet?",
            "Would you rather start with the website only or have inquiries organized in one place too?",
        ]
    )

    cautions.extend(
        [
            "Do not claim the company is losing revenue or missing calls without owner-confirmed or measured evidence.",
            "Do not present 'not detected' as proof a capability does not exist outside the inspected pages.",
        ]
    )

    return {
        "analysis": analysis,
        "recommended_plan": recommended_plan,
        "plan_reason": plan_reason,
        "pitch_points": pitch_points,
        "cautions": cautions,
        "discovery_questions": discovery_questions,
        "next_action": "Generate a private website concept and use it as the opening sales asset.",
        "complete_plan_note": "Business OS Complete remains a discovery-led upgrade; public website evidence alone is insufficient to recommend production receptionist, messaging or scheduling automation.",
    }
