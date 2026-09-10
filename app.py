import csv
import io
import json

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.db import connect, init_db, now_iso
from services.prospect_finder import discover
from services.scoring import opportunity_analysis
from services.website_auditor import audit_batch, audit_business_by_id
from services.lead_triage import triage_lead
from services.operations import appointment_state, end_from_duration, suggested_follow_up
from services.automation_engine import execute_sms

app = Flask(__name__)
app.secret_key = "business-os-local-v2"


STATUSES = [
    "Not Contacted",
    "Researching",
    "Qualified",
    "Contacted",
    "Demo",
    "Proposal",
    "Client",
    "Lost",
]


def analyze(business):
    return opportunity_analysis(business)


def businesses_with_analysis(rows):
    results = []

    for row in rows:
        business = dict(row)
        business["analysis"] = analyze(row)
        results.append(business)

    return results


@app.context_processor
def inject_global_counts():
    conn = connect()

    prospect_count = conn.execute(
        "SELECT COUNT(*) FROM businesses"
    ).fetchone()[0]

    pending_approvals = conn.execute(
        """
        SELECT COUNT(*)
        FROM approvals
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    conn.close()

    return {
        "global_prospect_count": prospect_count,
        "global_pending_approvals": pending_approvals,
    }


@app.route("/")
def dashboard():
    from services.action_queue import build_action_queue

    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    clients = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE status = 'Client'
        """
    ).fetchone()[0]

    audited = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE audit_status = 'completed'
        """
    ).fetchone()[0]

    google_prospects = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE source = 'google_places'
        """
    ).fetchone()[0]

    pending_approvals = conn.execute(
        """
        SELECT COUNT(*)
        FROM approvals
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    total_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        """
    ).fetchone()[0]

    new_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'New'
        """
    ).fetchone()[0]

    urgent_leads_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE priority = 'Urgent'
          AND status NOT IN ('Won', 'Lost')
        """
    ).fetchone()[0]

    needs_follow_up = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status IN ('New', 'Contacted')
          AND appointment_status != 'Scheduled'
        """
    ).fetchone()[0]

    contacted_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Contacted'
        """
    ).fetchone()[0]

    scheduled_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Estimate Scheduled'
        """
    ).fetchone()[0]

    won_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Won'
        """
    ).fetchone()[0]

    lost_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Lost'
        """
    ).fetchone()[0]

    recent_leads = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        ORDER BY leads.id DESC
        LIMIT 6
        """
    ).fetchall()

    urgent_leads = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        WHERE leads.priority = 'Urgent'
          AND leads.status NOT IN ('Won', 'Lost')
        ORDER BY leads.id DESC
        LIMIT 4
        """
    ).fetchall()

    action_queue_rows = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name,
            (
                SELECT MAX(lead_activities.created_at)
                FROM lead_activities
                WHERE lead_activities.lead_id = leads.id
            ) AS last_activity_at
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        WHERE leads.status NOT IN ('Won', 'Lost')
        ORDER BY leads.id DESC
        """
    ).fetchall()

    today_appointments = conn.execute(
        """
        SELECT COUNT(*)
        FROM appointments
        WHERE status = 'Scheduled'
          AND date(start_at) = date('now', 'localtime')
        """
    ).fetchone()[0]

    pending_messages = conn.execute(
        """
        SELECT COUNT(*)
        FROM outbound_messages
        WHERE status = 'Pending Approval'
        """
    ).fetchone()[0]

    conn.close()

    businesses = businesses_with_analysis(rows)

    high_opportunity = sum(
        1
        for business in businesses
        if business["analysis"]["level"] == "High"
    )

    closed_leads = (
        won_leads + lost_leads
    )

    if closed_leads:
        conversion_rate = round(
            (won_leads / closed_leads) * 100
        )
    else:
        conversion_rate = 0

    pipeline = [
        {
            "name": "New",
            "count": new_leads,
        },
        {
            "name": "Contacted",
            "count": contacted_leads,
        },
        {
            "name": "Estimate Scheduled",
            "count": scheduled_leads,
        },
        {
            "name": "Won",
            "count": won_leads,
        },
    ]

    pipeline_max = max(
        [
            stage["count"]
            for stage in pipeline
        ]
        + [1]
    )

    action_queue_total = len(action_queue_rows)
    action_queue = build_action_queue(action_queue_rows, limit=8)
    top_action = action_queue[0] if action_queue else None

    return render_template(
        "dashboard.html",
        businesses=businesses[:8],
        total=len(businesses),
        high=high_opportunity,
        clients=clients,
        audited=audited,
        discovered=google_prospects,
        pending=pending_approvals,
        total_leads=total_leads,
        new_leads=new_leads,
        urgent_leads_count=urgent_leads_count,
        needs_follow_up=needs_follow_up,
        scheduled_leads=scheduled_leads,
        won_leads=won_leads,
        conversion_rate=conversion_rate,
        recent_leads=recent_leads,
        urgent_leads=urgent_leads,
        action_queue=action_queue,
        action_queue_total=action_queue_total,
        top_action=top_action,
        today_appointments=today_appointments,
        pending_messages=pending_messages,
        pipeline=pipeline,
        pipeline_max=pipeline_max,
    )


