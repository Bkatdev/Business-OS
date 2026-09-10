"""Business OS v10.5 operator search.

Read-only, bounded search across core front-office records. This module does not
perform writes, merges, provider actions, or customer identity inference.
"""

MAX_QUERY_LENGTH = 120
PER_GROUP_LIMIT = 8


def _clean_query(raw):
    return " ".join((raw or "").strip().split())[:MAX_QUERY_LENGTH]


def _digits(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _like(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _phone_expr(column):
    return (
        f"replace(replace(replace(replace(replace(replace(COALESCE({column},''),"
        " '+', ''), '-', ''), '(', ''), ')', ''), ' ', ''), '.', '')"
    )


def _result(kind, title, subtitle, href, *, business_id=None, business_name="", meta=""):
    return {
        "kind": kind,
        "title": title or "Untitled record",
        "subtitle": subtitle or "",
        "href": href,
        "business_id": business_id,
        "business_name": business_name or "",
        "meta": meta or "",
    }


def search_operator_records(conn, raw_query, *, business_id=None, per_group=PER_GROUP_LIMIT):
    """Return grouped, bounded operator search results.

    ``business_id`` is an optional explicit scope for future tenant-aware
    operator views. Omitting it intentionally searches the local operator
    workspace. Search never mutates records or asserts customer identity.
    """
    query = _clean_query(raw_query)
    if len(query) < 2:
        return {"query": query, "groups": [], "total": 0, "too_short": bool(query)}

    try:
        limit = max(1, min(int(per_group), 20))
    except (TypeError, ValueError):
        limit = PER_GROUP_LIMIT

    text_like = _like(query.lower())
    digits = _digits(query)
    phone_like = _like(digits) if len(digits) >= 4 else None
    groups = []

    business_terms = [
        "lower(name) LIKE ? ESCAPE '\\'",
        "lower(city) LIKE ? ESCAPE '\\'",
        "lower(category) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(email,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(phone,'')) LIKE ? ESCAPE '\\'",
    ]
    params = [text_like] * len(business_terms)
    if phone_like:
        business_terms.append(f"{_phone_expr('phone')} LIKE ? ESCAPE '\\'")
        params.append(phone_like)
    where = "(" + " OR ".join(business_terms) + ")"
    if business_id is not None:
        where += " AND id = ?"
        params.append(business_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT id, name, city, category, phone, email, status, lifecycle_stage
        FROM businesses
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if rows:
        groups.append({
            "name": "Clients & businesses",
            "results": [
                _result(
                    "Business",
                    row["name"],
                    " · ".join(x for x in [row["city"], row["category"]] if x),
                    f"/client/{row['id']}" if (row["status"] == "Client" or row["lifecycle_stage"] in {"ONBOARDING", "ACTIVE"}) else f"/business/{row['id']}",
                    business_id=row["id"],
                    business_name=row["name"],
                    meta=row["phone"] or row["email"] or row["status"],
                )
                for row in rows
            ],
        })

    lead_terms = [
        "lower(COALESCE(l.caller_name,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.phone,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.address,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.service_type,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.issue_description,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(b.name,'')) LIKE ? ESCAPE '\\'",
    ]
    params = [text_like] * len(lead_terms)
    if phone_like:
        lead_terms.append(f"{_phone_expr('l.phone')} LIKE ? ESCAPE '\\'")
        params.append(phone_like)
    where = "(" + " OR ".join(lead_terms) + ")"
    if business_id is not None:
        where += " AND l.business_id = ?"
        params.append(business_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT l.id, l.business_id, l.caller_name, l.phone, l.service_type,
               l.status, l.priority, l.quarantine_status, b.name AS business_name
        FROM leads l
        LEFT JOIN businesses b ON b.id = l.business_id
        WHERE {where}
        ORDER BY l.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if rows:
        groups.append({
            "name": "Leads",
            "results": [
                _result(
                    "Lead",
                    row["caller_name"] or row["phone"] or f"Lead #{row['id']}",
                    " · ".join(x for x in [row["service_type"], row["status"]] if x),
                    f"/lead/{row['id']}",
                    business_id=row["business_id"],
                    business_name=row["business_name"],
                    meta="Quarantined" if row["quarantine_status"] == "Open" else row["priority"],
                )
                for row in rows
            ],
        })

    call_terms = [
        "lower(COALESCE(c.caller_phone,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(c.summary,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.caller_name,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(b.name,'')) LIKE ? ESCAPE '\\'",
    ]
    params = [text_like] * len(call_terms)
    if phone_like:
        call_terms.append(f"{_phone_expr('c.caller_phone')} LIKE ? ESCAPE '\\'")
        params.append(phone_like)
    where = "(" + " OR ".join(call_terms) + ")"
    if business_id is not None:
        where += " AND c.business_id = ?"
        params.append(business_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT c.id, c.business_id, c.lead_id, c.caller_phone, c.summary,
               c.call_status, c.created_at, l.caller_name, b.name AS business_name
        FROM calls c
        LEFT JOIN leads l ON l.id = c.lead_id
        LEFT JOIN businesses b ON b.id = c.business_id
        WHERE {where}
        ORDER BY c.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if rows:
        groups.append({
            "name": "Calls",
            "results": [
                _result(
                    "Call",
                    row["caller_name"] or row["caller_phone"] or f"Call #{row['id']}",
                    (row["summary"] or "No call summary")[:140],
                    f"/lead/{row['lead_id']}#customer-story" if row["lead_id"] else "/calls",
                    business_id=row["business_id"],
                    business_name=row["business_name"],
                    meta=" · ".join(x for x in [row["call_status"], row["created_at"]] if x),
                )
                for row in rows
            ],
        })

    appt_terms = [
        "lower(COALESCE(l.caller_name,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.phone,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(a.service_type,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(a.address,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(b.name,'')) LIKE ? ESCAPE '\\'",
    ]
    params = [text_like] * len(appt_terms)
    if phone_like:
        appt_terms.append(f"{_phone_expr('l.phone')} LIKE ? ESCAPE '\\'")
        params.append(phone_like)
    where = "(" + " OR ".join(appt_terms) + ")"
    if business_id is not None:
        where += " AND a.business_id = ?"
        params.append(business_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT a.id, a.business_id, a.lead_id, a.start_at, a.status,
               a.service_type, a.address, l.caller_name, l.phone,
               b.name AS business_name
        FROM appointments a
        LEFT JOIN leads l ON l.id = a.lead_id
        LEFT JOIN businesses b ON b.id = a.business_id
        WHERE {where}
        ORDER BY a.start_at DESC, a.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if rows:
        groups.append({
            "name": "Appointments",
            "results": [
                _result(
                    "Appointment",
                    row["caller_name"] or row["phone"] or f"Appointment #{row['id']}",
                    " · ".join(x for x in [row["service_type"], row["status"]] if x),
                    f"/lead/{row['lead_id']}#scheduling" if row["lead_id"] else "/schedule",
                    business_id=row["business_id"],
                    business_name=row["business_name"],
                    meta=row["start_at"],
                )
                for row in rows
            ],
        })

    message_terms = [
        "lower(COALESCE(m.recipient,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(m.body,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(l.caller_name,'')) LIKE ? ESCAPE '\\'",
        "lower(COALESCE(b.name,'')) LIKE ? ESCAPE '\\'",
    ]
    params = [text_like] * len(message_terms)
    if phone_like:
        message_terms.append(f"{_phone_expr('m.recipient')} LIKE ? ESCAPE '\\'")
        params.append(phone_like)
    where = "(" + " OR ".join(message_terms) + ")"
    if business_id is not None:
        where += " AND m.business_id = ?"
        params.append(business_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT m.id, m.business_id, m.lead_id, m.recipient, m.body, m.status,
               m.created_at, l.caller_name, b.name AS business_name
        FROM outbound_messages m
        LEFT JOIN leads l ON l.id = m.lead_id
        LEFT JOIN businesses b ON b.id = m.business_id
        WHERE {where}
        ORDER BY m.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if rows:
        groups.append({
            "name": "Messages",
            "results": [
                _result(
                    "Message",
                    row["caller_name"] or row["recipient"] or f"Message #{row['id']}",
                    (row["body"] or "")[:140],
                    f"/lead/{row['lead_id']}#customer-communication" if row["lead_id"] else "/automation",
                    business_id=row["business_id"],
                    business_name=row["business_name"],
                    meta=" · ".join(x for x in [row["status"], row["created_at"]] if x),
                )
                for row in rows
            ],
        })

    return {
        "query": query,
        "groups": groups,
        "total": sum(len(group["results"]) for group in groups),
        "too_short": False,
    }
