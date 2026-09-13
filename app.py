import os
import csv
import io
import json

from dotenv import load_dotenv

load_dotenv()

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
from services.v14_discovery import discover
from services.scoring import opportunity_analysis
from services.website_auditor import audit_batch, audit_business_by_id
from services.lead_triage import triage_lead
from services.operations import appointment_state, end_from_duration, suggested_follow_up
from services.automation_engine import execute_sms, validate_sms_message
from services.governance import classify_inbound, quarantine
from services.security import verify_retell_signature
from services.version import VERSION, RELEASE_NAME, BUILD_ID
from services.product_foundation import ensure_product_schema, readiness_for_business, save_profile, activate_business, client_product_view, attention_queue
from services.business_config import ensure_business_config_schema, configuration_view, add_service, toggle_service, add_intake_question, toggle_intake_question
from services.website_studio import website_studio_view
from services.website_versions import (
    WebsiteVersionConflict,
    WebsiteVersionNotFound,
    get_current_version,
    get_preview_version,
    list_versions,
    select_preview_version,
    synchronize_readiness,
    update_presentation,
)
from services.website_renderer import (
    WebsiteRenderNotFound,
    build_current_draft_render_model,
    build_preview_render_model,
)
from services.v13_creative_director import generate_concept_blueprint
from services.v13_site_model import build_site_model
from services.v13_concepts import (
    ConceptNotFound,
    create_concept,
    ensure_v13_schema,
    get_concept_for_business,
    list_concepts,
    next_concept_number,
)
from services.v13_sales import build_sales_brief
from services.founder_command import build_founder_command
from services.v14_sales_workspace import (
    build_sales_workspace,
    log_sales_interaction,
    complete_followup,
    save_conversion_draft,
    convert_to_onboarding,
)
from services.v14_delivery import (
    delivery_dashboard,
    create_local_release,
    active_release_by_slug,
    issue_form_nonce,
    submit_public_intake,
)
from services.v14_production_site import generate_design as generate_production_design, selected_design, production_model
from services.v14_client_portal import portal_view
from services.v14_client_experience import client_workspace_state, owner_preview_state
from services.v14_acceptance import acceptance_state
from services.v15_site_intelligence import intelligence_view, run_site_intelligence
from services.v16_website_engine import generate_v16_demo, get_v16_demo, list_v16_demos, ensure_v16_schema
from services.v19_ai_website_agent import generate_ai_demo
from services.v20_presentation import prepare_v20_site
from services.v21_presentation import prepare_v21_site
from services.v22_design_system import prepare_v22_site
from services.v15_upgrade_engine import (
    build_upgrade_blueprint,
    ensure_upgrade_schema,
    record_owner_verification,
    upgrade_workspace_view,
)
from services.front_office_intelligence import (
    ensure_front_office_schema, lead_intelligence, link_lead_service,
    save_intake_answer, unified_timeline, build_front_office_queue,
)
from services.operator_search import search_operator_records
from services.customer_continuity import customer_continuity
from services.system_health import build_health_report
from services.control_plane import ensure_control_plane_schema, control_plane_overview, command_center_summary, review_improvement, ledger_event
from services.execution_schema import ensure_execution_schema
from services.execution_core import live_actions_enabled
from services.reliability import (
    create_database_snapshot,
    ensure_daily_snapshot,
    reliability_dashboard,
    run_self_test,
    record_system_event,
)

app = Flask(__name__)
app.secret_key = os.getenv("BUSINESS_OS_SECRET_KEY", "business-os-local-development-only")


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
        "business_os_version": VERSION,
        "business_os_release": RELEASE_NAME,
        "business_os_build": BUILD_ID,
    }


@app.route("/")
def dashboard():
    conn = connect()
    ensure_control_plane_schema(conn)

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

    control_summary = command_center_summary(conn)

    pending_messages = conn.execute(
        """
        SELECT COUNT(*)
        FROM outbound_messages
        WHERE status = 'Pending Approval'
        """
    ).fetchone()[0]

    action_queue_total = len(action_queue_rows)
    action_queue = build_front_office_queue(conn, action_queue_rows, limit=8)
    top_action = action_queue[0] if action_queue else None

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
        control=control_summary,
    )


@app.route("/founder")
def founder_command():
    conn = connect()
    try:
        command = build_founder_command(conn)
    finally:
        conn.close()
    return render_template("founder_command.html", command=command)


@app.route("/business/<int:bid>/sales")
def sales_workspace(bid):
    conn = connect()
    try:
        try:
            workspace = build_sales_workspace(conn, bid)
            workspace["upgrade"] = upgrade_workspace_view(conn, bid)
        except LookupError:
            return render_template("404.html"), 404
    finally:
        conn.close()
    return render_template("sales_workspace.html", ws=workspace)


@app.route("/business/<int:bid>/sales/log", methods=["POST"])
def sales_log_interaction(bid):
    conn = connect()
    try:
        try:
            new_status = log_sales_interaction(
                conn,
                business_id=bid,
                interaction_type=request.form.get("interaction_type", ""),
                channel=request.form.get("channel", "OTHER"),
                summary=request.form.get("summary", ""),
                follow_up_at=request.form.get("follow_up_at", ""),
                follow_up_reason=request.form.get("follow_up_reason", ""),
            )
            flash(f"Sales activity saved. Pipeline is now {new_status}.", "success")
        except (LookupError, ValueError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("sales_workspace", bid=bid))


