from datetime import datetime, timedelta


def parse_local(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def human_datetime(value):
    dt = parse_local(value)
    if not dt:
        return str(value or "")
    return f"{dt.strftime('%a, %b')} {dt.day} at {dt.strftime('%I:%M %p').lstrip('0')}"


def end_from_duration(start_at, duration_minutes):
    start = parse_local(start_at)
    if not start:
        return ""
    try:
        minutes = max(15, min(int(duration_minutes or 60), 480))
    except (TypeError, ValueError):
        minutes = 60
    return (start + timedelta(minutes=minutes)).isoformat(timespec="minutes")


def suggested_follow_up(lead):
    name = str(lead["caller_name"] or "there").strip()
    service = str(lead["service_type"] or "your service request").strip()
    preferred = str(lead["preferred_time"] or "").strip()
    business = str(lead["business_name"] or "our team").strip()

    first_name = name.split()[0] if name and name != "Unknown Caller" else "there"
    text = (
        f"Hi {first_name}, this is {business}. Thanks for reaching out about "
        f"{service.lower()}. We wanted to follow up and help get your estimate scheduled."
    )
    if preferred:
        text += f" We saw that {preferred} works well for you."
    text += " Reply here and we’ll confirm the next available time."
    return text


def appointment_state(rows):
    now = datetime.now()
    upcoming = []
    past = []
    today = []

    for raw in rows:
        item = dict(raw)
        start = parse_local(item.get("start_at"))
        if not start:
            past.append(item)
            continue
        item["start_dt"] = start
        item["display_date"] = start.strftime("%a, %b %d")
        item["display_time"] = start.strftime("%I:%M %p").lstrip("0")
        if start.date() == now.date() and item.get("status") == "Scheduled":
            today.append(item)
        if start >= now and item.get("status") == "Scheduled":
            upcoming.append(item)
        else:
            past.append(item)

    upcoming.sort(key=lambda item: item.get("start_at", ""))
    today.sort(key=lambda item: item.get("start_at", ""))
    past.sort(key=lambda item: item.get("start_at", ""), reverse=True)
    return {"upcoming": upcoming, "today": today, "past": past}
