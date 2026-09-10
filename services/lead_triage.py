def triage_lead(
    priority="Normal",
    safety_flag="",
    preferred_time="",
    appointment_status="Not Scheduled",
    lead_status="New",
):
    priority = (
        priority or "Normal"
    ).strip()

    safety_flag = (
        safety_flag or ""
    ).strip()

    preferred_time = (
        preferred_time or ""
    ).strip()

    appointment_status = (
        appointment_status
        or "Not Scheduled"
    ).strip()

    lead_status = (
        lead_status or "New"
    ).strip()


    # Closed leads should never receive
    # active follow-up recommendations.

    if lead_status == "Won":
        return {
            "level": "Won",
            "next_action": "No follow-up required",
            "reason": (
                "This opportunity has been "
                "marked as won."
            ),
        }


    if lead_status == "Lost":
        return {
            "level": "Closed",
            "next_action": "No active follow-up",
            "reason": (
                "This opportunity has been "
                "marked as lost."
            ),
        }


    # Safety always takes precedence
    # for active opportunities.

    if priority == "Urgent" or safety_flag:
        return {
            "level": "Urgent",
            "next_action": "Escalate to owner",
            "reason": (
                safety_flag
                or "Lead was marked urgent."
            ),
        }


    if (
        lead_status == "Estimate Scheduled"
        or appointment_status == "Scheduled"
    ):
        return {
            "level": "Ready",
            "next_action": "Review scheduled estimate",
            "reason": (
                "Customer has an estimate "
                "scheduled."
            ),
        }


    if lead_status == "Contacted":
        return {
            "level": "Follow Up",
            "next_action": "Continue follow-up",
            "reason": (
                "Customer has been contacted "
                "but the opportunity is still open."
            ),
        }


    if preferred_time:
        return {
            "level": "Follow Up",
            "next_action": "Confirm estimate time",
            "reason": (
                f"Customer prefers "
                f"{preferred_time}."
            ),
        }


    return {
        "level": "Follow Up",
        "next_action": "Contact lead",
        "reason": (
            "Lead needs a response and no "
            "appointment has been scheduled."
        ),
    }
