from __future__ import annotations

import json
import re
from datetime import datetime

from services.db import connect, now_iso
from services.business_config import ensure_business_config_schema

CLOSED_STATUSES = {"Won", "Lost"}


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def ensure_front_office_schema(conn=None):
    own = conn is None
    conn = conn or connect()
    ensure_business_config_schema(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_service_links (
            lead_id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            link_method TEXT NOT NULL DEFAULT 'manual'
                CHECK(link_method IN ('manual','exact')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES business_services(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_service_links_business ON lead_service_links(business_id, service_id)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_intake_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES intake_questions(id) ON DELETE CASCADE,
            UNIQUE (lead_id, question_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_intake_answers_lead ON lead_intake_answers(lead_id, question_id)"
    )
    conn.commit()
    if own:
        conn.close()


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _lead_row(conn, lead_id):
    return conn.execute(
        """
        SELECT leads.*, businesses.name AS business_name,
               businesses.lifecycle_stage AS business_lifecycle_stage,
               businesses.automation_enabled AS business_automation_enabled
        FROM leads
        LEFT JOIN businesses ON businesses.id=leads.business_id
        WHERE leads.id=?
        """,
        (lead_id,),
    ).fetchone()


def _service_for_lead(conn, lead):
    if not lead or not lead["business_id"]:
        return None, "unassigned"

    stored = conn.execute(
        """
        SELECT bs.*
        FROM lead_service_links lsl
        JOIN business_services bs ON bs.id=lsl.service_id
        WHERE lsl.lead_id=? AND lsl.business_id=? AND bs.business_id=?
        """,
        (lead["id"], lead["business_id"], lead["business_id"]),
    ).fetchone()
    if stored:
        return stored, "linked"

    target = _normalized(lead["service_type"])
    if target:
        exact = conn.execute(
            "SELECT * FROM business_services WHERE business_id=? AND active=1 ORDER BY sort_order,id",
            (lead["business_id"],),
        ).fetchall()
        matches = [row for row in exact if _normalized(row["name"]) == target]
        if len(matches) == 1:
            return matches[0], "exact"
    return None, "unmatched"


def _questions_for_lead(conn, lead, service):
    if not lead or not lead["business_id"]:
        return []
    schema = conn.execute(
        """
        SELECT * FROM intake_schemas
        WHERE business_id=? AND status!='Archived'
        ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        (lead["business_id"],),
    ).fetchone()
    if not schema:
        return []

    args = [schema["id"]]
    service_clause = " AND q.service_id IS NULL"
    if service:
        service_clause = " AND (q.service_id IS NULL OR q.service_id=?)"
        args.append(service["id"])

    return conn.execute(
        f"""
        SELECT q.*, bs.name AS service_name
        FROM intake_questions q
        LEFT JOIN business_services bs ON bs.id=q.service_id
        WHERE q.schema_id=? AND q.active=1 {service_clause}
        ORDER BY q.sort_order, q.id
        """,
        args,
    ).fetchall()


def _answers_for_lead(conn, lead_id):
    rows = conn.execute(
        "SELECT * FROM lead_intake_answers WHERE lead_id=?",
        (lead_id,),
    ).fetchall()
    return {row["question_id"]: row for row in rows}


def _answer_present(question, answer):
    if not answer:
        return False
    text = (answer["answer_text"] or "").strip()
    if not text:
        return False
    qtype = question["question_type"]
    if qtype == "yes_no":
        return text.lower() in {"yes", "no"}
    if qtype == "choice":
        try:
            options = json.loads(question["options_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            options = []
        return not options or text in options
    return True


def lead_intelligence(conn, lead_id):
    ensure_front_office_schema(conn)
    lead = _lead_row(conn, lead_id)
    if not lead:
        return None

    service, service_match = _service_for_lead(conn, lead)
    questions = _questions_for_lead(conn, lead, service)
    answers = _answers_for_lead(conn, lead_id)

    required = [q for q in questions if q["required"]]
    missing_required = [q for q in required if not _answer_present(q, answers.get(q["id"]))]
    answered_count = sum(1 for q in questions if _answer_present(q, answers.get(q["id"])))
    completeness = 100 if not required else round(((len(required) - len(missing_required)) / len(required)) * 100)

    status = (lead["status"] or "New").strip()
    quarantine_open = (lead["quarantine_status"] or "") == "Open"
    has_configured_services = False
    if lead["business_id"]:
        has_configured_services = conn.execute(
            "SELECT 1 FROM business_services WHERE business_id=? AND active=1 LIMIT 1",
            (lead["business_id"],),
        ).fetchone() is not None

    if status in CLOSED_STATUSES:
        level, action, reason, action_class = (
            "Closed",
            "No active action",
            f"This lead is marked {status.lower()}.",
            "closed",
        )
    elif quarantine_open:
        level, action, reason, action_class = (
            "Blocked",
            "Resolve ownership / quarantine",
            lead["quarantine_reason"] or "This record is quarantined and automation must not proceed.",
            "blocked",
        )
    elif (lead["priority"] or "") == "Urgent" or (lead["safety_flag"] or "").strip():
        level, action, reason, action_class = (
            "Urgent",
            "Escalate to a person",
            (lead["safety_flag"] or "").strip() or "This lead was marked urgent.",
            "urgent",
        )
    elif not lead["business_id"]:
        level, action, reason, action_class = (
            "Review",
            "Assign a client",
            "Business OS cannot apply client-specific configuration until ownership is known.",
            "review",
        )
    elif has_configured_services and not service:
        level, action, reason, action_class = (
            "Needs context",
            "Confirm the requested service",
            "The request is not linked to a verified service in this client's catalog.",
            "context",
        )
    elif missing_required:
        first = ", ".join(q["label"] for q in missing_required[:2])
        suffix = "" if len(missing_required) <= 2 else f" +{len(missing_required)-2} more"
        level, action, reason, action_class = (
            "Needs info",
            "Collect required intake",
            f"Still needed: {first}{suffix}.",
            "context",
        )
    elif status == "Estimate Scheduled" or (lead["appointment_status"] or "") == "Scheduled":
        level, action, reason, action_class = (
            "Ready",
            "Review scheduled appointment",
            "Required intake is complete and an appointment is scheduled.",
            "ready",
        )
    elif status == "Contacted":
        level, action, reason, action_class = (
            "Follow up",
            "Continue follow-up",
            "The customer has been contacted and the opportunity is still open.",
            "follow-up",
        )
    elif (lead["preferred_time"] or "").strip():
        level, action, reason, action_class = (
            "Ready",
            "Confirm scheduling",
            f"Required intake is complete. Customer prefers {lead['preferred_time']}.",
            "ready",
        )
    else:
        level, action, reason, action_class = (
            "Ready",
            "Contact lead",
            "The request has enough configured context for the next human-controlled step.",
            "ready",
        )

    return {
        "lead": lead,
        "service": service,
        "service_match": service_match,
        "questions": questions,
        "answers": answers,
        "required_count": len(required),
        "answered_count": answered_count,
        "missing_required": missing_required,
        "completeness": completeness,
        "level": level,
        "next_action": action,
        "reason": reason,
        "action_class": action_class,
        "has_configured_services": has_configured_services,
    }


def link_lead_service(business_id, lead_id, service_id):
    conn = connect()
    ensure_front_office_schema(conn)
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND business_id=?", (lead_id, business_id)).fetchone()
    service = conn.execute(
        "SELECT * FROM business_services WHERE id=? AND business_id=? AND active=1",
        (service_id, business_id),
    ).fetchone()
    if not lead or not service:
        conn.close()
        return False, "The lead and service must belong to the same client."
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO lead_service_links(lead_id,business_id,service_id,link_method,created_at,updated_at)
        VALUES(?,?,?,'manual',?,?)
        ON CONFLICT(lead_id) DO UPDATE SET
            business_id=excluded.business_id,
            service_id=excluded.service_id,
            link_method='manual',
            updated_at=excluded.updated_at
        """,
        (lead_id, business_id, service_id, ts, ts),
    )
    conn.execute(
        "UPDATE leads SET service_type=?, updated_at=? WHERE id=? AND business_id=?",
        (service["name"], ts, lead_id, business_id),
    )
    conn.execute(
        """
        INSERT INTO lead_activities(lead_id,activity_type,title,details,created_at)
        VALUES(?, 'Context', 'Service confirmed', ?, ?)
        """,
        (lead_id, service["name"], ts),
    )
    conn.commit()
    conn.close()
    return True, "Structured service linked. No external action was taken."


def save_intake_answer(business_id, lead_id, question_id, answer_text):
    answer_text = (answer_text or "").strip()
    conn = connect()
    ensure_front_office_schema(conn)
    lead = conn.execute("SELECT * FROM leads WHERE id=? AND business_id=?", (lead_id, business_id)).fetchone()
    question = conn.execute(
        """
        SELECT q.* FROM intake_questions q
        JOIN intake_schemas s ON s.id=q.schema_id
        WHERE q.id=? AND s.business_id=? AND q.active=1
        """,
        (question_id, business_id),
    ).fetchone()
    if not lead or not question:
        conn.close()
        return False, "The lead and intake question must belong to the same client."

    qtype = question["question_type"]
    if qtype == "yes_no" and answer_text.lower() not in {"yes", "no"}:
        conn.close()
        return False, "Yes/No questions only accept Yes or No."
    if qtype == "choice":
        try:
            options = json.loads(question["options_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            options = []
        if options and answer_text not in options:
            conn.close()
            return False, "Select one of the configured choices."
    if question["required"] and not answer_text:
        conn.close()
        return False, "This required answer cannot be blank."
    if len(answer_text) > 2000:
        conn.close()
        return False, "Intake answers are limited to 2,000 characters."

    ts = now_iso()
    conn.execute(
        """
        INSERT INTO lead_intake_answers(lead_id,business_id,question_id,answer_text,created_at,updated_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(lead_id,question_id) DO UPDATE SET
            answer_text=excluded.answer_text,
            updated_at=excluded.updated_at
        """,
        (lead_id, business_id, question_id, answer_text, ts, ts),
    )
    conn.execute(
        """
        INSERT INTO lead_activities(lead_id,activity_type,title,details,created_at)
        VALUES(?, 'Intake', 'Intake answer updated', ?, ?)
        """,
        (lead_id, question["label"], ts),
    )
    conn.commit()
    conn.close()
    return True, "Intake answer saved. No external action was taken."


def unified_timeline(conn, lead_id, limit=40):
    ensure_front_office_schema(conn)
    events = []

    for row in conn.execute(
        "SELECT * FROM lead_activities WHERE lead_id=? ORDER BY id DESC LIMIT 50", (lead_id,)
    ).fetchall():
        events.append({
            "time": row["created_at"], "kind": row["activity_type"],
            "title": row["title"], "detail": row["details"] or "",
        })

    for row in conn.execute(
        "SELECT * FROM calls WHERE lead_id=? ORDER BY id DESC LIMIT 20", (lead_id,)
    ).fetchall():
        events.append({
            "time": row["created_at"], "kind": "Call", "title": "Call captured",
            "detail": row["summary"] or f"{row['duration_seconds']} second call",
        })

    for row in conn.execute(
        "SELECT * FROM appointments WHERE lead_id=? ORDER BY id DESC LIMIT 20", (lead_id,)
    ).fetchall():
        events.append({
            "time": row["updated_at"] or row["created_at"], "kind": "Appointment",
            "title": f"Appointment {row['status'].lower()}", "detail": row["start_at"],
        })

    for row in conn.execute(
        "SELECT * FROM outbound_messages WHERE lead_id=? ORDER BY id DESC LIMIT 20", (lead_id,)
    ).fetchall():
        events.append({
            "time": row["sent_at"] or row["approved_at"] or row["created_at"],
            "kind": "Message", "title": f"SMS {row['status'].lower()}",
            "detail": row["body"],
        })

    for row in conn.execute(
        """
        SELECT a.*, q.label FROM lead_intake_answers a
        JOIN intake_questions q ON q.id=a.question_id
        WHERE a.lead_id=? ORDER BY a.id DESC LIMIT 30
        """,
        (lead_id,),
    ).fetchall():
        events.append({
            "time": row["updated_at"], "kind": "Intake", "title": row["label"],
            "detail": row["answer_text"],
        })

    def parse_time(event):
        text = event.get("time") or ""
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min

    # De-duplicate activity records that mirror richer source records imperfectly by title/time.
    seen = set()
    unique = []
    for event in sorted(events, key=parse_time, reverse=True):
        key = (event["time"], event["kind"], event["title"], event["detail"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique[:limit]


def build_front_office_queue(conn, leads, limit=8):
    queue = []
    rank = {"Urgent": 1200, "Blocked": 1100, "Needs info": 900, "Needs context": 850,
            "Review": 800, "Follow up": 650, "Ready": 450, "Closed": 0}
    for lead in leads:
        intel = lead_intelligence(conn, lead["id"])
        if not intel or (lead["status"] or "") in CLOSED_STATUSES:
            continue
        queue.append({
            "id": lead["id"],
            "caller_name": lead["caller_name"] or "Unknown Caller",
            "service_type": (intel["service"]["name"] if intel["service"] else (lead["service_type"] or "Service request")),
            "status": lead["status"],
            "business_name": lead["business_name"] or "",
            "next_action": intel["next_action"],
            "reason": intel["reason"],
            "level": intel["level"],
            "level_class": intel["action_class"],
            "age_label": "Configuration-aware recommendation",
            "score": rank.get(intel["level"], 300) + int(lead["id"] or 0),
        })
    queue.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return queue[:limit]
