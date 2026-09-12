from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.platform_foundation import (
    create_deployment_record,
    ensure_platform_schema,
    record_evidence,
    record_usage,
)
from services.v14_discovery import discover as governed_discover
from services.founder_command import build_founder_command


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")
con.execute(
    """CREATE TABLE businesses (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Local Service Business',
    reviews INTEGER NOT NULL DEFAULT 0, rating REAL NOT NULL DEFAULT 0, website TEXT DEFAULT '', phone TEXT DEFAULT '', email TEXT DEFAULT '',
    online_booking INTEGER NOT NULL DEFAULT 0, emergency_service INTEGER NOT NULL DEFAULT 0, website_chat INTEGER NOT NULL DEFAULT 0,
    estimate_form INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Not Contacted', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '',
    audit_status TEXT DEFAULT 'not_audited', scheduling_mentioned INTEGER DEFAULT 0, lifecycle_stage TEXT NOT NULL DEFAULT 'PROSPECT', google_place_id TEXT DEFAULT ''
)"""
)
con.execute("CREATE TABLE website_concepts (id INTEGER PRIMARY KEY, business_id INTEGER NOT NULL)")
con.execute(
    "INSERT INTO businesses(id,name,city,category,reviews,rating,status,audit_status,lifecycle_stage) VALUES (1,'Alpha HVAC','Newark','HVAC',180,4.8,'Qualified','completed','PROSPECT')"
)
con.execute(
    "INSERT INTO businesses(id,name,city,category,reviews,rating,status,audit_status,lifecycle_stage) VALUES (2,'Beta Plumbing','Edison','Plumbing',20,4.2,'Not Contacted','not_audited','PROSPECT')"
)
ensure_platform_schema(con)
ensure_platform_schema(con)
check(
    "platform schema is idempotent",
    con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='usage_events'").fetchone()[0] == 1,
)

eid = record_evidence(
    con,
    business_id=1,
    fact_type="test_fact",
    evidence_kind="SYSTEM_MEASURED",
    summary="test",
)
check(
    "evidence is tenant-bound",
    con.execute("SELECT business_id FROM evidence_records WHERE id=?", (eid,)).fetchone()[0] == 1,
)
uid = record_usage(
    con,
    business_id=1,
    provider="simulation",
    capability="test",
    units=2,
    estimated_cost_usd=0.01,
)
check(
    "usage records measurable units",
    con.execute("SELECT units FROM usage_events WHERE id=?", (uid,)).fetchone()[0] == 2,
)

d1 = create_deployment_record(
    con,
    business_id=1,
    deployment_key="business:1:version:9",
    website_version_id=9,
)
d2 = create_deployment_record(
    con,
    business_id=1,
    deployment_key="business:1:version:9",
    website_version_id=9,
)
check("deployment identity is idempotent", d1["id"] == d2["id"] and d1["status"] == "DRAFT")

command = build_founder_command(con)
check(
    "founder command uses real prospect state",
    command["metrics"]["prospects"] == 2 and len(command["queue"]) == 2,
)
check(
    "audited prospect receives evidence-based priority",
    command["queue"][0]["business"]["id"] == 1,
)
check(
    "governed discovery exposes injectable provider boundary",
    "discover_fn" in governed_discover.__code__.co_varnames,
)

foundation = (ROOT / "services" / "platform_foundation.py").read_text(encoding="utf-8").lower()
for forbidden in (
    "publish_site(",
    "twilio",
    "retell.create",
    "business_os_live_actions_enabled=1",
):
    check(
        f"foundation does not unlock live provider behavior: {forbidden}",
        forbidden not in foundation,
    )

print("ALL V14 FOUNDATION TESTS PASSED")
