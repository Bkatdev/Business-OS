from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.execution_core import (
    ActionIntent,
    execute_action,
    live_actions_enabled,
    record_provider_event,
    reconcile_action_outcome,
)
from services.execution_schema import ensure_execution_schema
from services.providers.base import ProviderAdapter, ProviderResult
from services.version import VERSION, RELEASE_NAME, BUILD_ID

PASS = "PASS"
FAIL = "FAIL"
failures = 0


def check(name, condition, detail=""):
    global failures
    if condition:
        print(f"{PASS} · {name}" + (f" · {detail}" if detail else ""))
    else:
        failures += 1
        print(f"{FAIL} · {name}" + (f" · {detail}" if detail else ""))


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            lifecycle_stage TEXT NOT NULL,
            automation_enabled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            business_id INTEGER,
            data_classification TEXT NOT NULL,
            quarantine_status TEXT NOT NULL DEFAULT 'Not Required',
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );
        CREATE TABLE system_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'Info',
            source TEXT NOT NULL DEFAULT 'Business OS',
            business_id INTEGER,
            lead_id INTEGER,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            outcome TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
        CREATE TABLE policy_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            business_id INTEGER,
            lead_id INTEGER,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            context_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
        CREATE TABLE improvement_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL UNIQUE,
            severity TEXT NOT NULL DEFAULT 'Medium',
            area TEXT NOT NULL,
            title TEXT NOT NULL,
            observation TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Proposed',
            review_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute("INSERT INTO businesses VALUES (1, 'Demo One', 'DEMO', 0)")
    conn.execute("INSERT INTO businesses VALUES (2, 'Demo Two', 'DEMO', 0)")
    conn.execute("INSERT INTO leads VALUES (1, 1, 'DEMO', 'Not Required')")
    conn.execute("INSERT INTO leads VALUES (2, 2, 'DEMO', 'Not Required')")
    conn.execute("INSERT INTO businesses VALUES (3, 'Live Fixture', 'ACTIVE', 1)")
    conn.execute("INSERT INTO leads VALUES (3, 3, 'PRODUCTION', 'Not Required')")
    ensure_execution_schema(conn)
    conn.commit()
    return conn


def intent(**overrides):
    data = dict(
        action_type="SEND_SMS",
        business_id=1,
        lead_id=1,
        source_entity_type="outbound_message",
        source_entity_id=100,
        mode="simulation",
        approval_required=True,
        approval_reference="outbound_message:100",
        data_classification="DEMO",
        quarantine_status="Not Required",
        max_retries=3,
    )
    data.update(overrides)
    return ActionIntent(**data)


check("Version lineage", VERSION.startswith("v11.") and bool(RELEASE_NAME.strip()) and bool(BUILD_ID.strip()), f"{VERSION} · {RELEASE_NAME} · {BUILD_ID}")
check("Live gate defaults closed", not live_actions_enabled())

required_files = [
    ROOT / "services" / "execution_schema.py",
    ROOT / "services" / "execution_core.py",
    ROOT / "services" / "providers" / "base.py",
    ROOT / "services" / "providers" / "simulation.py",
    ROOT / "services" / "providers" / "registry.py",
    ROOT / "static" / "v11.css",
    ROOT / "ARCHITECTURE_V11.md",
]
check("Execution architecture files", all(path.exists() for path in required_files))

registry_text = (ROOT / "services" / "providers" / "registry.py").read_text(encoding="utf-8")
check("No live provider registered", "SimulationProvider" in registry_text and "ProviderUnavailable" in registry_text and "Twilio" not in registry_text)

conn = make_conn()
tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
check("Execution schema", {"actions", "action_attempts", "provider_events"}.issubset(tables))

payload = {"channel": "SMS", "recipient": "7325550101", "body": "Test only"}
first = execute_action(conn, intent(), payload, policy_allowed=True, policy_reason="Fixture policy allowed.")
second = execute_action(conn, intent(), payload, policy_allowed=True, policy_reason="Fixture policy allowed.")
check("Simulation succeeds through provider boundary", first.ok and first.status == "SUCCEEDED" and first.provider == "Simulation")
check("Action idempotency", second.deduplicated and second.action_id == first.action_id and conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 1)
check("Attempt idempotency", conn.execute("SELECT COUNT(*) FROM action_attempts WHERE action_id=?", (first.action_id,)).fetchone()[0] == 1)

cross = execute_action(
    conn,
    intent(source_entity_id=101, business_id=2, lead_id=1),
    {**payload, "body": "Cross tenant"},
    policy_allowed=True,
    policy_reason="Fixture policy allowed.",
)
check("Cross-tenant execution blocked", cross.status == "BLOCKED" and conn.execute("SELECT COUNT(*) FROM action_attempts WHERE action_id=?", (cross.action_id,)).fetchone()[0] == 0)