@app.route("/prospects")
def prospects():
    search = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    status = request.args.get("status", "").strip()
    audit = request.args.get("audit", "").strip()

    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    if search:
        search_lower = search.lower()

        businesses = [
            business
            for business in businesses
            if search_lower in (business["name"] or "").lower()
            or search_lower in (business["city"] or "").lower()
            or search_lower in (business["category"] or "").lower()
        ]

    if level:
        businesses = [
            business
            for business in businesses
            if business["analysis"]["level"] == level
        ]

    if status:
        businesses = [
            business
            for business in businesses
            if business["status"] == status
        ]

    if audit:
        businesses = [
            business
            for business in businesses
            if business["audit_status"] == audit
        ]

    return render_template(
        "prospects.html",
        businesses=businesses,
        q=search,
        level=level,
        status=status,
        audit=audit,
        statuses=STATUSES,
        pipeline_statuses=STATUSES,
    )


@app.route("/prospects/discover", methods=["POST"])
def discover_prospects():
    query = request.form.get("query", "").strip()
    category = request.form.get(
        "category",
        "Local Service Business",
    ).strip()

    page_size = request.form.get("page_size", "10")

    if not query:
        flash(
            "Enter a business search first.",
            "error",
        )
        return redirect(url_for("prospects"))

    try:
        result = discover(
            query,
            page_size,
            category,
        )

        flash(
            f"Google returned {result['returned']} businesses. "
            f"Added {len(result['added'])}. "
            f"Skipped {len(result['skipped'])} duplicates.",
            "success",
        )

    except Exception as exc:
        flash(
            f"Prospect discovery failed: {exc}",
            "error",
        )

    return redirect(url_for("prospects"))


