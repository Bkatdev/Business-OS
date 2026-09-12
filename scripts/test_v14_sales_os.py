from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.db as db
from services.v14_sales_workspace import (
    build_outreach_drafts,
    build_sales_workspace,
    complete_followup,
    conversion_readiness,
    convert_to_onboarding,
    ensure_sales_schema,
    log_sales_interaction,
    save_conversion_draft,
)


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


with tempfile.TemporaryDirectory() as td:
    db.DB_PATH = Path(td) / "sales-test.db"
    db.init_db()
    con = db.connect()
    con.execute(
        """
        INSERT INTO businesses(
            name,city,category,reviews,rating,website,phone,email,status,created_at,
            audit_status,lifecycle_stage,automation_enabled
        ) VALUES ('Alpha HVAC','Newark','HVAC',180,4.8,'https://alpha.example','973-555-0101','',
                  'Not Contacted',?,'completed','PROSPECT',0)
        """,
        (db.now_iso(),),
    )
    bid = con.execute("SELECT id FROM businesses WHERE name='Alpha HVAC'").fetchone()[0]
    con.execute(
        """
        INSERT INTO website_concepts(
            business_id,concept_number,status,truth_state,generation_mode,creative_brief,blueprint_json,created_at
        ) VALUES (?,1,'DRAFT','PUBLIC_UNVERIFIED','CONTEXT_DIRECTOR_V1','','{}',?)
        """,
        (bid, db.now_iso()),
    )
    con.commit()

    ensure_sales_schema(con)
    drafts = build_outreach_drafts(dict(con.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()), concept_count=1)
    check("outreach draft states a private concept exists", "built a private website concept" in drafts["email_body"])
    check("outreach draft does not claim lost revenue", "lost revenue" not in drafts["email_body"].lower())

    status = log_sales_interaction(
        con,
        business_id=bid,
        interaction_type="OUTREACH",
        channel="EMAIL",
        summary="Sent private concept invitation.",
        follow_up_at="2099-01-02T10:00",
        follow_up_reason="Follow up if no reply",
    )
    check("outreach advances pipeline to Contacted", status == "Contacted")
    check("business status persisted", con.execute("SELECT status FROM businesses WHERE id=?", (bid,)).fetchone()[0] == "Contacted")
    follow = con.execute("SELECT * FROM sales_followups WHERE business_id=?", (bid,)).fetchone()
    check("follow-up created", follow is not None and follow["status"] == "OPEN")
    check("follow-up completion tenant-safe", complete_followup(con, business_id=bid, followup_id=follow["id"]))
    check("follow-up marked done", con.execute("SELECT status FROM sales_followups WHERE id=?", (follow["id"],)).fetchone()[0] == "DONE")

    ws = build_sales_workspace(con, bid)
    check("workspace has deterministic battle card", ws["sales"]["recommended_plan"] in {"Website", "Front Office"})
    check("workspace exposes concept", ws["concept_count"] == 1)
    check("workspace contains interaction history", len(ws["interactions"]) == 1)

    incomplete = {
        "verified_phone": "973-555-0101",
        "services": "Heating repair",
    }
    check("incomplete owner verification is blocked", not conversion_readiness(incomplete)["ready"])

    owner_verified = {
        "owner_name": "Owner",
        "verified_business_name": "Alpha HVAC LLC",
        "verified_industry": "HVAC",
        "verified_phone": "973-555-0199",
        "verified_email": "owner@alpha.example",
        "services": "Heating repair\nAC repair",
        "business_hours": "Mon-Fri 8am-5pm",
        "service_area": "Newark and nearby Essex County",
        "emergency_rules": "Do not provide emergency instructions; escalate urgent gas or safety concerns.",
        "escalation_instructions": "Call the owner for urgent exceptions.",
        "scheduling_policy": "Requests only until owner approves live scheduling.",
        "messaging_tone": "Professional, warm, concise",
        "onboarding_notes": "Owner verified during kickoff.",
    }
    save_conversion_draft(con, business_id=bid, values=owner_verified)
    record = dict(con.execute("SELECT * FROM prospect_conversion_records WHERE business_id=?", (bid,)).fetchone())
    check("complete owner verification is ready", conversion_readiness(record)["ready"])

    ok, message = convert_to_onboarding(con, business_id=bid)
    check("conversion succeeds only after verification", ok)
    converted = con.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    check("conversion enters ONBOARDING", converted["status"] == "Client" and converted["lifecycle_stage"] == "ONBOARDING")
    check("conversion keeps automation disabled", int(converted["automation_enabled"] or 0) == 0)
    check("owner-verified identity replaces prospect identity", converted["name"] == "Alpha HVAC LLC" and converted["category"] == "HVAC")
    check("only owner-verified contact replaces public contact", converted["phone"] == "973-555-0199" and converted["email"] == "owner@alpha.example")
    profile = con.execute("SELECT * FROM client_profiles WHERE business_id=?", (bid,)).fetchone()
    check("owner-verified production profile created", profile is not None and "Heating repair" in profile["services"])
    owner_evidence = con.execute("SELECT COUNT(*) FROM evidence_records WHERE business_id=? AND evidence_kind='OWNER_VERIFIED'", (bid,)).fetchone()[0]
    check("owner verification records provenance", owner_evidence >= 7)
    con.close()

    # Template syntax smoke tests run even in environments without Flask.
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    env.get_template("sales_workspace.html")
    env.get_template("founder_command.html")
    check("sales and Founder HQ templates parse", True)

    # When Flask is installed (normal Business OS runtime), also exercise the
    # actual routes before an installer is allowed to touch the real repo.
    import importlib.util
    if importlib.util.find_spec("flask") is not None:
        import app as app_module
        app_module.app.config.update(TESTING=True)
        client = app_module.app.test_client()
        response = client.get(f"/business/{bid}/sales")
        check("sales workspace route renders", response.status_code == 200 and b"BATTLE CARD" in response.data)
        founder = client.get("/founder")
        check("Founder HQ route renders with sales metrics", founder.status_code == 200 and b"Follow-ups due" in founder.data)

print("All v14 sales operating system checks passed.")
