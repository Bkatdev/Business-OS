from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.db as db
from services.v14_sales_workspace import save_conversion_draft, convert_to_onboarding
from services.website_studio import get_or_create_project
from services.website_versions import get_current_version, select_preview_version
from services.v14_delivery import (
    ensure_delivery_schema, delivery_readiness, create_local_release,
    active_release_by_slug, issue_form_nonce, submit_public_intake,
)
from services.v14_production_site import generate_design


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


with tempfile.TemporaryDirectory() as td:
    db.DB_PATH = Path(td) / "delivery-test.db"
    db.init_db()
    con = db.connect()
    con.execute(
        """INSERT INTO businesses(name,city,category,reviews,rating,website,phone,email,status,created_at,audit_status,lifecycle_stage,automation_enabled)
           VALUES ('Prospect Co','Trenton','Plumbing',80,4.7,'https://public.example','609-555-0000','', 'Proposal',?,'completed','PROSPECT',0)""",
        (db.now_iso(),),
    )
    bid = con.execute("SELECT id FROM businesses WHERE name='Prospect Co'").fetchone()[0]
    con.commit()

    owner = {
        "owner_name": "Pat Owner", "verified_business_name": "Pat's Plumbing LLC",
        "verified_industry": "Plumbing", "verified_phone": "609-555-0111",
        "verified_email": "pat@example.com", "services": "Drain cleaning\nWater heater repair",
        "business_hours": "Mon-Fri 8-5", "service_area": "Mercer County",
        "emergency_rules": "Escalate gas, fire, flooding, or safety emergencies.",
        "escalation_instructions": "Call Pat for urgent exceptions.",
        "scheduling_policy": "Collect preferred times; owner confirms appointments.",
        "messaging_tone": "Professional, warm, concise", "onboarding_notes": "Test conversion",
    }
    save_conversion_draft(con, business_id=bid, values=owner)
    ok, _ = convert_to_onboarding(con, business_id=bid)
    check("verified prospect converts to onboarding", ok)
    check("conversion keeps automation disabled", con.execute("SELECT automation_enabled FROM businesses WHERE id=?", (bid,)).fetchone()[0] == 0)
    services = con.execute("SELECT name,public,active FROM business_services WHERE business_id=? ORDER BY id", (bid,)).fetchall()
    check("owner-verified services materialize into structured truth", [r["name"] for r in services] == ["Drain cleaning", "Water heater repair"])
    check("materialized services are public and active", all(r["public"] and r["active"] for r in services))
    schema = con.execute("SELECT * FROM intake_schemas WHERE business_id=?", (bid,)).fetchone()
    check("conversion activates default intake schema", schema is not None and schema["status"] == "Active")

    project = get_or_create_project(con, bid)
    current = get_current_version(con, bid)
    select_preview_version(con, bid, current["id"])
    generate_design(con, bid, "Professional local service company. Clear, trustworthy, conversion-focused.")
    ready = delivery_readiness(con, bid)
    check("delivery gate passes only after owner truth + selected preview + matching production design", ready["ready"])

    release = create_local_release(con, bid)
    check("local immutable release becomes active", release["status"] == "ACTIVE" and release["is_active"] == 1)
    check("local release does not use external provider", release["provider"] == "business_os_local_delivery")
    public = active_release_by_slug(con, release["public_slug"])
    check("public slug resolves exactly one active tenant release", public and public["business_id"] == bid)
    check("frozen artifact contains owner-verified identity", public["artifact"]["business"]["name"] == "Pat's Plumbing LLC")
    check("frozen artifact contains structured services", len(public["artifact"]["services"]) == 2)
    check("frozen artifact is production design schema v2", public["artifact"]["schema_version"] == 2 and public["artifact"]["artifact_kind"] == "PRODUCTION_SITE")
    check("frozen artifact includes validated design blueprint", bool(public["artifact"].get("blueprint", {}).get("layout_family")))

    nonce = issue_form_nonce(con, release["id"])
    result = submit_public_intake(
        con, slug=release["public_slug"], nonce=nonce, idempotency_key="submit-1",
        values={"name":"Jamie Customer","phone":"609-555-0222","email":"jamie@example.com",
                "address":"1 Main St","service":"Drain cleaning","message":"Kitchen drain is backing up",
                "preferred_time":"Tomorrow afternoon","company_website":""},
    )
    check("valid website request creates canonical lead", result["status"] == "ACCEPTED" and result["lead_id"])
    lead = con.execute("SELECT * FROM leads WHERE id=?", (result["lead_id"],)).fetchone()
    check("website lead is tenant-bound", lead["business_id"] == bid)
    check("website lead source is explicit", lead["source"] == "Website")
    check("website lead preserves request data", lead["service_type"] == "Drain cleaning" and "backing up" in lead["issue_description"])
    check("public intake never schedules automatically", lead["appointment_status"] == "Not Scheduled")
    check("public intake never enables automation", con.execute("SELECT automation_enabled FROM businesses WHERE id=?", (bid,)).fetchone()[0] == 0)

    replay = submit_public_intake(
        con, slug=release["public_slug"], nonce="anything", idempotency_key="submit-1",
        values={"name":"changed"},
    )
    check("same idempotency key cannot create duplicate lead", replay["status"] == "IDEMPOTENT_REPLAY" and replay["lead_id"] == result["lead_id"])
    check("idempotent replay leaves exactly one lead", con.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,)).fetchone()[0] == 1)

    nonce2 = issue_form_nonce(con, release["id"])
    dupe = submit_public_intake(
        con, slug=release["public_slug"], nonce=nonce2, idempotency_key="submit-2",
        values={"name":"Jamie Customer","phone":"609-555-0222","email":"jamie@example.com",
                "address":"1 Main St","service":"Drain cleaning","message":"Kitchen drain is backing up",
                "preferred_time":"Tomorrow afternoon","company_website":""},
    )
    check("double-click style repeat is recorded as duplicate", dupe["status"] == "DUPLICATE" and dupe["lead_id"] == result["lead_id"])
    check("fingerprint duplicate still leaves one canonical lead", con.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,)).fetchone()[0] == 1)

    nonce3 = issue_form_nonce(con, release["id"])
    bad_service = submit_public_intake(
        con, slug=release["public_slug"], nonce=nonce3, idempotency_key="submit-3",
        values={"name":"Eve","phone":"609-555-0333","email":"", "service":"Roof replacement","message":"x","company_website":""},
    )
    check("service not in frozen tenant release fails closed", bad_service["status"] == "REJECTED")
    check("rejected submission creates no lead", con.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,)).fetchone()[0] == 1)

    nonce4 = issue_form_nonce(con, release["id"])
    bot = submit_public_intake(
        con, slug=release["public_slug"], nonce=nonce4, idempotency_key="submit-4",
        values={"name":"Bot","phone":"1","service":"Drain cleaning","company_website":"https://spam.example"},
    )
    check("honeypot submission is rejected", bot["status"] == "REJECTED")

    # A second tenant must never accept the first tenant's service/release identity.
    con.execute("INSERT INTO businesses(name,city,category,status,created_at,lifecycle_stage,automation_enabled) VALUES ('Other Co','Camden','Roofing','Client',?,'ONBOARDING',0)", (db.now_iso(),))
    other = con.execute("SELECT id FROM businesses WHERE name='Other Co'").fetchone()[0]
    con.commit()
    check("release remains bound to original tenant", active_release_by_slug(con, release["public_slug"])["business_id"] != other)

    # Creating a new release retires the previous artifact without mutating it.
    from services.website_versions import update_presentation
    changed = update_presentation(con, bid, {"hero_headline":"A newly reviewed headline"}, expected_current_version_id=current["id"])
    select_preview_version(con, bid, changed["id"])
    generate_design(con, bid, "Updated reviewed production design")
    second = create_local_release(con, bid)
    check("new reviewed version creates a new release", second["id"] != release["id"])
    old = con.execute("SELECT is_active,artifact_sha256 FROM site_release_artifacts WHERE deployment_id=?", (release["id"],)).fetchone()
    check("old release is retired rather than overwritten", old["is_active"] == 0 and old["artifact_sha256"] == release["artifact_sha256"])
    check("old public slug stops resolving", active_release_by_slug(con, release["public_slug"]) is None)
    check("new public slug resolves", active_release_by_slug(con, second["public_slug"])["id"] == second["id"])

    # Database and safety invariants.
    check("foreign key check clean", con.execute("PRAGMA foreign_key_check").fetchall() == [])
    check("database integrity ok", con.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    con.close()

    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    env.get_template("delivery_center.html")
    env.get_template("public_site.html")
    check("delivery templates parse", True)

    import importlib.util
    if importlib.util.find_spec("flask") is not None:
        import app as app_module
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        center = client.get(f"/client/{bid}/delivery")
        check("delivery center route renders", center.status_code == 200 and b"CUSTOMER DELIVERY LOOP" in center.data)
        public_page = client.get(f"/site/{second['public_slug']}")
        check("customer site route renders", public_page.status_code == 200 and b"Request an estimate" in public_page.data and b"Send request" in public_page.data and b"BUSINESS OS LOCAL CUSTOMER TEST" not in public_page.data)

print("ALL V14 CUSTOMER DELIVERY LOOP TESTS PASSED")
