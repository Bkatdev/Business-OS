from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.db as db
from services.v14_sales_workspace import save_conversion_draft, convert_to_onboarding
from services.website_studio import get_or_create_project
from services.website_versions import get_current_version, select_preview_version
from services.v14_production_site import generate_design
from services.v14_delivery import (
    create_local_release,
    active_release_by_slug,
    issue_form_nonce,
    submit_public_intake,
)
from services.v14_client_experience import owner_preview_state
from services.v14_acceptance import acceptance_state


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


with tempfile.TemporaryDirectory() as td:
    db.DB_PATH = Path(td) / "v14-rc.db"
    db.init_db()
    con = db.connect()
    con.execute(
        """INSERT INTO businesses(name,city,category,reviews,rating,website,phone,email,status,created_at,audit_status,lifecycle_stage,automation_enabled)
           VALUES ('RC Prospect','East Brunswick','Tree Care',0,0,'','732-555-0100','', 'Proposal',?,'completed','PROSPECT',0)""",
        (db.now_iso(),),
    )
    bid = con.execute("SELECT id FROM businesses WHERE name='RC Prospect'").fetchone()[0]
    con.commit()

    owner = {
        "owner_name": "Ben Test",
        "verified_business_name": "Ben's Test Tree Care",
        "verified_industry": "Tree Care",
        "verified_phone": "732-555-0100",
        "verified_email": "owner@testtreecare.example",
        "services": "Tree Removal\nTree Trimming\nStump Grinding\nStorm Cleanup",
        "business_hours": "Monday-Friday 8:00 AM-6:00 PM\nSaturday 9:00 AM-3:00 PM\nSunday Closed",
        "service_area": "East Brunswick, NJ\nOld Bridge, NJ\nMarlboro, NJ\nMonroe Township, NJ",
        "emergency_rules": "Escalate utility-line, electrical, or immediate safety hazards to the owner.",
        "escalation_instructions": "Contact the owner for urgent safety issues or decisions Business OS cannot make.",
        "scheduling_policy": "Collect preferred times; owner confirms appointments.",
        "messaging_tone": "Friendly, professional, concise, and helpful.",
        "onboarding_notes": "Release candidate acceptance fixture.",
    }
    save_conversion_draft(con, business_id=bid, values=owner)
    converted, _ = convert_to_onboarding(con, business_id=bid)
    check(
        "fixture converts to ONBOARDING without enabling automation",
        converted
        and con.execute("SELECT automation_enabled FROM businesses WHERE id=?", (bid,)).fetchone()[0] == 0,
    )

    get_or_create_project(con, bid)
    current = get_current_version(con, bid)
    select_preview_version(con, bid, current["id"])
    generate_design(
        con,
        bid,
        "Premium, rugged, trustworthy local tree-care company. Strong visual hierarchy and an obvious estimate path.",
    )
    release = create_local_release(con, bid)
    frozen = active_release_by_slug(con, release["public_slug"])
    check(
        "customer release freezes production design schema",
        frozen["artifact"]["artifact_kind"] == "PRODUCTION_SITE"
        and frozen["artifact"]["schema_version"] == 2,
    )
    check(
        "fake .example email is suppressed from production customer artifact",
        frozen["artifact"].get("public_email") == "",
    )
    check(
        "service areas are semantic items",
        frozen["artifact"].get("service_areas")
        == ["East Brunswick, NJ", "Old Bridge, NJ", "Marlboro, NJ", "Monroe Township, NJ"],
    )
    check("frozen release carries validated blueprint", bool(frozen["artifact"].get("blueprint", {}).get("layout_family")))

    # A second tenant proves that every owner/operator scoped view stays isolated.
    con.execute(
        "INSERT INTO businesses(name,city,category,status,created_at,lifecycle_stage,automation_enabled) VALUES ('Other Client','Camden','Roofing','Client',?,'ONBOARDING',0)",
        (db.now_iso(),),
    )
    other = con.execute("SELECT id FROM businesses WHERE name='Other Client'").fetchone()[0]
    con.execute(
        "INSERT INTO leads(business_id,caller_name,phone,service_type,status,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (other, "Other Tenant Person", "856-555-9999", "Roofing", "New", "Website", db.now_iso(), db.now_iso()),
    )
    con.commit()

    for tab in ("today", "leads", "calls", "schedule", "website", "settings"):
        portal = owner_preview_state(con, bid, tab=tab)
        check(f"owner {tab} tab read model is functional", portal["tab"] == tab and portal["business"]["id"] == bid)
        check(
            f"owner {tab} tab remains tenant-scoped",
            all(int(item["business_id"]) == bid for item in portal.get("leads", []))
            and all(int(item["business_id"]) == bid for item in portal.get("calls", []))
            and all(int(item["business_id"]) == bid for item in portal.get("appointments", [])),
        )
    check("unknown owner tab fails closed to Today", owner_preview_state(con, bid, tab="bogus")["tab"] == "today")

    lab = acceptance_state(con, bid)
    check("three-persona acceptance state is ready", lab["ready_for_full_journey"])
    check("acceptance state sees active local release", lab["active_release"] and lab["active_release"]["public_slug"] == release["public_slug"])

    nonce = issue_form_nonce(con, release["id"])
    intake = submit_public_intake(
        con,
        slug=release["public_slug"],
        nonce=nonce,
        idempotency_key="rc-journey-1",
        values={
            "name": "Jamie Homeowner",
            "phone": "732-555-0222",
            "email": "jamie@example.com",
            "address": "1 Test Lane",
            "service": "Tree Removal",
            "preferred_time": "Tomorrow afternoon",
            "message": "Large tree needs an estimate.",
            "company_website": "",
        },
    )
    check("customer persona creates canonical lead", intake["status"] == "ACCEPTED" and intake["lead_id"])
    lead = con.execute("SELECT * FROM leads WHERE id=?", (intake["lead_id"],)).fetchone()
    check("customer lead is tenant-bound and unscheduled", lead["business_id"] == bid and lead["appointment_status"] == "Not Scheduled")
    check("customer journey does not enable automation", con.execute("SELECT automation_enabled FROM businesses WHERE id=?", (bid,)).fetchone()[0] == 0)
    owner_leads = owner_preview_state(con, bid, tab="leads")
    check("new customer lead appears in owner read model", any(x["caller_name"] == "Jamie Homeowner" for x in owner_leads["leads"]))
    con.close()

    # Static/template contracts are always testable, even in build containers that
    # do not have Flask installed. The installer runs the full route checks on the
    # user's application environment where Flask is already required by app.py.
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    for name in [
        "base.html",
        "_client_workspace_nav.html",
        "client_acceptance_lab.html",
        "client_portal_preview.html",
        "production_site_preview.html",
        "public_site.html",
        "delivery_center.html",
        "leads.html",
        "calls.html",
        "schedule.html",
        "system_health.html",
    ]:
        env.get_template(name)
    check("release-candidate templates parse", True)

    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    check(
        "operator primary nav is five-concept mental model",
        all(f">{label}<" in base for label in ["Home", "Sales", "Clients", "Attention", "System"]),
    )
    check(
        "engineering tools are not permanent top-level nav",
        '<span class="nav-label">Automation</span>' not in base
        and '<span class="nav-label">Control Plane</span>' not in base,
    )
    owner_tpl = (ROOT / "templates" / "client_portal_preview.html").read_text(encoding="utf-8")
    for label in ["Today", "Leads", "Calls", "Schedule", "Website", "Settings"]:
        check(f"owner navigation includes functional {label} tab", f"'{label.lower() if label != 'Today' else 'today'}'" in owner_tpl or f">{label}<" in owner_tpl)
    check("owner portal excludes operator concepts", "Founder HQ" not in owner_tpl and "Prospects" not in owner_tpl and "Control Plane" not in owner_tpl)

    public_tpl = (ROOT / "templates" / "public_site.html").read_text(encoding="utf-8")
    shared = (ROOT / "templates" / "_production_site_body.html").read_text(encoding="utf-8")
    check("production preview and customer release share one body renderer", "_production_site_body.html" in public_tpl and "customer-form" in shared)
    check("old v12 public renderer is no longer the release surface", "v12-public" not in public_tpl and "v12.css" not in public_tpl)

    app_src = (ROOT / "app.py").read_text(encoding="utf-8")
    check("acceptance lab and owner tab routes are wired", "def client_acceptance_lab" in app_src and 'request.args.get("tab", "today")' in app_src)
    check("operator client list routes accept tenant filter", app_src.count('request.args.get("business_id", "").strip()') >= 3)

    # When Flask is available (normal Business OS runtime), run the literal route
    # journey too. This makes the installer fail/rollback on user machines if
    # links or route names drift even when pure service tests pass.
    if importlib.util.find_spec("flask") is not None:
        import app as app_module

        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        check("operator client overview route renders", client.get(f"/client/{bid}").status_code == 200)
        lab_page = client.get(f"/client/{bid}/acceptance")
        check("Acceptance Lab route renders", lab_page.status_code == 200 and b"THREE-PERSONA WORKING MODEL" in lab_page.data)
        for tab, marker in {
            "today": b"Here\xe2\x80\x99s what\xe2\x80\x99s happening.",
            "leads": b"Customer opportunities.",
            "calls": b"Calls and conversations.",
            "schedule": b"Your schedule.",
            "website": b"Your customer front door.",
            "settings": b"Business settings.",
        }.items():
            response = client.get(f"/client/{bid}/owner-preview?tab={tab}")
            check(f"owner {tab} route renders", response.status_code == 200 and marker in response.data and b"Other Tenant Person" not in response.data)
        public_page = client.get(f"/site/{release['public_slug']}")
        check("customer site route uses production renderer", public_page.status_code == 200 and b"v14_production.css" in public_page.data and b"Send request" in public_page.data)
        route_nonce = re.search(rb'name="nonce" value="([^"]+)"', public_page.data)
        route_key = re.search(rb'name="idempotency_key" value="([^"]+)"', public_page.data)
        check("customer route issues anti-replay form state", bool(route_nonce and route_key))
        route_submit = client.post(
            f"/site/{release['public_slug']}/request",
            data={"nonce":route_nonce.group(1).decode(),"idempotency_key":route_key.group(1).decode(),"name":"Route Customer","phone":"732-555-0333","email":"route@example.com","address":"2 Test Lane","service":"Tree Trimming","preferred_time":"Friday morning","message":"Please review this trimming request.","company_website":""},
        )
        check("customer route POST creates a lead and renders success", route_submit.status_code == 200 and b"Request received." in route_submit.data)
        operator_leads = client.get(f"/leads?business_id={bid}")
        check("operator tenant-filtered Leads route hides other tenants", operator_leads.status_code == 200 and b"Jamie Homeowner" in operator_leads.data and b"Route Customer" in operator_leads.data and b"Other Tenant Person" not in operator_leads.data)
        check("operator tenant-filtered Calls route renders", client.get(f"/calls?business_id={bid}").status_code == 200)
        check("operator tenant-filtered Schedule route renders", client.get(f"/schedule?business_id={bid}").status_code == 200)
    else:
        print("INFO: Flask not installed in build container; full route journey is enforced by installer in the Business OS runtime environment.")

print("ALL V14 RELEASE CANDIDATE WORKFLOW TESTS PASSED")
