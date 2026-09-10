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

def _hours_since(value):
    ts = _parse_datetime(value)
    if ts is None:
        return 0
    try:
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        seconds = (now - ts).total_seconds()
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

def _recommendation(status, priority, safety_flag, preferred_time):
    if priority == "Urgent" or safety_flag:
        return ("Urgent", "urgent", "Escalate to owner", safety_flag or "This lead was marked urgent.", 1000)
    if status == "New":
        reason = (f"Customer prefers {preferred_time} and has not been contacted yet." if preferred_time else "New opportunity has not been contacted yet.")
        return ("High", "high", "Contact lead", reason, 800)
    if status == "Contacted":
        reason = (f"Customer has been contacted and prefers {preferred_time}." if preferred_time else "Customer has been contacted but the opportunity is still open.")
        return ("Follow Up", "follow-up", "Continue follow-up", reason, 650)
    if status == "Estimate Scheduled":
        return ("Scheduled", "scheduled", "Review scheduled estimate", "An estimate is scheduled and the opportunity remains open.", 450)
    return ("Open", "open", "Review lead", "This opportunity is still open and should be reviewed.", 250)

def build_action_queue(leads, limit=8):
    queue = []
    for lead in leads:
        status = str(_value(lead, "status", "New")).strip()
        if status in CLOSED_STATUSES:
            continue
        priority = str(_value(lead, "priority", "Normal")).strip()
        safety_flag = str(_value(lead, "safety_flag", "")).strip()
        preferred_time = str(_value(lead, "preferred_time", "")).strip()
        last_activity = _value(lead, "last_activity_at", "") or _value(lead, "created_at", "")
        hours = _hours_since(last_activity)
        level, level_class, next_action, reason, base_score = _recommendation(status, priority, safety_flag, preferred_time)
        queue.append({
            "id": _value(lead, "id", 0),
            "caller_name": _value(lead, "caller_name", "") or "Unknown Caller",
            "service_type": _value(lead, "service_type", "") or "Service request",
            "status": status,
            "next_action": next_action,
            "reason": reason,
            "level": level,
            "level_class": level_class,
            "age_label": _age_label(hours),
            "score": base_score + min(hours, 240),
        })
    queue.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return queue[:limit]