@app.route("/prospects/add", methods=["POST"])
def add_prospect():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()

    if not name or not city:
        flash(
            "Business name and city are required.",
            "error",
        )
        return redirect(url_for("prospects"))

    conn = connect()

    conn.execute(
        """
        INSERT INTO businesses (
            name,
            city,
            category,
            reviews,
            rating,
            website,
            phone,
            email,
            online_booking,
            emergency_service,
            website_chat,
            estimate_form,
            status,
            notes,
            created_at,
            source,
            audit_status
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            0, 0, 0, 0,
            'Not Contacted',
            '',
            ?,
            'manual',
            'not_audited'
        )
        """,
        (
            name,
            city,
            request.form.get(
                "category",
                "Local Service Business",
            ).strip(),
            int(request.form.get("reviews") or 0),
            float(request.form.get("rating") or 0),
            request.form.get("website", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("email", "").strip(),
            now_iso(),
        ),
    )

    conn.commit()
    conn.close()

    flash(
        f"{name} was added.",
        "success",
    )

    return redirect(url_for("prospects"))


@app.route("/business/<int:bid>")
def business_detail(bid):
    conn = connect()

    business = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE id = ?
        """,
        (bid,),
    ).fetchone()

    approvals = conn.execute(
        """
        SELECT *
        FROM approvals
        WHERE business_id = ?
        ORDER BY id DESC
        """,
        (bid,),
    ).fetchall()

    conn.close()

    if business is None:
        return render_template("404.html"), 404

    evidence = {}

    raw_evidence = business["audit_evidence"]

    if raw_evidence:
        try:
            evidence = json.loads(raw_evidence)

        except json.JSONDecodeError:
            evidence = {
                "raw": raw_evidence
            }

    return render_template(
        "business_detail.html",
        business=dict(business),
        analysis=analyze(business),
        evidence=evidence,
        approvals=approvals,
        statuses=STATUSES,
        pipeline_statuses=STATUSES,
    )


@app.route(
    "/business/<int:bid>/audit",
    methods=["POST"],
)
def audit_one(bid):
    try:
        result = audit_business_by_id(bid)

        if result["ok"]:
            flash(
                "Website audit completed successfully.",
                "success",
            )

        else:
            flash(
                "Website audit could not fully complete: "
                + result.get(
                    "message",
                    result.get(
                        "status",
                        "Unknown error",
                    ),
                ),
                "error",
            )

    except Exception as exc:
        flash(
            f"Website audit failed: {exc}",
            "error",
        )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route(
    "/business/<int:bid>/status",
    methods=["POST"],
)
def update_status(bid):
    status = request.form.get(
        "status",
        "Not Contacted",
    )

    if status not in STATUSES:
        status = "Not Contacted"

    conn = connect()

    conn.execute(
        """
        UPDATE businesses
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            bid,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        "Pipeline status updated.",
        "success",
    )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route(
    "/business/<int:bid>/notes",
    methods=["POST"],
)
def update_notes(bid):
    notes = request.form.get(
        "notes",
        "",
    )

    conn = connect()

    conn.execute(
        """
        UPDATE businesses
        SET notes = ?
        WHERE id = ?
        """,
        (
            notes,
            bid,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        "Notes saved.",
        "success",
    )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route("/audits")
def audits():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    return render_template(
        "audits.html",
        businesses=businesses,
    )


@app.route(
    "/audits/run",
    methods=["POST"],
)
def run_audits():
    mode = request.form.get(
        "mode",
        "not_audited",
    )

    try:
        results = audit_batch(
            mode=mode,
            limit=25,
        )

        completed = sum(
            1
            for _, _, result in results
            if result["ok"]
        )

        failed = len(results) - completed

        flash(
            f"Audit finished. "
            f"{completed} completed. "
            f"{failed} could not complete.",
            "success",
        )

    except Exception as exc:
        flash(
            f"Audit run failed: {exc}",
            "error",
        )

    return redirect(
        url_for("audits")
    )


@app.route("/agents")
def agents():
    return render_template(
        "agents.html"
    )


@app.route("/approvals")
def approvals():
    conn = connect()

    rows = conn.execute(
        """
        SELECT
            approvals.*,
            businesses.name AS business_name
        FROM approvals
        LEFT JOIN businesses
            ON businesses.id = approvals.business_id
        ORDER BY approvals.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "approvals.html",
        approvals=rows,
    )


@app.route(
    "/approvals/<int:approval_id>/<action>",
    methods=["POST"],
)
def approval_action(
    approval_id,
    action,
):
    if action == "approve":
        status = "Approved"
    else:
        status = "Rejected"

    conn = connect()

    conn.execute(
        """
        UPDATE approvals
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            approval_id,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        f"Approval marked {status.lower()}.",
        "success",
    )

    return redirect(
        url_for("approvals")
    )



def _normalize_phone(value):
    return "".join(
        character
        for character in str(value or "")
        if character.isdigit()
    )


def _resolve_retell_business(conn, agent_id):
    agent_id = str(agent_id or "").strip()

    if agent_id:
        mapped = conn.execute(
            """
            SELECT id
            FROM businesses
            WHERE status = 'Client'
              AND retell_agent_id = ?
            LIMIT 1
            """,
            (agent_id,),
        ).fetchone()

        if mapped:
            return mapped["id"]

    clients = conn.execute(
        """
        SELECT id
        FROM businesses
        WHERE status = 'Client'
        ORDER BY id DESC
        LIMIT 2
        """
    ).fetchall()

    if len(clients) == 1:
        return clients[0]["id"]

    return None


@app.route("/webhooks/retell", methods=["POST"])
def retell_webhook():
    data = request.get_json(silent=True) or {}

    event = str(data.get("event", "") or "")

    # We only want the finished post-call analysis.
    if event and event != "call_analyzed":
        return {
            "ok": True,
            "ignored": True,
            "event": event,
        }, 200

    call = data.get("call") or {}

    if not isinstance(call, dict):
        return {
            "ok": False,
            "error": "Invalid call payload",
        }, 400

    retell_call_id = str(
        call.get("call_id", "") or ""
    ).strip()

    retell_agent_id = str(
        call.get("agent_id", "") or ""
    ).strip()

    caller_phone = str(
        call.get("from_number", "") or ""
    ).strip()

    extracted_phone = ""

    transcript = str(
        call.get("transcript", "") or ""
    )

    # Retell supplies duration in milliseconds.
    duration_ms = call.get("duration_ms")

    try:
        duration_seconds = int(
            int(duration_ms or 0) / 1000
        )
    except (TypeError, ValueError):
        duration_seconds = 0

    # Fallback in case duration_ms is missing.
    if duration_seconds <= 0:
        try:
            start_timestamp = int(
                call.get("start_timestamp") or 0
            )
            end_timestamp = int(
                call.get("end_timestamp") or 0
            )

            if (
                start_timestamp > 0
                and end_timestamp > start_timestamp
            ):
                duration_seconds = int(
                    (end_timestamp - start_timestamp)
                    / 1000
                )

        except (TypeError, ValueError):
            duration_seconds = 0

    call_analysis = call.get("call_analysis") or {}

    if not isinstance(call_analysis, dict):
        call_analysis = {}

    summary = str(
        call_analysis.get("call_summary", "") or ""
    )

    custom = (
        call_analysis.get("custom_analysis_data")
        or {}
    )

    if not isinstance(custom, dict):
        custom = {}

    caller_name = str(
        custom.get("caller_name", "") or ""
    ).strip()

    address = str(
        custom.get("address", "") or ""
    ).strip()

    service_type = str(
        custom.get("service_type", "") or ""
    ).strip()

    issue_description = str(
        custom.get("issue_description", "") or ""
    ).strip()

    preferred_time = str(
        custom.get("preferred_time", "") or ""
    ).strip()

    extracted_phone = str(
        custom.get("caller_phone", "") or ""
    ).strip()

    if extracted_phone:
        caller_phone = extracted_phone

    safety_flag = str(
        custom.get("safety_flag", "") or ""
    ).strip()

    priority = str(
        custom.get("priority", "Normal") or "Normal"
    ).strip()

    if priority not in ["Urgent", "Normal"]:
        priority = "Normal"

    appointment_confirmed = (
        custom.get("appointment_confirmed") is True
    )

    if appointment_confirmed:
        appointment_status = "Scheduled"
    else:
        appointment_status = "Not Scheduled"

    # For now every inbound receptionist record is
    # stored as a new lead. We can classify this more
    # intelligently later.
    lead_type = "New Lead"

    conn = connect()

    # Retell can retry webhooks. Prevent duplicate calls.
    existing_call = None

    if retell_call_id:
        existing_call = conn.execute(
            """
            SELECT id, lead_id
            FROM calls
            WHERE retell_call_id = ?
            LIMIT 1
            """,
            (retell_call_id,),
        ).fetchone()

    if existing_call:
        conn.close()
        return {
            "ok": True,
            "duplicate": True,
            "call_id": existing_call["id"],
            "lead_id": existing_call["lead_id"],
        }, 200

    business_id = _resolve_retell_business(
        conn,
        retell_agent_id,
    )

    # A repeat call from the same phone number should attach to the
    # existing open opportunity instead of creating CRM clutter.
    duplicate_lead = None
    normalized_phone = _normalize_phone(caller_phone)

    if business_id and normalized_phone:
        candidates = conn.execute(
            """
            SELECT *
            FROM leads
            WHERE business_id = ?
              AND status NOT IN ('Won', 'Lost')
            ORDER BY id DESC
            LIMIT 50
            """,
            (business_id,),
        ).fetchall()

        for candidate in candidates:
            if _normalize_phone(candidate["phone"]) == normalized_phone:
                duplicate_lead = candidate
                break

    timestamp = now_iso()

    if duplicate_lead:
        lead_id = duplicate_lead["id"]

        merged_priority = (
            "Urgent"
            if priority == "Urgent" or duplicate_lead["priority"] == "Urgent"
            else "Normal"
        )

        conn.execute(
            """
            UPDATE leads
            SET caller_name = CASE WHEN caller_name = '' THEN ? ELSE caller_name END,
                address = CASE WHEN address = '' THEN ? ELSE address END,
                service_type = CASE WHEN service_type = '' THEN ? ELSE service_type END,
                issue_description = CASE WHEN issue_description = '' THEN ? ELSE issue_description END,
                preferred_time = CASE WHEN ? != '' THEN ? ELSE preferred_time END,
                safety_flag = CASE WHEN ? != '' THEN ? ELSE safety_flag END,
                priority = ?,
                retell_call_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                caller_name,
                address,
                service_type,
                issue_description,
                preferred_time,
                preferred_time,
                safety_flag,
                safety_flag,
                merged_priority,
                retell_call_id,
                timestamp,
                lead_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (?, 'Call', 'Repeat inquiry received', ?, ?)
            """,
            (
                lead_id,
                "Another inbound call was attached to this open lead.",
                timestamp,
            ),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO leads (
                business_id,
                caller_name,
                phone,
                address,
                service_type,
                issue_description,
                lead_type,
                priority,
                safety_flag,
                preferred_time,
                appointment_status,
                status,
                source,
                retell_call_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_id,
                caller_name,
                caller_phone,
                address,
                service_type,
                issue_description,
                lead_type,
                priority,
                safety_flag,
                preferred_time,
                appointment_status,
                "New",
                "AI Receptionist",
                retell_call_id,
                timestamp,
                timestamp,
            ),
        )
        lead_id = cursor.lastrowid

    cursor = conn.execute(
        """
        INSERT INTO calls (
            business_id,
            lead_id,
            retell_call_id,
            caller_phone,
            duration_seconds,
            summary,
            transcript,
            call_status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            lead_id,
            retell_call_id,
            caller_phone,
            duration_seconds,
            summary,
            transcript,
            "Completed",
            timestamp,
        ),
    )

    call_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "duplicate": False,
        "duplicate_lead": bool(duplicate_lead),
        "lead_id": lead_id,
        "call_id": call_id,
        "business_id": business_id,
    }, 201


@app.route("/leads")


def leads():
    conn = connect()

    rows = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        ORDER BY leads.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "leads.html",
        leads=rows,
    )

@app.route("/lead/<int:lead_id>")
def lead_detail(lead_id):
    conn = connect()

    lead = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        WHERE leads.id = ?
        """,
        (lead_id,),
    ).fetchone()

    if lead is None:
        conn.close()
        return render_template("404.html"), 404

    call = conn.execute(
        """
        SELECT *
        FROM calls
        WHERE lead_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (lead_id,),
    ).fetchone()

    activities = conn.execute(
        """
        SELECT *
        FROM lead_activities
        WHERE lead_id = ?
        ORDER BY id DESC
        """,
        (lead_id,),
    ).fetchall()

    notes = conn.execute(
        """
        SELECT *
        FROM lead_notes
        WHERE lead_id = ?
        ORDER BY id DESC
        """,
        (lead_id,),
    ).fetchall()

    appointments = conn.execute(
        """
        SELECT *
        FROM appointments
        WHERE lead_id = ?
        ORDER BY start_at DESC, id DESC
        """,
        (lead_id,),
    ).fetchall()

    messages = conn.execute(
        """
        SELECT *
        FROM outbound_messages
        WHERE lead_id = ?
        ORDER BY id DESC
        LIMIT 8
        """,
        (lead_id,),
    ).fetchall()

    conn.close()

    triage = triage_lead(
        priority=lead["priority"],
        safety_flag=lead["safety_flag"],
        preferred_time=lead["preferred_time"],
        appointment_status=lead["appointment_status"],
        lead_status=lead["status"],
    )

    return render_template(
        "lead_detail.html",
        lead=lead,
        call=call,
        triage=triage,
        activities=activities,
        notes=notes,
        appointments=appointments,
        messages=messages,
        suggested_message=suggested_follow_up(lead),
    )

LEAD_STATUSES = [
    "New",
    "Contacted",
    "Estimate Scheduled",
    "Won",
    "Lost",
]


@app.route(
    "/lead/<int:lead_id>/status",
    methods=["POST"],
)
def update_lead_status(lead_id):
    status = request.form.get(
        "status",
        "New",
    ).strip()

    if status not in LEAD_STATUSES:
        flash(
            "Invalid lead status.",
            "error",
        )
        return redirect(
            url_for(
                "lead_detail",
                lead_id=lead_id,
            )
        )

    conn = connect()

    lead = conn.execute(
        """
        SELECT id
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()

    if lead is None:
        conn.close()
        return render_template("404.html"), 404

    if status == "Estimate Scheduled":
        appointment_status = "Scheduled"
    elif status in ("New", "Lost"):
        appointment_status = "Not Scheduled"
    else:
        appointment_status = None

    timestamp = now_iso()
    last_contacted_at = timestamp if status == "Contacted" else None
    clear_follow_up = status in ("Won", "Lost")

    if appointment_status is not None:
        conn.execute(
            """
            UPDATE leads
            SET status = ?,
                appointment_status = ?,
                updated_at = ?,
                last_contacted_at = CASE
                    WHEN ? IS NOT NULL THEN ?
                    ELSE last_contacted_at
                END,
                next_follow_up_at = CASE
                    WHEN ? THEN ''
                    ELSE next_follow_up_at
                END
            WHERE id = ?
            """,
            (
                status,
                appointment_status,
                timestamp,
                last_contacted_at,
                last_contacted_at,
                clear_follow_up,
                lead_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE leads
            SET status = ?,
                updated_at = ?,
                last_contacted_at = CASE
                    WHEN ? IS NOT NULL THEN ?
                    ELSE last_contacted_at
                END,
                next_follow_up_at = CASE
                    WHEN ? THEN ''
                    ELSE next_follow_up_at
                END
            WHERE id = ?
            """,
            (
                status,
                timestamp,
                last_contacted_at,
                last_contacted_at,
                clear_follow_up,
                lead_id,
            ),
        )

    conn.commit()
    conn.close()

    flash(
        f"Lead moved to {status}.",
        "success",
    )

    return redirect(
        url_for(
            "lead_detail",
            lead_id=lead_id,
        )
    )


@app.route(
    "/lead/<int:lead_id>/follow-up",
    methods=["POST"],
)
def update_lead_follow_up(lead_id):
    next_follow_up_at = request.form.get("next_follow_up_at", "").strip()

    conn = connect()
    lead = conn.execute(
        "SELECT id FROM leads WHERE id = ?",
        (lead_id,),
    ).fetchone()

    if lead is None:
        conn.close()
        return render_template("404.html"), 404

    timestamp = now_iso()
    conn.execute(
        """
        UPDATE leads
        SET next_follow_up_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (next_follow_up_at, timestamp, lead_id),
    )

    conn.execute(
        """
        INSERT INTO lead_activities (
            lead_id, activity_type, title, details, created_at
        )
        VALUES (?, 'Follow Up', ?, ?, ?)
        """,
        (
            lead_id,
            "Follow-up scheduled" if next_follow_up_at else "Follow-up cleared",
            next_follow_up_at or "No follow-up date set.",
            timestamp,
        ),
    )

    conn.commit()
    conn.close()
    flash("Follow-up updated.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route(
    "/lead/<int:lead_id>/note",
    methods=["POST"],
)
def add_lead_note(lead_id):
    note = request.form.get("note", "").strip()

    if not note:
        flash("Write a note before saving.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))

    conn = connect()
    lead = conn.execute(
        "SELECT id FROM leads WHERE id = ?",
        (lead_id,),
    ).fetchone()

    if lead is None:
        conn.close()
        return render_template("404.html"), 404

    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO lead_notes (lead_id, note, created_at)
        VALUES (?, ?, ?)
        """,
        (lead_id, note, timestamp),
    )
    conn.execute(
        """
        INSERT INTO lead_activities (
            lead_id, activity_type, title, details, created_at
        )
        VALUES (?, 'Note', 'Note added', ?, ?)
        """,
        (lead_id, note, timestamp),
    )
    conn.execute(
        "UPDATE leads SET updated_at = ? WHERE id = ?",
        (timestamp, lead_id),
    )
    conn.commit()
    conn.close()

    flash("Note added.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/calls")
def calls():
    conn = connect()

    rows = conn.execute(
        """
        SELECT
            calls.*,
            leads.caller_name AS caller_name,
            businesses.name AS business_name
        FROM calls
        LEFT JOIN leads
            ON leads.id = calls.lead_id
        LEFT JOIN businesses
            ON businesses.id = calls.business_id
        ORDER BY calls.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "calls.html",
        calls=rows,
    )




@app.route("/clients")
def clients():
    conn = connect()

    rows = conn.execute(
        """
        SELECT
            businesses.*,
            (SELECT COUNT(*) FROM leads WHERE leads.business_id = businesses.id) AS lead_count,
            (SELECT COUNT(*) FROM leads WHERE leads.business_id = businesses.id AND leads.status NOT IN ('Won', 'Lost')) AS open_lead_count,
            (SELECT COUNT(*) FROM leads WHERE leads.business_id = businesses.id AND leads.priority = 'Urgent' AND leads.status NOT IN ('Won', 'Lost')) AS urgent_lead_count,
            (SELECT COUNT(*) FROM calls WHERE calls.business_id = businesses.id) AS call_count
        FROM businesses
        WHERE businesses.status = 'Client'
        ORDER BY businesses.id DESC
        """
    ).fetchall()

    conn.close()
    businesses = businesses_with_analysis(rows)

    return render_template(
        "clients.html",
        businesses=businesses,
    )


@app.route("/client/<int:bid>")
def client_operations(bid):
    from services.action_queue import build_action_queue

    conn = connect()
    business = conn.execute(
        "SELECT * FROM businesses WHERE id = ? AND status = 'Client'",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    leads = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name,
            (
                SELECT MAX(lead_activities.created_at)
                FROM lead_activities
                WHERE lead_activities.lead_id = leads.id
            ) AS last_activity_at
        FROM leads
        LEFT JOIN businesses ON businesses.id = leads.business_id
        WHERE leads.business_id = ?
        ORDER BY leads.id DESC
        """,
        (bid,),
    ).fetchall()

    recent_calls = conn.execute(
        """
        SELECT calls.*, leads.caller_name
        FROM calls
        LEFT JOIN leads ON leads.id = calls.lead_id
        WHERE calls.business_id = ?
        ORDER BY calls.id DESC
        LIMIT 8
        """,
        (bid,),
    ).fetchall()

    appointment_rows = conn.execute(
        """
        SELECT appointments.*, leads.caller_name, leads.phone
        FROM appointments
        LEFT JOIN leads ON leads.id = appointments.lead_id
        WHERE appointments.business_id = ?
        ORDER BY appointments.start_at ASC
        """,
        (bid,),
    ).fetchall()

    pending_messages = conn.execute(
        """
        SELECT outbound_messages.*, leads.caller_name
        FROM outbound_messages
        LEFT JOIN leads ON leads.id = outbound_messages.lead_id
        WHERE outbound_messages.business_id = ?
          AND outbound_messages.status = 'Pending Approval'
        ORDER BY outbound_messages.id DESC
        LIMIT 6
        """,
        (bid,),
    ).fetchall()

    conn.close()

    open_leads = [lead for lead in leads if lead["status"] not in ("Won", "Lost")]
    won_count = sum(1 for lead in leads if lead["status"] == "Won")
    lost_count = sum(1 for lead in leads if lead["status"] == "Lost")
    closed_count = won_count + lost_count
    win_rate = round((won_count / closed_count) * 100) if closed_count else 0
    urgent_count = sum(
        1 for lead in open_leads
        if lead["priority"] == "Urgent" or lead["safety_flag"]
    )

    action_queue = build_action_queue(open_leads, limit=10)

    return render_template(
        "client_operations.html",
        business=business,
        leads=leads,
        recent_calls=recent_calls,
        action_queue=action_queue,
        open_count=len(open_leads),
        urgent_count=urgent_count,
        won_count=won_count,
        win_rate=win_rate,
        schedule=appointment_state(appointment_rows),
        pending_messages=pending_messages,
    )


@app.route(
    "/client/<int:bid>/retell-agent",
    methods=["POST"],
)
def update_client_retell_agent(bid):
    retell_agent_id = request.form.get("retell_agent_id", "").strip()

    conn = connect()
    business = conn.execute(
        "SELECT id FROM businesses WHERE id = ? AND status = 'Client'",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    conn.execute(
        "UPDATE businesses SET retell_agent_id = ? WHERE id = ?",
        (retell_agent_id, bid),
    )
    conn.commit()
    conn.close()

    flash("Receptionist mapping updated.", "success")
    return redirect(url_for("client_operations", bid=bid))


@app.route("/schedule")
def schedule():
    conn = connect()
    rows = conn.execute(
        """
        SELECT appointments.*, leads.caller_name, leads.phone,
               businesses.name AS business_name
        FROM appointments
        LEFT JOIN leads ON leads.id = appointments.lead_id
        LEFT JOIN businesses ON businesses.id = appointments.business_id
        ORDER BY appointments.start_at ASC
        """
    ).fetchall()
    conn.close()
    return render_template("schedule.html", schedule=appointment_state(rows))


@app.route("/automation")
def automation_center():
    conn = connect()
    pending = conn.execute(
        """
        SELECT outbound_messages.*, leads.caller_name, businesses.name AS business_name
        FROM outbound_messages
        LEFT JOIN leads ON leads.id = outbound_messages.lead_id
        LEFT JOIN businesses ON businesses.id = outbound_messages.business_id
        WHERE outbound_messages.status = 'Pending Approval'
        ORDER BY outbound_messages.id DESC
        """
    ).fetchall()
    ready = conn.execute(
        """
        SELECT outbound_messages.*, leads.caller_name, businesses.name AS business_name
        FROM outbound_messages
        LEFT JOIN leads ON leads.id = outbound_messages.lead_id
        LEFT JOIN businesses ON businesses.id = outbound_messages.business_id
        WHERE outbound_messages.status IN ('Approved', 'Failed')
        ORDER BY outbound_messages.id DESC
        """
    ).fetchall()
    recent = conn.execute(
        """
        SELECT outbound_messages.*, leads.caller_name, businesses.name AS business_name
        FROM outbound_messages
        LEFT JOIN leads ON leads.id = outbound_messages.lead_id
        LEFT JOIN businesses ON businesses.id = outbound_messages.business_id
        WHERE outbound_messages.status NOT IN ('Pending Approval', 'Approved', 'Failed')
        ORDER BY outbound_messages.id DESC
        LIMIT 20
        """
    ).fetchall()
    executions = conn.execute(
        """
        SELECT automation_executions.*, leads.caller_name, businesses.name AS business_name
        FROM automation_executions
        LEFT JOIN leads ON leads.id = automation_executions.lead_id
        LEFT JOIN businesses ON businesses.id = automation_executions.business_id
        ORDER BY automation_executions.id DESC
        LIMIT 30
        """
    ).fetchall()
    stats = {
        "pending": len(pending),
        "ready": len(ready),
        "successful": sum(1 for row in executions if row["status"] == "Success"),
        "blocked": sum(1 for row in executions if row["status"] == "Blocked"),
    }
    conn.close()
    return render_template(
        "automation.html", pending=pending, ready=ready, recent=recent,
        executions=executions, stats=stats, execution_mode="Simulation"
    )


@app.route("/lead/<int:lead_id>/appointment", methods=["POST"])
def create_appointment(lead_id):
    start_at = request.form.get("start_at", "").strip()
    duration_minutes = request.form.get("duration_minutes", "60").strip()
    notes = request.form.get("appointment_notes", "").strip()

    if not start_at:
        flash("Choose a date and time for the estimate.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))

    conn = connect()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        conn.close()
        return render_template("404.html"), 404

    timestamp = now_iso()
    end_at = end_from_duration(start_at, duration_minutes)
    conn.execute(
        """
        INSERT INTO appointments (
            business_id, lead_id, start_at, end_at, status,
            service_type, address, notes, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'Scheduled', ?, ?, ?, 'Business OS', ?, ?)
        """,
        (lead["business_id"], lead_id, start_at, end_at,
         lead["service_type"] or "Estimate", lead["address"] or "",
         notes, timestamp, timestamp),
    )
    conn.execute(
        """
        UPDATE leads
        SET status = 'Estimate Scheduled', appointment_status = 'Scheduled',
            next_follow_up_at = '', updated_at = ?
        WHERE id = ?
        """,
        (timestamp, lead_id),
    )
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Appointment', 'Estimate scheduled', ?, ?)
        """,
        (lead_id, start_at, timestamp),
    )
    conn.commit()
    conn.close()
    flash("Estimate added to the schedule.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/appointment/<int:appointment_id>/cancel", methods=["POST"])
def cancel_appointment(appointment_id):
    conn = connect()
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appointment is None:
        conn.close()
        return render_template("404.html"), 404
    timestamp = now_iso()
    conn.execute("UPDATE appointments SET status = 'Cancelled', updated_at = ? WHERE id = ?", (timestamp, appointment_id))
    conn.execute(
        """
        UPDATE leads
        SET status = CASE WHEN status = 'Estimate Scheduled' THEN 'Contacted' ELSE status END,
            appointment_status = 'Not Scheduled', updated_at = ?
        WHERE id = ?
        """,
        (timestamp, appointment["lead_id"]),
    )
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Appointment', 'Estimate cancelled', ?, ?)
        """,
        (appointment["lead_id"], appointment["start_at"], timestamp),
    )
    conn.commit()
    conn.close()
    flash("Estimate cancelled and lead returned to follow-up.", "success")
    return redirect(request.referrer or url_for("schedule"))


@app.route("/lead/<int:lead_id>/message", methods=["POST"])
def queue_lead_message(lead_id):
    body = request.form.get("message_body", "").strip()
    if not body:
        flash("Write a message before queuing it.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    conn = connect()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        conn.close()
        return render_template("404.html"), 404
    if not (lead["phone"] or "").strip():
        conn.close()
        flash("This lead has no phone number, so an SMS draft cannot be queued.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO outbound_messages (business_id, lead_id, channel, recipient, body, status, automation_key, created_at)
        VALUES (?, ?, 'SMS', ?, ?, 'Pending Approval', 'manual_follow_up', ?)
        """,
        (lead["business_id"], lead_id, lead["phone"], body, timestamp),
    )
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Message', 'SMS queued for approval', ?, ?)
        """,
        (lead_id, body, timestamp),
    )
    conn.commit()
    conn.close()
    flash("SMS draft queued for approval. Nothing was sent.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/message/<int:message_id>/approve", methods=["POST"])
def approve_message(message_id):
    conn = connect()
    message = conn.execute("SELECT * FROM outbound_messages WHERE id = ?", (message_id,)).fetchone()
    if message is None:
        conn.close()
        return render_template("404.html"), 404
    if message["status"] != "Pending Approval":
        conn.close()
        flash("That message is no longer pending approval.", "error")
        return redirect(request.referrer or url_for("automation_center"))
    timestamp = now_iso()
    conn.execute("UPDATE outbound_messages SET status = 'Approved', approved_at = ? WHERE id = ?", (timestamp, message_id))
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Message', 'SMS approved', 'Approved and ready for a future messaging provider.', ?)
        """,
        (message["lead_id"], timestamp),
    )
    conn.commit()
    conn.close()
    flash("Message approved. It is staged, not sent yet.", "success")
    return redirect(request.referrer or url_for("automation_center"))


@app.route("/message/<int:message_id>/execute", methods=["POST"])
def execute_message(message_id):
    conn = connect()
    result = execute_sms(conn, message_id, mode="simulation")
    conn.close()
    if result.ok:
        flash("Simulation passed. No customer was contacted.", "success")
    else:
        flash(result.detail, "error")
    return redirect(request.referrer or url_for("automation_center"))


@app.route("/message/<int:message_id>/discard", methods=["POST"])
def discard_message(message_id):
    conn = connect()
    message = conn.execute("SELECT * FROM outbound_messages WHERE id = ?", (message_id,)).fetchone()
    if message is None:
        conn.close()
        return render_template("404.html"), 404
    timestamp = now_iso()
    conn.execute("UPDATE outbound_messages SET status = 'Discarded' WHERE id = ?", (message_id,))
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Message', 'SMS draft discarded', '', ?)
        """,
        (message["lead_id"], timestamp),
    )
    conn.commit()
    conn.close()
    flash("Message draft discarded.", "success")
    return redirect(request.referrer or url_for("automation_center"))


@app.route("/prospects/export")
def export_prospects():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id
        """
    ).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    headers = [
        "name",
        "city",
        "category",
        "reviews",
        "rating",
        "website",
        "phone",
        "email",
        "status",
        "address",
        "source",
        "audit_status",
    ]

    writer.writerow(headers)

    for row in rows:
        writer.writerow(
            [
                row[header]
                if header in row.keys()
                else ""
                for header in headers
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=business_os_prospects.csv"
        },
    )


