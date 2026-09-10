"""Reliability, governance, snapshot, and release-safety helpers."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

from services.db import DB_PATH, connect, now_iso

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "local_backups" / "database"
MAX_SNAPSHOTS = 20


@dataclass
class CheckResult:
    key: str
    name: str
    status: str
    detail: str

    @property
    def ok(self):
        return self.status == "pass"


def _table_names(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _count(conn, sql, params=()):
    return int(conn.execute(sql, params).fetchone()[0])


def run_self_test(conn, *, persist=True):
    checks = []
    tables = _table_names(conn)

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    checks.append(CheckResult(
        "sqlite_integrity", "Database integrity",
        "pass" if integrity == "ok" else "fail",
        "SQLite integrity_check returned ok." if integrity == "ok" else f"SQLite reported: {integrity}",
    ))

    required_tables = {
        "businesses", "leads", "calls", "lead_activities", "lead_notes",
        "appointments", "outbound_messages", "automation_executions",
        "system_events", "reliability_runs", "data_snapshots", "app_meta",
        "quarantine_items",
    }
    missing_tables = sorted(required_tables - tables)
    checks.append(CheckResult(
        "schema_tables", "Required data model",
        "pass" if not missing_tables else "fail",
        "All required tables are present." if not missing_tables else "Missing: " + ", ".join(missing_tables),
    ))

    required_message_columns = {
        "business_id", "lead_id", "recipient", "status", "provider",
        "provider_message_id", "send_attempts", "last_attempt_at",
        "data_classification", "quarantine_status", "quarantine_reason",
    }
    message_columns = _column_names(conn, "outbound_messages") if "outbound_messages" in tables else set()
    missing_columns = sorted(required_message_columns - message_columns)
    checks.append(CheckResult(
        "schema_columns", "Governed automation schema",
        "pass" if not missing_columns else "fail",
        "Execution + governance fields are present." if not missing_columns else "Missing: " + ", ".join(missing_columns),
    ))

    fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    checks.append(CheckResult(
        "foreign_keys", "Relationship integrity",
        "pass" if not fk_issues else "fail",
        "No broken foreign-key relationships found." if not fk_issues else f"{len(fk_issues)} foreign-key issue(s) found.",
    ))

    # Only PRODUCTION records are release-blocking. Legacy/test/demo/unverified
    # records remain visible and quarantined, but they are not rewritten as fake clients.
    production_message_violations = _count(conn, """
        SELECT COUNT(*)
        FROM outbound_messages m
        LEFT JOIN leads l ON l.id = m.lead_id
        LEFT JOIN businesses b ON b.id = m.business_id
        WHERE UPPER(COALESCE(m.data_classification,'')) = 'PRODUCTION'
          AND (
              m.business_id IS NULL OR l.id IS NULL OR l.business_id IS NULL
              OR m.business_id != l.business_id
              OR UPPER(COALESCE(l.data_classification,'')) != 'PRODUCTION'
              OR COALESCE(m.quarantine_status,'') = 'Open'
              OR COALESCE(l.quarantine_status,'') = 'Open'
              OR UPPER(COALESCE(b.lifecycle_stage,'')) != 'ACTIVE'
          )
    """)
    checks.append(CheckResult(
        "tenant_messages", "Production message isolation",
        "pass" if production_message_violations == 0 else "fail",
        "Every production message has a provable active-client boundary."
        if production_message_violations == 0
        else f"{production_message_violations} production message(s) violate the tenant boundary.",
    ))

    production_exec_violations = _count(conn, """
        SELECT COUNT(*)
        FROM automation_executions e
        LEFT JOIN leads l ON l.id = e.lead_id
        LEFT JOIN businesses b ON b.id = e.business_id
        WHERE UPPER(COALESCE(e.data_classification,'')) = 'PRODUCTION'
          AND (
              e.business_id IS NULL OR l.id IS NULL OR l.business_id IS NULL
              OR e.business_id != l.business_id
              OR UPPER(COALESCE(l.data_classification,'')) != 'PRODUCTION'
              OR COALESCE(e.quarantine_status,'') = 'Open'
              OR COALESCE(l.quarantine_status,'') = 'Open'
              OR UPPER(COALESCE(b.lifecycle_stage,'')) != 'ACTIVE'
          )
    """)
    checks.append(CheckResult(
        "tenant_executions", "Production execution isolation",
        "pass" if production_exec_violations == 0 else "fail",
        "Every production execution stays inside one active client."
        if production_exec_violations == 0
        else f"{production_exec_violations} production execution(s) violate the tenant boundary.",
    ))

    duplicate_mappings = _count(conn, """
        SELECT COUNT(*) FROM (
          SELECT retell_agent_id
          FROM businesses
          WHERE TRIM(COALESCE(retell_agent_id,'')) != ''
          GROUP BY retell_agent_id HAVING COUNT(*) > 1
        )
    """)
    checks.append(CheckResult(
        "retell_uniqueness", "Receptionist mapping uniqueness",
        "pass" if duplicate_mappings == 0 else "fail",
        "Each Retell agent maps to at most one business."
        if duplicate_mappings == 0 else f"{duplicate_mappings} duplicate agent mapping(s) exist.",
    ))

    orphan_appointments = _count(conn, """
        SELECT COUNT(*) FROM appointments a
        LEFT JOIN leads l ON l.id = a.lead_id
        WHERE l.id IS NULL
    """)
    checks.append(CheckResult(
        "appointments", "Appointment links",
        "pass" if orphan_appointments == 0 else "fail",
        "Every appointment points to a real lead."
        if orphan_appointments == 0 else f"{orphan_appointments} orphan appointment(s) found.",
    ))

    active_clients = _count(conn, "SELECT COUNT(*) FROM businesses WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE'")
    mapped_active = _count(conn, """
        SELECT COUNT(*) FROM businesses
        WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE'
          AND TRIM(COALESCE(retell_agent_id,'')) != ''
    """)
    checks.append(CheckResult(
        "retell_mapping", "Active-client routing",
        "pass" if active_clients == mapped_active else "fail",
        f"{mapped_active}/{active_clients} ACTIVE client(s) have exact Retell routing."
        if active_clients else "No ACTIVE clients require production routing yet.",
    ))

    open_quarantine = _count(conn, "SELECT COUNT(*) FROM quarantine_items WHERE status='Open'")
    prod_quarantine = _count(conn, """
        SELECT COUNT(*) FROM quarantine_items
        WHERE status='Open' AND UPPER(COALESCE(classification,''))='PRODUCTION'
    """)
    quarantine_status = "fail" if prod_quarantine else ("warn" if open_quarantine else "pass")
    quarantine_detail = (
        f"{prod_quarantine} production quarantine item(s) require resolution."
        if prod_quarantine else
        (f"{open_quarantine} legacy/test/unverified item(s) are safely quarantined."
         if open_quarantine else "No open quarantine items.")
    )
    checks.append(CheckResult("quarantine", "Quarantine gate", quarantine_status, quarantine_detail))

    secret_configured = bool(os.getenv("BUSINESS_OS_SECRET_KEY", "").strip())
    debug_enabled = os.getenv("BUSINESS_OS_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    checks.append(CheckResult(
        "runtime_config", "Runtime safety",
        "pass" if secret_configured and not debug_enabled else "warn",
        "Production secret configured and debug disabled."
        if secret_configured and not debug_enabled
        else "Local mode is safe for development; production must set BUSINESS_OS_SECRET_KEY and keep BUSINESS_OS_DEBUG off.",
    ))

    retell_key = bool(os.getenv("RETELL_API_KEY", "").strip())
    unsigned_local = os.getenv("BUSINESS_OS_ALLOW_UNSIGNED_RETELL", "0").strip().lower() in {"1", "true", "yes", "on"}
    checks.append(CheckResult(
        "webhook_security", "Webhook authenticity",
        "pass" if retell_key and not unsigned_local else "warn",
        "Retell signature verification is configured and unsigned bypass is off."
        if retell_key and not unsigned_local
        else "Before production, configure RETELL_API_KEY and keep BUSINESS_OS_ALLOW_UNSIGNED_RETELL off.",
    ))

    recent_failures = _count(conn, """
        SELECT COUNT(*) FROM outbound_messages
        WHERE status='Failed' AND COALESCE(last_attempt_at, created_at) >= ?
    """, ((datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds"),))
    checks.append(CheckResult(
        "recent_failures", "Recent automation failures",
        "pass" if recent_failures == 0 else "warn",
        "No failed messages in the last 24 hours."
        if recent_failures == 0 else f"{recent_failures} failed message(s) in the last 24 hours.",
    ))

    failures = sum(1 for c in checks if c.status == "fail")
    warnings = sum(1 for c in checks if c.status == "warn")
    overall = "Fail" if failures else ("Attention" if warnings else "Pass")
    result = {
        "status": overall,
        "checks": [asdict(c) for c in checks],
        "passes": sum(1 for c in checks if c.status == "pass"),
        "warnings": warnings,
        "failures": failures,
        "total": len(checks),
        "created_at": now_iso(),
    }
    if persist:
        conn.execute(
            """
            INSERT INTO reliability_runs(kind, status, summary, details, created_at)
            VALUES ('Self Test', ?, ?, ?, ?)
            """,
            (overall, f"{result['passes']}/{result['total']} passed; {warnings} warning(s); {failures} failure(s).",
             json.dumps(result["checks"]), result["created_at"]),
        )
        conn.commit()
    return result


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_database_snapshot(reason="Manual", *, retention=MAX_SNAPSHOTS):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"business_os-{stamp}.db"
    path = BACKUP_DIR / filename
    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(path)
    try:
        source.backup(destination)
    finally:
        destination.close(); source.close()
    verify = sqlite3.connect(path)
    try:
        integrity = verify.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        verify.close()
    if integrity != "ok":
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Snapshot integrity check failed: {integrity}")
    checksum = _sha256(path)
    size = path.stat().st_size
    conn = connect()
    conn.execute("INSERT INTO data_snapshots(filename,size_bytes,checksum,reason,created_at) VALUES (?,?,?,?,?)",
                 (filename, size, checksum, reason, now_iso()))
    conn.commit(); conn.close()
    snapshots = sorted(BACKUP_DIR.glob("business_os-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in snapshots[max(1, int(retention)):]:
        old.unlink(missing_ok=True)
    return {"filename": filename, "path": str(path), "size_bytes": size, "checksum": checksum, "reason": reason}


def ensure_daily_snapshot():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().date()
    for path in BACKUP_DIR.glob("business_os-*.db"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime).date() == today:
                return None
        except OSError:
            continue
    return create_database_snapshot("Automatic daily")


def record_system_event(title, details="", severity="Error", event_type="Runtime", business_id=None, lead_id=None):
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT INTO system_events(severity,event_type,title,details,business_id,lead_id,created_at) VALUES (?,?,?,?,?,?,?)",
            (severity, event_type, title, str(details or "")[:4000], business_id, lead_id, now_iso()),
        )
        conn.commit(); return cursor.lastrowid
    finally:
        conn.close()


def reliability_dashboard(conn):
    latest_run = conn.execute("SELECT * FROM reliability_runs ORDER BY id DESC LIMIT 1").fetchone()
    snapshots = conn.execute("SELECT * FROM data_snapshots ORDER BY id DESC LIMIT 8").fetchall()
    recent_events = conn.execute("SELECT * FROM system_events ORDER BY id DESC LIMIT 20").fetchall()
    quarantine = conn.execute("""
        SELECT q.*, b.name AS business_name
        FROM quarantine_items q
        LEFT JOIN businesses b ON b.id=q.business_id
        WHERE q.status='Open'
        ORDER BY q.id DESC LIMIT 20
    """).fetchall()
    lifecycle = {
        row["lifecycle_stage"]: row["n"]
        for row in conn.execute("""
            SELECT lifecycle_stage, COUNT(*) n FROM businesses
            GROUP BY lifecycle_stage
        """).fetchall()
    }
    backup_exists = any(BACKUP_DIR.glob("business_os-*.db"))
    last_snapshot = snapshots[0] if snapshots else None
    critical_events = sum(1 for row in recent_events if row["severity"] in {"Error", "Critical"})
    return {
        "latest_run": latest_run, "snapshots": snapshots, "recent_events": recent_events,
        "backup_exists": backup_exists, "last_snapshot": last_snapshot,
        "critical_events": critical_events, "backup_dir": str(BACKUP_DIR),
        "quarantine": quarantine, "open_quarantine": len(quarantine), "lifecycle": lifecycle,
    }
