def triage_lead(
    priority="Normal",
    safety_flag="",
    preferred_time="",
    appointment_status="Not Scheduled",
):
    priority = (priority or "Normal").strip()
    safety_flag = (safety_flag or "").strip()
    preferred_time = (preferred_time or "").strip()
    appointment_status = (
        appointment_status or "Not Scheduled"
    ).strip()

    if priority == "Urgent" or safety_flag:
        return {
            "level": "Urgent",
            "next_action": "Escalate to owner",
            "reason": (
                safety_flag
                or "Lead was marked urgent."
            ),
        }

    if appointment_status == "Scheduled":
        return {
            "level": "Ready",
            "next_action": "Review scheduled estimate",
            "reason": "Customer already has an appointment.",
        }

    if preferred_time:
        return {
            "level": "Follow Up",
            "next_action": "Confirm estimate time",
            "reason": (
                f"Customer prefers {preferred_time}."
            ),
        }

    return {
        "level": "Follow Up",
        "next_action": "Contact lead",
        "reason": (
            "Lead needs a response and no appointment "
            "has been scheduled."
        ),
    }