@app.route("/business/<int:bid>/sales/followup/<int:followup_id>/complete", methods=["POST"])
def sales_complete_followup(bid, followup_id):
    conn = connect()
    try:
        try:
            changed = complete_followup(conn, business_id=bid, followup_id=followup_id)
            flash("Follow-up completed." if changed else "Follow-up was already closed.", "success")
        except LookupError as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("sales_workspace", bid=bid))


@app.route("/business/<int:bid>/sales/conversion", methods=["POST"])
def sales_save_conversion(bid):
    conn = connect()
    try:
        try:
            save_conversion_draft(conn, business_id=bid, values=request.form)
            flash("Owner-verification draft saved. Nothing was activated.", "success")
        except (LookupError, ValueError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("sales_workspace", bid=bid) + "#conversion")


@app.route("/business/<int:bid>/sales/convert", methods=["POST"])
def sales_convert_to_client(bid):
    conn = connect()
    try:
        ok, message = convert_to_onboarding(conn, business_id=bid)
    finally:
        conn.close()
    flash(message, "success" if ok else "error")
    if ok:
        return redirect(url_for("business_configuration", bid=bid))
    return redirect(url_for("sales_workspace", bid=bid) + "#conversion")


@app.route("/demo-studio")
def demo_studio():
    conn = connect()
    ensure_v13_schema(conn)
    rows = conn.execute("SELECT * FROM businesses ORDER BY id DESC").fetchall()
    businesses = []
    for row in rows:
        item = dict(row)
        item["concept_count"] = conn.execute("SELECT COUNT(*) FROM website_concepts WHERE business_id=?", (row["id"],)).fetchone()[0]
        businesses.append(item)
    conn.close()
    return render_template("demo_studio.html", businesses=businesses)


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


@app.route("/business/<int:bid>/intelligence")
def website_intelligence(bid):
    conn = connect()
    try:
        view = intelligence_view(conn, bid)
        view["upgrade"] = upgrade_workspace_view(conn, bid)
    except LookupError:
        return render_template("404.html"), 404
    finally:
        conn.close()
    return render_template("v15_website_intelligence.html", view=view)


@app.route("/business/<int:bid>/intelligence/run", methods=["POST"])
def run_website_intelligence(bid):
    conn = connect()
    try:
        run_site_intelligence(conn, bid)
        flash("Website Intelligence captured a new evidence snapshot. Nothing was promoted into Business Truth.", "success")
    except Exception as exc:
        flash(f"Website Intelligence could not complete: {exc}", "error")
    finally:
        conn.close()
    return redirect(url_for("website_intelligence", bid=bid))


@app.route("/business/<int:bid>/upgrade/build", methods=["POST"])
def build_website_upgrade_blueprint(bid):
    conn = connect()
    try:
        try:
            result = build_upgrade_blueprint(conn, bid)
            counts = result["counts"]
            flash(
                "Upgrade Blueprint ready: "
                f"keep {counts['KEEP']}, improve {counts['IMPROVE']}, "
                f"add {counts['ADD']}, verify {counts['VERIFY']}.",
                "success",
            )
        except (LookupError, ValueError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("website_intelligence", bid=bid))


@app.route("/business/<int:bid>/upgrade/verify", methods=["POST"])
def verify_business_truth_claim(bid):
    conn = connect()
    try:
        try:
            result = record_owner_verification(
                conn,
                bid,
                claim_key=request.form.get("claim_key", ""),
                decision=request.form.get("decision", ""),
                confirmed_value=request.form.get("confirmed_value", ""),
                note=request.form.get("note", ""),
            )
            flash(
                f"Owner answer recorded. Upgrade Blueprint v{result['blueprint']['version_number']} reflects it.",
                "success",
            )
        except (LookupError, ValueError) as exc:
            flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("website_intelligence", bid=bid) + "#business-truth")


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


@app.route("/business/<int:bid>/concept")
def prospect_concept_workspace(bid):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    sales = build_sales_brief(business)
    concepts = list_concepts(conn, bid)
    demos = list_v16_demos(conn, bid, 20)
    current_demo = demos[0] if demos else None
    conn.close()
    return render_template(
        "prospect_concept.html",
        business=dict(business),
        sales=sales,
        concepts=concepts,
        demos=demos,
        current_demo=current_demo,
    )


@app.route("/business/<int:bid>/concept/generate", methods=["POST"])
def generate_prospect_concept(bid):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404

    creative_brief = request.form.get("creative_brief", "").strip()
    concept_number = next_concept_number(conn, bid)
    try:
        director = generate_concept_blueprint(dict(business), creative_brief, concept_number)
        concept = create_concept(
            conn,
            bid,
            creative_brief,
            director.blueprint,
            director.generation_mode,
        )
        flash(
            f"Private concept {concept['concept_number']} generated. Nothing was published.",
            "success",
        )
    except Exception as exc:
        flash(f"Concept generation failed safely: {exc}", "error")
    finally:
        conn.close()

    return redirect(url_for("prospect_concept_workspace", bid=bid))