@app.route(
    "/prospects/import",
    methods=["POST"],
)
def import_prospects():
    upload = request.files.get("file")

    if not upload or not upload.filename:
        flash(
            "Choose a CSV file first.",
            "error",
        )
        return redirect(
            url_for("prospects")
        )

    text = upload.stream.read().decode(
        "utf-8-sig"
    )

    reader = csv.DictReader(
        io.StringIO(text)
    )

    conn = connect()

    added = 0
    skipped = 0

    for row in reader:
        name = (
            row.get("name")
            or ""
        ).strip()

        city = (
            row.get("city")
            or ""
        ).strip()

        if not name or not city:
            skipped += 1
            continue

        website = (
            row.get("website")
            or ""
        ).strip()

        phone = (
            row.get("phone")
            or ""
        ).strip()

        duplicate = conn.execute(
            """
            SELECT id
            FROM businesses
            WHERE LOWER(name) = LOWER(?)
              AND (
                (phone != '' AND phone = ?)
                OR
                (
                    website != ''
                    AND LOWER(website) = LOWER(?)
                )
                OR
                LOWER(city) = LOWER(?)
              )
            LIMIT 1
            """,
            (
                name,
                phone,
                website,
                city,
            ),
        ).fetchone()

        if duplicate:
            skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO businesses (
                name,
                city,
                category,
                reviews,
                rating,
                website,
                phone,
                email,
                online_booking,
                emergency_service,
                website_chat,
                estimate_form,
                status,
                notes,
                created_at,
                address,
                source,
                audit_status
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                0, 0, 0, 0,
                ?, '',
                ?, ?,
                'csv',
                'not_audited'
            )
            """,
            (
                name,
                city,
                (
                    row.get("category")
                    or "Local Service Business"
                ).strip(),
                int(
                    float(
                        row.get("reviews")
                        or 0
                    )
                ),
                float(
                    row.get("rating")
                    or 0
                ),
                website,
                phone,
                (
                    row.get("email")
                    or ""
                ).strip(),
                (
                    row.get("status")
                    or "Not Contacted"
                ).strip(),
                now_iso(),
                (
                    row.get("address")
                    or ""
                ).strip(),
            ),
        )

        added += 1

    conn.commit()
    conn.close()

    flash(
        f"CSV import complete. "
        f"{added} added. "
        f"{skipped} skipped.",
        "success",
    )

    return redirect(
        url_for("prospects")
    )


@app.errorhandler(404)
def page_not_found(error):
    return (
        render_template("404.html"),
        404,
    )


if __name__ == "__main__":
    init_db()

    app.run(
        debug=True
    )