quarantined = execute_action(
    conn,
    intent(source_entity_id=102, quarantine_status="Open"),
    {**payload, "body": "Quarantined"},
    policy_allowed=True,
    policy_reason="Fixture policy allowed.",
)
check("Quarantine blocks provider execution", quarantined.status == "BLOCKED" and conn.execute("SELECT COUNT(*) FROM action_attempts WHERE action_id=?", (quarantined.action_id,)).fetchone()[0] == 0)

live = execute_action(
    conn,
    intent(source_entity_id=103, mode="live", business_id=3, lead_id=3, data_classification="PRODUCTION"),
    {**payload, "body": "Live must remain locked"},
    policy_allowed=True,
    policy_reason="Fixture policy allowed.",
)
check("Global live kill switch", live.status == "BLOCKED" and "BUSINESS_OS_LIVE_ACTIONS_ENABLED" in live.detail)

row1, duplicate1 = record_provider_event(
    conn, provider="Fixture", event_id="evt_same", event_type="delivered", provider_external_id="x1", payload={"a": 1}
)
row2, duplicate2 = record_provider_event(
    conn, provider="Fixture", event_id="evt_same", event_type="delivered", provider_external_id="x1", payload={"a": 1}
)
check("Provider event deduplication", not duplicate1 and duplicate2 and row1["id"] == row2["id"] and conn.execute("SELECT COUNT(*) FROM provider_events WHERE provider='Fixture' AND event_id='evt_same'").fetchone()[0] == 1)

# Provider exceptions become UNKNOWN; they are not blindly retried.
import services.execution_core as execution_core
original_provider_for = execution_core.provider_for

class ExplodingProvider(ProviderAdapter):
    name = "ExplodingFixture"
    def execute(self, *, action, payload):
        raise RuntimeError("ambiguous provider timeout")

execution_core.provider_for = lambda **kwargs: ExplodingProvider()
unknown = execute_action(
    conn,
    intent(source_entity_id=104),
    {**payload, "body": "Unknown outcome"},
    policy_allowed=True,
    policy_reason="Fixture policy allowed.",
)
check("Unknown outcome is fail-safe", unknown.status == "UNKNOWN")
unknown_row = conn.execute("SELECT * FROM actions WHERE id=?", (unknown.action_id,)).fetchone()
check("Unknown outcome is not blindly retried", not unknown_row["next_retry_at"])
reconciled = reconcile_action_outcome(conn, unknown.action_id, status="SUCCEEDED", detail="Late provider callback confirmed delivery.", provider_external_id="late-confirm-1")
check("Late outcome reconciliation", reconciled.ok and reconciled.status == "SUCCEEDED" and reconciled.provider_external_id == "late-confirm-1")
reconciled_again = reconcile_action_outcome(conn, unknown.action_id, status="FAILED_PERMANENT", detail="Out-of-order failure")
check("Confirmed success is monotonic", reconciled_again.status == "SUCCEEDED" and reconciled_again.deduplicated)

class RetryableProvider(ProviderAdapter):
    name = "RetryFixture"
    def execute(self, *, action, payload):
        return ProviderResult(outcome="FAILED", detail="temporary outage", retryable=True, error_class="TEMPORARY")

execution_core.provider_for = lambda **kwargs: RetryableProvider()
retry = execute_action(
    conn,
    intent(source_entity_id=105),
    {**payload, "body": "Retryable failure"},
    policy_allowed=True,
    policy_reason="Fixture policy allowed.",
)
retry_row = conn.execute("SELECT * FROM actions WHERE id=?", (retry.action_id,)).fetchone()
check("Retryable failures are bounded and scheduled", retry.status == "RETRY_SCHEDULED" and retry_row["next_retry_at"] and retry_row["retry_count"] == 1 and retry_row["max_retries"] == 3)
execution_core.provider_for = original_provider_for

check("Policy decisions recorded", conn.execute("SELECT COUNT(*) FROM policy_decisions").fetchone()[0] >= 5)
check("Action ledger events recorded", conn.execute("SELECT COUNT(*) FROM system_ledger WHERE event_type='Action'").fetchone()[0] >= 5)
check("Foreign keys", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0)
check("Database integrity", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
conn.close()

app_text = (ROOT / "app.py").read_text(encoding="utf-8")
auto_text = (ROOT / "services" / "automation_engine.py").read_text(encoding="utf-8")
template_text = (ROOT / "templates" / "automation.html").read_text(encoding="utf-8")
check("SMS routed through execution core", "execute_action(" in auto_text and "ActionIntent(" in auto_text)
check("No live execution route exposed", 'mode="live"' not in app_text)
check("Execution UI wired", "GOVERNED ACTION LEDGER" in template_text and "LIVE ACTIONS LOCKED" in template_text)

if failures:
    print(f"\nBusiness OS v11 verification FAILED · {failures} check(s) failed")
    raise SystemExit(1)
print("\nBusiness OS v11 verification PASS")
