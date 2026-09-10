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
            SELECT id
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
        }, 200

    cursor = conn.execute(
        """
        INSERT INTO leads (
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
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
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
            now_iso(),
        ),
    )

    lead_id = cursor.lastrowid

    cursor = conn.execute(
        """
        INSERT INTO calls (
            lead_id,
            retell_call_id,
            caller_phone,
            duration_seconds,
            summary,
            transcript,
            call_status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            retell_call_id,
            caller_phone,
            duration_seconds,
            summary,
            transcript,
            "Completed",
            now_iso(),
        ),
    )

    call_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "duplicate": False,
        "lead_id": lead_id,
        "call_id": call_id,
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

    if appointment_status is not None:
        conn.execute(
            """
            UPDATE leads
            SET status = ?,
                appointment_status = ?
            WHERE id = ?
            """,
            (
                status,
                appointment_status,
                lead_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE leads
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
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
        SELECT *
        FROM businesses
        WHERE status = 'Client'
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    return render_template(
        "clients.html",
        businesses=businesses,
    )


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