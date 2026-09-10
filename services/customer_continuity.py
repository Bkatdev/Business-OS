"""Business OS v10.5 deterministic customer continuity.

Continuity is read-only and deliberately conservative: records are related only
when they share the same proven business owner and the exact same normalized
phone number. Nothing is merged or rewritten.
"""


def normalize_phone(value):
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def customer_continuity(conn, lead_id, *, event_limit=12):
    lead = conn.execute(
        "SELECT id,business_id,caller_name,phone FROM leads WHERE id=?",
        (lead_id,),
    ).fetchone()
    if not lead or not lead["business_id"]:
        return {"available": False, "reason": "No proven client owner.", "related_leads": [], "events": []}

    normalized = normalize_phone(lead["phone"])
    if len(normalized) < 7:
        return {"available": False, "reason": "No reliable phone identifier.", "related_leads": [], "events": []}

    candidates = conn.execute(
        """
        SELECT id,business_id,caller_name,phone,service_type,status,created_at,
               quarantine_status
        FROM leads
        WHERE business_id=? AND TRIM(COALESCE(phone,'')) != ''
        ORDER BY id DESC
        LIMIT 500
        """,
        (lead["business_id"],),
    ).fetchall()
    related = [row for row in candidates if normalize_phone(row["phone"]) == normalized]
    lead_ids = [row["id"] for row in related]

    if not lead_ids:
        return {"available": True, "normalized_phone": normalized, "related_leads": [], "events": [], "counts": {}}

    placeholders = ",".join("?" for _ in lead_ids)
    events = []

    for row in conn.execute(
        f"SELECT id,lead_id,summary,call_status,created_at FROM calls WHERE business_id=? AND lead_id IN ({placeholders}) ORDER BY id DESC LIMIT 30",
        [lead["business_id"], *lead_ids],
    ).fetchall():
        events.append({"time": row["created_at"], "kind": "Call", "title": row["call_status"] or "Call", "detail": row["summary"] or "Call captured", "lead_id": row["lead_id"]})

    for row in conn.execute(
        f"SELECT id,lead_id,start_at,status,service_type,updated_at,created_at FROM appointments WHERE business_id=? AND lead_id IN ({placeholders}) ORDER BY id DESC LIMIT 30",
        [lead["business_id"], *lead_ids],
    ).fetchall():
        events.append({"time": row["updated_at"] or row["created_at"], "kind": "Appointment", "title": f"Appointment {str(row['status'] or '').lower()}", "detail": " · ".join(x for x in [row["service_type"], row["start_at"]] if x), "lead_id": row["lead_id"]})

    for row in conn.execute(
        f"SELECT id,lead_id,status,body,sent_at,approved_at,created_at FROM outbound_messages WHERE business_id=? AND lead_id IN ({placeholders}) ORDER BY id DESC LIMIT 30",
        [lead["business_id"], *lead_ids],
    ).fetchall():
        events.append({"time": row["sent_at"] or row["approved_at"] or row["created_at"], "kind": "Message", "title": row["status"] or "Message", "detail": (row["body"] or "")[:180], "lead_id": row["lead_id"]})

    for row in related:
        if row["id"] != lead_id:
            events.append({"time": row["created_at"], "kind": "Lead", "title": row["status"] or "Lead", "detail": row["service_type"] or "Related inquiry", "lead_id": row["id"]})

    # ISO timestamps used by the app sort lexically; keep empty timestamps last.
    events.sort(key=lambda item: item["time"] or "", reverse=True)
    events = events[:max(1, min(int(event_limit), 30))]

    return {
        "available": True,
        "normalized_phone": normalized,
        "related_leads": related,
        "other_leads": [row for row in related if row["id"] != lead_id],
        "events": events,
        "counts": {
            "leads": len(related),
            "calls": conn.execute(f"SELECT COUNT(*) FROM calls WHERE business_id=? AND lead_id IN ({placeholders})", [lead["business_id"], *lead_ids]).fetchone()[0],
            "appointments": conn.execute(f"SELECT COUNT(*) FROM appointments WHERE business_id=? AND lead_id IN ({placeholders})", [lead["business_id"], *lead_ids]).fetchone()[0],
            "messages": conn.execute(f"SELECT COUNT(*) FROM outbound_messages WHERE business_id=? AND lead_id IN ({placeholders})", [lead["business_id"], *lead_ids]).fetchone()[0],
        },
    }