@app.route("/business/<int:bid>/concept/<int:concept_id>/preview")
def prospect_concept_preview(bid, concept_id):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    try:
        concept = get_concept_for_business(conn, bid, concept_id)
    except ConceptNotFound:
        conn.close()
        return render_template("404.html"), 404
    conn.close()

    site = build_site_model(dict(business), concept["blueprint"])
    response = render_template(
        "prospect_concept_preview.html",
        business=dict(business),
        concept=concept,
        bp=concept["blueprint"],
        site=site,
    )
    return Response(
        response,
        headers={
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.route("/business/<int:bid>/v19/design", methods=["POST"])
def v19_design_website(bid):
    """Real model-backed Website Design Agent. No template fallback."""
    conn = connect()
    try:
        creative_brief = request.form.get("creative_brief", "").strip()
        demo = generate_ai_demo(conn, bid, refresh_intelligence=True, creative_brief=creative_brief)
        flash(f"Website #{demo['id']} is ready for review.", "success")
        return redirect(url_for("v16_private_demo", bid=bid, demo_id=demo["id"]))
    except Exception as exc:
        flash(f"AI Website Design Agent stopped safely: {exc}", "error")
        return redirect(url_for("prospect_concept_workspace", bid=bid))
    finally:
        conn.close()


@app.route("/business/<int:bid>/v16/design", methods=["POST"])
def v16_design_website(bid):
    """One-click v16 path: refresh evidence when possible, then build a private tenant-bound demo."""
    conn = connect()
    try:
        demo = generate_v16_demo(conn, bid, refresh_intelligence=True)
        flash(f"v16 private website demo #{demo['id']} is ready.", "success")
        return redirect(url_for("v16_private_demo", bid=bid, demo_id=demo["id"]))
    except Exception as exc:
        flash(f"v16 website generation failed safely: {exc}", "error")
        return redirect(url_for("prospect_concept_workspace", bid=bid))
    finally:
        conn.close()


@app.route("/business/<int:bid>/v16/demo/<int:demo_id>")
def v16_private_demo(bid, demo_id):
    conn = connect()
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    demo = get_v16_demo(conn, bid, demo_id)
    if business is None or demo is None:
        conn.close()
        return render_template("404.html"), 404
    is_ai_demo = demo.get("design_family") in {"AI_AGENT_V19", "AI_AGENT_V20", "AI_AGENT_V21", "AI_AGENT_V22"} or demo["site"].get("engine_version") in {"19.0", "20.0", "21.0", "22.0"}
    template = "v19_ai_demo.html" if is_ai_demo else "v16_private_demo.html"
    render_site = prepare_v22_site(conn, bid, demo_id, demo["site"]) if is_ai_demo else demo["site"]
    conn.close()
    return Response(render_template(template, business=dict(business), demo=demo, s=render_site, submitted=request.args.get("submitted")), headers={"X-Robots-Tag":"noindex, nofollow, noarchive","Cache-Control":"private, no-store, max-age=0"})


@app.route("/business/<int:bid>/v16/demo/<int:demo_id>/lead", methods=["POST"])
def v16_demo_lead(bid, demo_id):
    conn = connect()
    demo = get_v16_demo(conn, bid, demo_id)
    if demo is None:
        conn.close(); return render_template("404.html"), 404
    name = request.form.get("name", "").strip()[:200]
    phone = request.form.get("phone", "").strip()[:80]
    email = request.form.get("email", "").strip()[:254]
    service = request.form.get("service", "").strip()[:200]
    address = request.form.get("address", "").strip()[:300]
    message = request.form.get("message", "").strip()[:2000]
    property_type = request.form.get("property_type", "").strip()[:80]
    allowed = {x.get("name") for x in demo["site"].get("services", []) if isinstance(x, dict)}
    allowed.update(demo["site"].get("form", {}).get("service_options", []))
    if not name or not phone or not message or service not in allowed:
        conn.close(); flash("Please complete the required estimate fields.", "error")
        return redirect(url_for("v16_private_demo", bid=bid, demo_id=demo_id) + "#estimate")
    ts = now_iso()
    urgent = any(x in (service + " " + message).lower() for x in ("emergency", "storm", "fallen", "danger", "urgent"))
    cur = conn.execute("""INSERT INTO leads(business_id,caller_name,phone,address,service_type,issue_description,lead_type,priority,safety_flag,preferred_time,appointment_status,status,source,retell_call_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,'New Lead',?,?,'','Not Scheduled','New','Website','',?,?)""",
        (bid,name,phone,address,service,message,"Urgent" if urgent else "Normal","Urgent website inquiry" if urgent else "",ts,ts))
    lead_id = cur.lastrowid
    note = "v16 private demo intake"
    if email: note += f" · Email: {email}"
    if property_type: note += f" · Property: {property_type}"
    conn.execute("INSERT INTO lead_notes(lead_id,note,created_at) VALUES (?,?,?)", (lead_id,note,ts))
    conn.commit(); conn.close()
    return redirect(url_for("v16_private_demo", bid=bid, demo_id=demo_id, submitted=lead_id) + "#estimate")


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

    message_rows = conn.execute(
        """
        SELECT
            outbound_messages.*,
            leads.caller_name,
            businesses.name AS business_name
        FROM outbound_messages
        LEFT JOIN leads ON leads.id = outbound_messages.lead_id
        LEFT JOIN businesses ON businesses.id = outbound_messages.business_id
        WHERE outbound_messages.status = 'Pending Approval'
        ORDER BY outbound_messages.id DESC
        LIMIT 12
        """
    ).fetchall()

    conn.close()

    return render_template(
        "approvals.html",
        approvals=rows,
        message_approvals=message_rows,
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
    """Resolve only an explicit agent mapping. Never guess from client count."""
    agent_id = str(agent_id or "").strip()
    if not agent_id:
        return None
    mapped = conn.execute(
        """
        SELECT id
        FROM businesses
        WHERE retell_agent_id = ?
        LIMIT 1
        """,
        (agent_id,),
    ).fetchone()
    return mapped["id"] if mapped else None


@app.route("/webhooks/retell", methods=["POST"])
def retell_webhook():
    raw_body = request.get_data(cache=True)
    signature = request.headers.get("X-Retell-Signature", "")
    api_key = os.getenv("RETELL_API_KEY", "").strip()
    allow_unsigned = os.getenv("BUSINESS_OS_ALLOW_UNSIGNED_RETELL", "0").strip().lower() in {"1", "true", "yes", "on"}

    # Signed requests are always verified. Unsigned requests are accepted only
    # when an operator deliberately enables the local-development bypass.
    if signature:
        verified, reason = verify_retell_signature(raw_body, signature, api_key)
        if not verified:
            record_system_event("Rejected Retell webhook", reason, severity="Warning", event_type="Security")
            return {"ok": False, "error": "Webhook authentication failed"}, 401
    elif not allow_unsigned:
        record_system_event(
            "Rejected unsigned Retell webhook",
            "No X-Retell-Signature header was present and unsigned local bypass is disabled.",
            severity="Warning", event_type="Security"
        )
        return {"ok": False, "error": "Webhook signature required"}, 401

    try:
        data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "Invalid JSON payload"}, 400

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

    # The CRM type is independent from governance classification.
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
    governance = classify_inbound(conn, business_id)
    data_classification = governance.classification
    quarantine_open = data_classification == "UNVERIFIED" or business_id is None
    quarantine_status = "Open" if quarantine_open else "Not Required"
    quarantine_reason = governance.reason if quarantine_open else ""

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
              AND data_classification = ?
              AND quarantine_status != 'Open'
              AND status NOT IN ('Won', 'Lost')
            ORDER BY id DESC
            LIMIT 50
            """,
            (business_id, data_classification),
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
                data_classification = ?,
                source_agent_id = ?,
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
                data_classification,
                retell_agent_id,
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
                updated_at,
                data_classification,
                quarantine_status,
                quarantine_reason,
                source_agent_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                data_classification,
                quarantine_status,
                quarantine_reason,
                retell_agent_id,
            ),
        )
        lead_id = cursor.lastrowid
        if quarantine_open:
            quarantine(
                conn, "lead", lead_id, "unverified_retell_routing",
                quarantine_reason, business_id=business_id, classification=data_classification
            )

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
            created_at,
            data_classification,
            quarantine_status,
            quarantine_reason,
            source_agent_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data_classification,
            quarantine_status,
            quarantine_reason,
            retell_agent_id,
        ),
    )

    call_id = cursor.lastrowid
    if quarantine_open:
        quarantine(
            conn, "call", call_id, "unverified_retell_routing",
            quarantine_reason, business_id=business_id, classification=data_classification
        )

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


@app.route("/search")
def global_search():
    query = request.args.get("q", "")
    raw_business = request.args.get("business_id", "").strip()
    business_id = int(raw_business) if raw_business.isdigit() else None
    conn = connect()
    results = search_operator_records(conn, query, business_id=business_id)
    conn.close()
    return render_template(
        "search_results.html",
        search=results,
        business_id=business_id,
    )


@app.route("/leads")


def leads():
    conn = connect()
    raw_business = request.args.get("business_id", "").strip()
    business_id = int(raw_business) if raw_business.isdigit() else None
    where = "WHERE leads.business_id = ?" if business_id is not None else ""
    args = (business_id,) if business_id is not None else ()
    rows = conn.execute(
        f"""
        SELECT leads.*, businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses ON businesses.id = leads.business_id
        {where}
        ORDER BY leads.id DESC
        """,
        args,
    ).fetchall()
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone() if business_id is not None else None
    conn.close()
    return render_template("leads.html", leads=rows, business=business, business_id=business_id)

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

    intelligence = lead_intelligence(conn, lead_id)
    timeline = unified_timeline(conn, lead_id)
    continuity = customer_continuity(conn, lead_id)
    configured_services = []
    if lead["business_id"]:
        configured_services = conn.execute(
            "SELECT * FROM business_services WHERE business_id=? AND active=1 ORDER BY sort_order,id",
            (lead["business_id"],),
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
        intelligence=intelligence,
        unified_timeline=timeline,
        customer_continuity=continuity,
        configured_services=configured_services,
    )


@app.route("/lead/<int:lead_id>/service-link", methods=["POST"])
def set_lead_service_link(lead_id):
    raw_service = request.form.get("service_id", "").strip()
    if not raw_service.isdigit():
        flash("Choose a verified service before saving.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    conn = connect()
    lead = conn.execute("SELECT id,business_id FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    if not lead or not lead["business_id"]:
        flash("This lead must have a proven client owner before a service can be linked.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    ok, message = link_lead_service(lead["business_id"], lead_id, int(raw_service))
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/lead/<int:lead_id>/intake/<int:question_id>", methods=["POST"])
def save_lead_intake_answer(lead_id, question_id):
    conn = connect()
    lead = conn.execute("SELECT id,business_id FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    if not lead or not lead["business_id"]:
        flash("This lead must have a proven client owner before intake can be saved.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    answer = request.form.get("answer_text", "")
    ok, message = save_intake_answer(lead["business_id"], lead_id, question_id, answer)
    flash(message, "success" if ok else "error")
    return redirect(url_for("lead_detail", lead_id=lead_id))

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
    raw_business = request.args.get("business_id", "").strip()
    business_id = int(raw_business) if raw_business.isdigit() else None
    where = "WHERE calls.business_id = ?" if business_id is not None else ""
    args = (business_id,) if business_id is not None else ()
    rows = conn.execute(
        f"""
        SELECT calls.*, leads.caller_name AS caller_name, businesses.name AS business_name
        FROM calls
        LEFT JOIN leads ON leads.id = calls.lead_id
        LEFT JOIN businesses ON businesses.id = calls.business_id
        {where}
        ORDER BY calls.id DESC
        """,
        args,
    ).fetchall()
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone() if business_id is not None else None
    conn.close()
    return render_template("calls.html", calls=rows, business=business, business_id=business_id)




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

    product = client_product_view(conn, business)
    attention = attention_queue(conn, business_id=bid, limit=12)

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
        "client_command_center.html",
        business=business,
        product=product,
        attention=attention,
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

    if retell_agent_id:
        duplicate = conn.execute(
            "SELECT id, name FROM businesses WHERE retell_agent_id = ? AND id != ? LIMIT 1",
            (retell_agent_id, bid),
        ).fetchone()
        if duplicate:
            conn.close()
            flash(f"That Retell agent is already mapped to {duplicate['name']}. Mapping blocked.", "error")
            return redirect(url_for("client_operations", bid=bid))
    conn.execute(
        "UPDATE businesses SET retell_agent_id = ?, lifecycle_updated_at = ? WHERE id = ?",
        (retell_agent_id, now_iso(), bid),
    )
    conn.commit()
    conn.close()

    flash("Receptionist mapping updated. Exact routing is enforced.", "success")
    return redirect(url_for("client_operations", bid=bid))


@app.route("/client/<int:bid>/onboarding", methods=["GET", "POST"])
def client_onboarding(bid):
    conn = connect()
    ensure_product_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id = ?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    if request.method == "POST":
        conn.close()
        save_profile(bid, request.form)
        flash("Client configuration saved. Activation remains deliberate and gated.", "success")
        return redirect(url_for("client_onboarding", bid=bid))
    readiness = readiness_for_business(conn, business)
    conn.close()
    return render_template("client_onboarding.html", business=business, readiness=readiness)


@app.route("/client/<int:bid>/activate", methods=["POST"])
def activate_client(bid):
    ok, message = activate_business(bid)
    flash(message, "success" if ok else "error")
    return redirect(url_for("client_onboarding", bid=bid))


@app.route("/client/<int:bid>/configuration")
def business_configuration(bid):
    conn = connect()
    ensure_product_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    config = configuration_view(conn, bid)
    readiness = readiness_for_business(conn, business)
    conn.close()
    return render_template("business_configuration.html", business=business, config=config, readiness=readiness)



@app.route("/client/<int:bid>/design")
def production_design_studio(bid):
    conn=connect(); business=conn.execute("SELECT * FROM businesses WHERE id=?",(bid,)).fetchone()
    if business is None: conn.close(); return render_template("404.html"),404
    design=selected_design(conn,bid); conn.close(); return render_template("production_design_studio.html",business=business,design=design)

@app.route("/client/<int:bid>/design/generate",methods=["POST"])
def production_site_generate(bid):
    conn=connect()
    try: generate_production_design(conn,bid,request.form.get("creative_brief","")); flash("Production design generated from reviewed truth.","success")
    except (LookupError,ValueError) as exc: flash(str(exc),"error")
    finally: conn.close()
    return redirect(url_for("production_design_studio",bid=bid))

@app.route("/client/<int:bid>/design/preview")
def production_site_preview(bid):
    conn=connect(); business=conn.execute("SELECT * FROM businesses WHERE id=?",(bid,)).fetchone()
    if business is None: conn.close(); return render_template("404.html"),404
    try: site=production_model(conn,bid)
    except (LookupError,ValueError) as exc: conn.close(); flash(str(exc),"error"); return redirect(url_for("production_design_studio",bid=bid))
    conn.close(); return render_template("production_site_preview.html",site=site,bp=site["blueprint"],business=business)

@app.route("/client/<int:bid>/owner-preview")
def client_portal_preview(bid):
    conn = connect()
    tab = request.args.get("tab", "today")
    try:
        portal = owner_preview_state(conn, bid, tab=tab)
    except LookupError:
        conn.close()
        return render_template("404.html"), 404
    except Exception as exc:
        # Operator preview must fail visibly and recoverably rather than strand the user.
        business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
        conn.close()
        if business is None:
            return render_template("404.html"), 404
        return render_template(
            "client_portal_unavailable.html",
            business=business,
            reason=str(exc),
        ), 503
    conn.close()
    return render_template("client_portal_preview.html", portal=portal, business=portal["business"])




@app.route("/client/<int:bid>/acceptance")
def client_acceptance_lab(bid):
    """Operator-only local acceptance lab for the three-persona journey."""
    conn = connect()
    try:
        state = acceptance_state(conn, bid)
    except LookupError:
        conn.close()
        return render_template("404.html"), 404
    conn.close()
    return render_template("client_acceptance_lab.html", business=state["business"], lab=state)


@app.route("/client/<int:bid>/delivery")
def delivery_center(bid):
    conn = connect()
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    try:
        delivery = delivery_dashboard(conn, bid)
    except (LookupError, ValueError) as exc:
        conn.close()
        flash(str(exc), "error")
        return redirect(url_for("client_command_center", bid=bid))
    conn.close()
    return render_template("delivery_center.html", business=business, delivery=delivery)


@app.route("/client/<int:bid>/delivery/release", methods=["POST"])
def delivery_release(bid):
    conn = connect()
    try:
        release = create_local_release(conn, bid)
        flash(
            f"Reviewed local release #{release['id']} created. Nothing was published externally.",
            "success",
        )
    except (LookupError, ValueError) as exc:
        flash(str(exc), "error")
    finally:
        conn.close()
    return redirect(url_for("delivery_center", bid=bid))


@app.route("/site/<slug>")
def public_site(slug):
    conn = connect()
    release = active_release_by_slug(conn, slug)
    if release is None:
        conn.close()
        return render_template("404.html"), 404
    nonce = issue_form_nonce(conn, release["id"])
    conn.close()
    import secrets
    return render_template(
        "public_site.html",
        site=release["artifact"],
        slug=slug,
        nonce=nonce,
        idempotency_key=secrets.token_urlsafe(18),
        form={},
        errors=[],
        submitted=False,
        lead_id=None,
    )


@app.route("/site/<slug>/request", methods=["POST"])
def public_site_request(slug):
    conn = connect()
    release = active_release_by_slug(conn, slug)
    if release is None:
        conn.close()
        return render_template("404.html"), 404
    values = {
        "name": request.form.get("name", ""),
        "phone": request.form.get("phone", ""),
        "email": request.form.get("email", ""),
        "address": request.form.get("address", ""),
        "service": request.form.get("service", ""),
        "preferred_time": request.form.get("preferred_time", ""),
        "message": request.form.get("message", ""),
        "company_website": request.form.get("company_website", ""),
    }
    try:
        result = submit_public_intake(
            conn,
            slug=slug,
            nonce=request.form.get("nonce", ""),
            idempotency_key=request.form.get("idempotency_key", ""),
            values=values,
        )
    except ValueError as exc:
        # A consumed/expired nonce requires a clean form reload; do not reuse it.
        nonce = issue_form_nonce(conn, release["id"])
        conn.close()
        import secrets
        return render_template(
            "public_site.html", site=release["artifact"], slug=slug, nonce=nonce,
            idempotency_key=secrets.token_urlsafe(18), form=values,
            errors=[str(exc)], submitted=False, lead_id=None,
        ), 400

    if result.get("status") == "REJECTED":
        nonce = issue_form_nonce(conn, release["id"])
        conn.close()
        import secrets
        return render_template(
            "public_site.html", site=release["artifact"], slug=slug, nonce=nonce,
            idempotency_key=secrets.token_urlsafe(18), form=values,
            errors=result.get("errors") or ["Request could not be accepted."],
            submitted=False, lead_id=None,
        ), 400

    conn.close()
    return render_template(
        "public_site.html", site=release["artifact"], slug=slug, nonce="",
        idempotency_key="", form={}, errors=[], submitted=True,
        lead_id=result.get("lead_id"),
    )


@app.route("/client/<int:bid>/website")
def website_studio(bid):
    conn = connect()

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        studio = website_studio_view(
            conn,
            bid,
        )

        draft = get_current_version(
            conn,
            bid,
        )

        preview = get_preview_version(
            conn,
            bid,
        )

        versions = list_versions(
            conn,
            bid,
            limit=20,
        )

        render_model = (
            build_current_draft_render_model(
                conn,
                bid,
            )
        )

    except (
        WebsiteVersionNotFound,
        WebsiteRenderNotFound,
    ) as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "business_configuration",
                bid=bid,
            )
        )

    conn.close()

    return render_template(
        "website_studio.html",
        business=business,
        studio=studio,
        draft=draft,
        preview=preview,
        versions=versions,
        site=render_model,
    )


@app.route(
    "/client/<int:bid>/website/save",
    methods=["POST"],
)
def save_website_studio(bid):
    conn = connect()

    business = conn.execute(
        "SELECT id FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    changes = {
        "theme_key": (
            request.form.get(
                "theme_key",
                "classic",
            ).strip()
        ),
        "hero_headline": request.form.get(
            "hero_headline",
            "",
        ),
        "hero_supporting_text": request.form.get(
            "hero_supporting_text",
            "",
        ),
        "primary_cta_label": request.form.get(
            "primary_cta_label",
            "Request Service",
        ),
        "about_copy": request.form.get(
            "about_copy",
            "",
        ),
        "contact_intro": request.form.get(
            "contact_intro",
            "",
        ),
        "show_services": (
            request.form.get(
                "show_services"
            )
            == "1"
        ),
        "show_about": (
            request.form.get(
                "show_about"
            )
            == "1"
        ),
        "show_contact": (
            request.form.get(
                "show_contact"
            )
            == "1"
        ),
        "seo_title": request.form.get(
            "seo_title",
            "",
        ),
        "seo_description": request.form.get(
            "seo_description",
            "",
        ),
    }

    expected_version = request.form.get(
        "expected_current_version_id",
        "",
    ).strip()

    try:
        result = update_presentation(
            conn,
            bid,
            changes,
            expected_current_version_id=(
                expected_version
                if expected_version
                else None
            ),
        )

        synchronize_readiness(
            conn,
            bid,
        )

    except WebsiteVersionConflict as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    except (
        WebsiteVersionNotFound,
        ValueError,
    ) as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    if result.get(
        "created_new_version"
    ):
        flash(
            "Website draft saved as a new version. "
            "The reviewed preview was not changed.",
            "success",
        )

    else:
        flash(
            "No presentation changes were detected.",
            "success",
        )

    return redirect(
        url_for(
            "website_studio",
            bid=bid,
        )
    )


@app.route(
    "/client/<int:bid>/website/preview/select",
    methods=["POST"],
)
def select_website_preview(bid):
    raw_version = request.form.get(
        "version_id",
        "",
    ).strip()

    if not raw_version.isdigit():
        flash(
            "Choose a valid Website Studio version.",
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn = connect()

    business = conn.execute(
        "SELECT id FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        select_preview_version(
            conn,
            bid,
            int(raw_version),
        )

        synchronize_readiness(
            conn,
            bid,
        )

    except WebsiteVersionNotFound as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    flash(
        "Preview version selected. "
        "Nothing has been published.",
        "success",
    )

    return redirect(
        url_for(
            "website_studio",
            bid=bid,
        )
    )


@app.route("/client/<int:bid>/website/preview")
def website_preview(bid):
    conn = connect()

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        model = build_preview_render_model(
            conn,
            bid,
        )

    except WebsiteRenderNotFound as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    return render_template(
        "website_preview.html",
        business=business,
        site=model,
    )


@app.route("/client/<int:bid>/configuration/services", methods=["POST"])
def add_business_service(bid):
    ok, message = add_service(
        bid,
        request.form.get("name", ""),
        request.form.get("description", ""),
        public=request.form.get("public") == "1",
        bookable=request.form.get("bookable") == "1",
        requires_estimate=request.form.get("requires_estimate") == "1",
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("business_configuration", bid=bid))


@app.route("/client/<int:bid>/configuration/services/<int:service_id>/toggle", methods=["POST"])
def toggle_business_service(bid, service_id):
    ok, message = toggle_service(bid, service_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("business_configuration", bid=bid))


@app.route("/client/<int:bid>/configuration/intake", methods=["POST"])
def add_business_intake_question(bid):
    raw_service = request.form.get("service_id", "").strip()
    service_id = int(raw_service) if raw_service.isdigit() else None
    options = [x for x in request.form.get("options", "").splitlines()]
    ok, message = add_intake_question(
        bid,
        request.form.get("label", ""),
        request.form.get("question_type", "short_text"),
        required=request.form.get("required") == "1",
        service_id=service_id,
        options=options,
    )
    flash(message, "success" if ok else "error")
    return redirect(url_for("business_configuration", bid=bid))


@app.route("/client/<int:bid>/configuration/intake/<int:question_id>/toggle", methods=["POST"])
def toggle_business_intake_question(bid, question_id):
    ok, message = toggle_intake_question(bid, question_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("business_configuration", bid=bid))


@app.route("/attention")
def attention_center():
    raw = request.args.get("business_id", "").strip()
    business_id = int(raw) if raw.isdigit() else None
    conn = connect()
    ensure_product_schema(conn)
    items = attention_queue(conn, business_id=business_id, limit=75)
    conn.close()
    return render_template("attention_center.html", items=items, business_id=business_id)



@app.route("/control-plane")
def control_plane():
    conn=connect(); overview=control_plane_overview(conn); conn.close()
    return render_template("control_plane.html", control=overview)


@app.route("/system-map")
def system_map():
    conn=connect(); overview=control_plane_overview(conn); conn.close()
    return render_template("system_map.html", control=overview)


@app.route("/improvements")
def improvements():
    conn=connect(); overview=control_plane_overview(conn); conn.close()
    return render_template("improvements.html", control=overview)


@app.route("/improvements/<int:proposal_id>/review", methods=["POST"])
def review_improvement_proposal(proposal_id):
    status=request.form.get("status","").strip(); note=request.form.get("note","")
    if review_improvement(proposal_id,status,note):
        flash(f"Improvement proposal marked {status}. No system behavior was changed automatically.","success")
    else:
        flash("Improvement review was not saved.","error")
    return redirect(url_for("improvements"))

@app.route("/system-health")
def system_health():
    conn = connect()
    report = build_health_report(conn)
    reliability = reliability_dashboard(conn)
    latest_test = run_self_test(conn, persist=False)
    conn.close()
    return render_template(
        "system_health.html",
        report=report,
        reliability=reliability,
        latest_test=latest_test,
    )


@app.route("/system-health/run-check", methods=["POST"])
def run_reliability_check():
    conn = connect()
    result = run_self_test(conn, persist=True)
    conn.close()
    if result["failures"]:
        flash(f"Self-test found {result['failures']} release-blocking failure(s).", "error")
    elif result["warnings"]:
        flash(f"Self-test passed with {result['warnings']} warning(s) to review.", "success")
    else:
        flash("Full self-test passed.", "success")
    return redirect(url_for("system_health"))


@app.route("/system-health/snapshot", methods=["POST"])
def create_system_snapshot():
    try:
        snapshot = create_database_snapshot("Manual health-center snapshot")
    except Exception as exc:
        record_system_event("Database snapshot failed", str(exc), severity="Error", event_type="Recovery")
        flash(f"Snapshot failed: {exc}", "error")
    else:
        flash(f"Recovery snapshot created: {snapshot['filename']}", "success")
    return redirect(url_for("system_health"))


@app.route("/schedule")
def schedule():
    conn = connect()
    raw_business = request.args.get("business_id", "").strip()
    business_id = int(raw_business) if raw_business.isdigit() else None
    where = "WHERE appointments.business_id = ?" if business_id is not None else ""
    args = (business_id,) if business_id is not None else ()
    rows = conn.execute(
        f"""
        SELECT appointments.*, leads.caller_name, leads.phone, businesses.name AS business_name
        FROM appointments
        LEFT JOIN leads ON leads.id = appointments.lead_id
        LEFT JOIN businesses ON businesses.id = appointments.business_id
        {where}
        ORDER BY appointments.start_at ASC
        """,
        args,
    ).fetchall()
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone() if business_id is not None else None
    conn.close()
    return render_template("schedule.html", schedule=appointment_state(rows), business=business, business_id=business_id)


@app.route("/automation")
def automation_center():
    conn = connect()
    ensure_execution_schema(conn)
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
    actions = conn.execute(
        """
        SELECT actions.*, leads.caller_name, businesses.name AS business_name
        FROM actions
        LEFT JOIN leads ON leads.id = actions.lead_id
        LEFT JOIN businesses ON businesses.id = actions.business_id
        ORDER BY actions.id DESC
        LIMIT 40
        """
    ).fetchall()
    action_stats = {
        "succeeded": sum(1 for row in actions if row["status"] == "SUCCEEDED"),
        "attention": sum(1 for row in actions if row["status"] in {"UNKNOWN", "FAILED_PERMANENT"}),
        "pending_outcome": sum(1 for row in actions if row["status"] == "ACCEPTED_PENDING_OUTCOME"),
        "retry_scheduled": sum(1 for row in actions if row["status"] == "RETRY_SCHEDULED"),
    }
    stats = {
        "pending": len(pending),
        "ready": len(ready),
        "successful": action_stats["succeeded"],
        "blocked": sum(1 for row in actions if row["status"] == "BLOCKED"),
    }
    conn.close()
    return render_template(
        "automation.html", pending=pending, ready=ready, recent=recent,
        executions=executions, actions=actions, action_stats=action_stats, stats=stats,
        execution_mode="Simulation", live_actions_enabled=live_actions_enabled()
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
    if not lead["business_id"]:
        conn.close()
        flash("Assign this lead to a client before preparing customer communication.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    owner = conn.execute(
        "SELECT id, lifecycle_stage FROM businesses WHERE id = ?", (lead["business_id"],)
    ).fetchone()
    if owner is None or (owner["lifecycle_stage"] or "").upper() in {"PROSPECT", "QUALIFIED", "PAUSED", "CANCELLED"}:
        conn.close()
        flash("This lead is not attached to an automation-eligible client lifecycle. Messaging is locked.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    if (lead["quarantine_status"] or "") == "Open":
        conn.close()
        flash("This lead is quarantined. Resolve ownership before preparing communication.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    classification = (lead["data_classification"] or "LEGACY").upper()
    if classification not in {"TEST", "DEMO", "PRODUCTION"}:
        conn.close()
        flash(f"{classification} data is not messaging-eligible.", "error")
        return redirect(url_for("lead_detail", lead_id=lead_id))
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO outbound_messages
            (business_id, lead_id, channel, recipient, body, status, automation_key,
             created_at, data_classification, quarantine_status, quarantine_reason)
        VALUES (?, ?, 'SMS', ?, ?, 'Pending Approval', 'manual_follow_up', ?, ?, 'Not Required', '')
        """,
        (lead["business_id"], lead_id, lead["phone"], body, timestamp, classification),
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
    # Approval uses the same tenant/recipient guardrails as execution.
    original_status = message["status"]
    conn.execute("UPDATE outbound_messages SET status = 'Approved' WHERE id = ?", (message_id,))
    staged = conn.execute("SELECT * FROM outbound_messages WHERE id = ?", (message_id,)).fetchone()
    valid, reason = validate_sms_message(conn, staged)
    conn.execute("UPDATE outbound_messages SET status = ? WHERE id = ?", (original_status, message_id))
    if not valid:
        conn.commit()
        conn.close()
        flash("Approval blocked: " + reason, "error")
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


@app.errorhandler(500)
def internal_server_error(error):
    incident_id = None
    try:
        incident_id = record_system_event(
            "Unhandled application error",
            str(error),
            severity="Error",
            event_type="Runtime",
        )
    except Exception:
        pass
    return render_template("500.html", incident_id=incident_id), 500


@app.errorhandler(404)
def page_not_found(error):
    return (
        render_template("404.html"),
        404,
    )


if __name__ == "__main__":
    init_db()
    conn = connect()
    ensure_product_schema(conn)
    ensure_business_config_schema(conn)
    ensure_front_office_schema(conn)
    ensure_control_plane_schema(conn)
    ensure_execution_schema(conn)
    ensure_v13_schema(conn)
    ensure_upgrade_schema(conn)
    conn.close()
    print(f"Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}")
    print(f"Project root: {os.path.dirname(os.path.abspath(__file__))}")
    try:
        ensure_daily_snapshot()
    except Exception as exc:
        # Backup failure should be visible, but must not prevent local startup.
        print(f"Business OS backup warning: {exc}")

    debug_mode = os.getenv("BUSINESS_OS_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    try:
        local_port = int(os.getenv("BUSINESS_OS_PORT", "5000"))
    except ValueError:
        local_port = 5000
    if not 1 <= local_port <= 65535:
        local_port = 5000
    app.run(
        debug=debug_mode,
        port=local_port,
    )
