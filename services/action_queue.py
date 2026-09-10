from datetime import datetime

CLOSED_STATUSES = {"Won", "Lost"}


def _value(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = default
    return default if value is None else value


def _parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _now_for(timestamp=None):
    if timestamp is not None and timestamp.tzinfo is not None:
        return datetime.now(timestamp.tzinfo)
    return datetime.now()


def _hours_since(value):
    timestamp = _parse_datetime(value)
    if timestamp is None:
        return 0
    try:
        seconds = (_now_for(timestamp) - timestamp).total_seconds()
    except (TypeError, ValueError):
        return 0
    return max(0, int(seconds // 3600))


def _age_label(hours):
    if hours <= 0:
        return "Updated recently"
    if hours == 1:
        return "1 hour since activity"
    if hours < 24:
        return f"{hours} hours since activity"
    days = hours // 24
    return "1 day since activity" if days == 1 else f"{days} days since activity"


def _follow_up_state(value):
    due = _parse_datetime(value)
    if due is None:
        return {"has_due": False, "overdue": False, "label": ""}

    now = _now_for(due)
    delta_seconds = (due - now).total_seconds()

    if delta_seconds <= 0:
        overdue_hours = max(0, int(abs(delta_seconds) // 3600))
        if overdue_hours < 1:
            label = "Follow-up due now"
        elif overdue_hours < 24:
            label = f"Follow-up overdue by {overdue_hours}h"
        else:
            days = overdue_hours // 24
            label = f"Follow-up overdue by {days}d"
        return {"has_due": True, "overdue": True, "label": label}

    future_hours = int(delta_seconds // 3600)
    if future_hours < 1:
        label = "Follow-up due within an hour"
    elif future_hours < 24:
        label = f"Follow-up due in {future_hours}h"
    else:
        days = future_hours // 24
        label = f"Follow-up due in {days}d"
    return {"has_due": True, "overdue": False, "label": label}


def _recommendation(status, priority, safety_flag, preferred_time, follow_up):
    if priority == "Urgent" or safety_flag:
        return (
            "Urgent",
            "urgent",
            "Escalate to owner",
            safety_flag or "This lead was marked urgent.",
            1200,
        )

    if follow_up["overdue"]:
        return (
            "Overdue",
            "overdue",
            "Follow up now",
            follow_up["label"],
            1000,
        )

    if status == "New":
        reason = (
            f"Customer prefers {preferred_time} and has not been contacted yet."
            if preferred_time
            else "New opportunity has not been contacted yet."
        )
        return ("High", "high", "Contact lead", reason, 800)

    if status == "Contacted":
        if follow_up["has_due"]:
            reason = follow_up["label"]
        elif preferred_time:
            reason = f"Customer has been contacted and prefers {preferred_time}."
        else:
            reason = "Customer has been contacted but the opportunity is still open."
        return ("Follow Up", "follow-up", "Continue follow-up", reason, 650)

    if status == "Estimate Scheduled":
        return (
            "Scheduled",
            "scheduled",
            "Review scheduled estimate",
            follow_up["label"] or "An estimate is scheduled and the opportunity remains open.",
            450,
        )

    return (
        "Open",
        "open",
        "Review lead",
        "This opportunity is still open and should be reviewed.",
        250,
    )


def build_action_queue(leads, limit=8):
    queue = []

    for lead in leads:
        status = str(_value(lead, "status", "New")).strip()
        if status in CLOSED_STATUSES:
            continue

        priority = str(_value(lead, "priority", "Normal")).strip()
        safety_flag = str(_value(lead, "safety_flag", "")).strip()
        preferred_time = str(_value(lead, "preferred_time", "")).strip()
        next_follow_up_at = _value(lead, "next_follow_up_at", "")
        last_activity = (
            _value(lead, "last_activity_at", "")
            or _value(lead, "updated_at", "")
            or _value(lead, "created_at", "")
        )

        hours = _hours_since(last_activity)
        follow_up = _follow_up_state(next_follow_up_at)
        level, level_class, next_action, reason, base_score = _recommendation(
            status,
            priority,
            safety_flag,
            preferred_time,
            follow_up,
        )

        queue.append({
            "id": _value(lead, "id", 0),
            "caller_name": _value(lead, "caller_name", "") or "Unknown Caller",
            "service_type": _value(lead, "service_type", "") or "Service request",
            "status": status,
            "business_name": _value(lead, "business_name", "") or "",
            "next_action": next_action,
            "reason": reason,
            "level": level,
            "level_class": level_class,
            "age_label": _age_label(hours),
            "follow_up_label": follow_up["label"],
            "is_overdue": follow_up["overdue"],
            "score": base_score + min(hours, 240),
        })

    queue.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return queue[:limit]
