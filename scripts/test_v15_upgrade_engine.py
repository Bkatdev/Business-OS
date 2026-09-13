from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.v15_site_intelligence import CAPABILITIES, ensure_intelligence_schema
from services.v15_upgrade_engine import (
    build_upgrade_blueprint,
    ensure_upgrade_schema,
    record_owner_verification,
    upgrade_workspace_view,
)


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            website TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Researching',
            lifecycle_stage TEXT NOT NULL DEFAULT 'PROSPECT',
            automation_enabled INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.executemany(
        "INSERT INTO businesses(id,name,category,city,website,phone,email) VALUES (?,?,?,?,?,?,?)",
        [
            (1, "Acme Tree Care", "Tree Care", "East Brunswick", "https://acme.test", "732-555-0100", ""),
            (2, "Other Salon", "Hair Salon", "Marlboro", "https://other.test", "", ""),
        ],
    )
    ensure_intelligence_schema(conn)
    ensure_upgrade_schema(conn)
    return conn


def seed_run(conn, business_id, url, *, two_phones=False):
    cur = conn.execute(
        """
        INSERT INTO site_intelligence_runs(
            business_id,requested_url,canonical_url,status,pages_discovered,pages_analyzed,
            evidence_count,asset_count,started_at,completed_at
        ) VALUES (?,?,?,'COMPLETED',3,3,6,1,'2026-09-13T01:00:00','2026-09-13T01:00:02')
        """, (business_id, url, url),
    )
    run_id = cur.lastrowid
    evidence = [
        ("CONTACT_PHONE", "732-555-0100", "Call now", "high"),
        ("CONTACT_PHONE", "(732) 555-0100", "Footer phone", "high"),
        ("HEADING", "Tree Removal", url + "/services", "medium"),
        ("HEADING", "Tree Trimming", url + "/services", "medium"),
        ("CTA", "Contact us", "/contact", "medium"),
    ]
    if two_phones:
        evidence.append(("CONTACT_PHONE", "732-555-0199", "Alternate phone", "high"))
    for kind, value, excerpt, confidence in evidence:
        conn.execute(
            """
            INSERT INTO site_intelligence_evidence(
                run_id,business_id,page_url,evidence_type,normalized_value,excerpt,confidence,observed_at
            ) VALUES (?,?,?,?,?,?,?,'2026-09-13T01:00:02')
            """, (run_id,business_id,url,kind,value,excerpt,confidence),
        )
    conn.execute(
        """
        INSERT INTO site_asset_observations(
            run_id,business_id,page_url,asset_url,asset_type,alt_text,observed_at
        ) VALUES (?,?,?,?,?,?,?)
        """, (run_id,business_id,url,url + "/crew.jpg","IMAGE","Crew","2026-09-13T01:00:02"),
    )
    present = {"PHONE_CONTACT", "GENERAL_CONTACT_FORM", "REVIEW_DISPLAY"}
    for key in CAPABILITIES:
        state = "PRESENT" if key in present else ("UNKNOWN" if key == "LEAD_ACKNOWLEDGMENT" else "NOT_DETECTED")
        conn.execute(
            """
            INSERT INTO site_capability_observations(
                run_id,business_id,capability_key,observed_state,confidence,evidence_count,rationale,observed_at
            ) VALUES (?,?,?,?,?,?,?,'2026-09-13T01:00:02')
            """, (run_id,business_id,key,state,"high" if state == "PRESENT" else "medium",2 if state == "PRESENT" else 0,
                  "Observed on public site." if state == "PRESENT" else "Not detected across 3 analyzed public pages."),
        )
    conn.commit()
    return run_id


conn = setup()
seed_run(conn, 1, "https://acme.test", two_phones=True)

before = dict(conn.execute(
    "SELECT name,category,city,website,phone,email,status,lifecycle_stage,automation_enabled FROM businesses WHERE id=1"
).fetchone())
first = build_upgrade_blueprint(conn, 1)
after = dict(conn.execute(
    "SELECT name,category,city,website,phone,email,status,lifecycle_stage,automation_enabled FROM businesses WHERE id=1"
).fetchone())

check("blueprint generation does not mutate prospect or production state", before == after)
check("tree care selects field-estimate relevance", first["blueprint"]["industry_profile"] == "FIELD_ESTIMATE")
check("conflicting public phones fail closed", next(c for c in first["claims"] if c["claim_key"] == "CONTACT_PHONE")["truth_state"] == "CONFLICT")
check("conflict creates an owner-verification item", any("phone" in i["title"] for i in first["items"]["VERIFY"]))
check("missing estimate path becomes a focused addition", any(i["subject_key"] == "ESTIMATE_REQUEST" for i in first["items"]["ADD"]))
check("missing photo upload is relevant to field estimates", any(i["subject_key"] == "PHOTO_UPLOAD" for i in first["items"]["ADD"]))
check("generic form creates a structured-form improvement", any(i["subject_key"] == "CONTACT_TO_ESTIMATE" for i in first["items"]["IMPROVE"]))
check("live booking is not blindly recommended to tree care", not any(i["subject_key"] == "LIVE_BOOKING" for i in first["items"]["ADD"]))
check("present direct phone path is preserved", any(i["subject_key"] == "PHONE_CONTACT" for i in first["items"]["KEEP"]))

old_blueprint_id = first["blueprint"]["id"]
second = record_owner_verification(
    conn, 1, claim_key="CONTACT_PHONE", decision="CONFIRMED",
    confirmed_value="732-555-0100", note="Owner confirmed during demo.",
)
confirmed = next(c for c in second["claims"] if c["claim_key"] == "CONTACT_PHONE")
check("owner confirmation wins without editing public evidence", confirmed["truth_state"] == "OWNER_CONFIRMED")
check("resolved claim leaves the verification queue", not confirmed["requires_owner_verification"])
check("verification creates a new immutable blueprint version", second["blueprint"]["id"] != old_blueprint_id and second["history_count"] == 2)
old = upgrade_workspace_view(conn, 1, blueprint_id=old_blueprint_id)
check("prior blueprint remains unchanged", next(c for c in old["claims"] if c["claim_key"] == "CONTACT_PHONE")["truth_state"] == "CONFLICT")

seed_run(conn, 2, "https://other.test")
other = build_upgrade_blueprint(conn, 2)
check("appointment businesses use a different relevance profile", other["blueprint"]["industry_profile"] == "APPOINTMENT_SERVICE")
check("tenant-scoped blueprint lookup refuses another business id", upgrade_workspace_view(conn, 2, blueprint_id=old_blueprint_id)["blueprint"] is None)
check("tenant rows remain isolated", all(row["business_id"] == 1 for row in first["gaps"]) and all(row["business_id"] == 2 for row in other["gaps"]))

for kwargs in (
    {"claim_key": "DROP_TABLE", "decision": "CONFIRMED", "confirmed_value": "x"},
    {"claim_key": "BUSINESS_NAME", "decision": "MAYBE", "confirmed_value": "x"},
    {"claim_key": "BUSINESS_NAME", "decision": "CONFIRMED", "confirmed_value": ""},
):
    try:
        record_owner_verification(conn, 1, **kwargs)
        raise AssertionError("malformed verification was accepted")
    except ValueError:
        pass
check("malformed verification input fails closed", True)

source = (ROOT / "services" / "v15_upgrade_engine.py").read_text(encoding="utf-8").lower()
check("upgrade engine contains no provider execution path", all(token not in source for token in ("execute_sms", "send_sms", "publish_site", "create_appointment")))
print("ALL V15 UPGRADE ENGINE TESTS PASSED")
