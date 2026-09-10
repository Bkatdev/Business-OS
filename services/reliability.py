"""Reliability, snapshot, and release-safety helpers for Business OS.

This module is deliberately dependency-free. It provides non-destructive system
checks and safe SQLite snapshots so the product can be operated with a small
maintenance burden.
"""

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
    status: str  # pass | warn | fail
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "pass"


def _table_names(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _count(conn, sql, params=()):
    return int(conn.execute(sql, params).fetchone()[0])


def run_self_test(conn, *, persist=True):
    """Run fast, non-destructive checks against the active Business OS database."""
    checks: list[CheckResult] = []

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    checks.append(CheckResult(
        "sqlite_integrity",
        "Database integrity",
        "pass" if integrity == "ok" else "fail",
        "SQLite integrity_check returned ok." if integrity == "ok" else f"SQLite reported: {integrity}",
    ))

    required_tables = {
        "businesses", "leads", "calls", "lead_activities", "lead_notes",
        "appointments", "outbound_messages", "automation_executions",
        "system_events", "reliability_runs", "data_snapshots",
    }
    missing_tables = sorted(required_tables - _table_names(conn))
    checks.append(CheckResult(
        "schema_tables", "Required data model",
        "pass" if not missing_tables else "fail",
        "All required tables are present." if not missing_tables else "Missing: " + ", ".join(missing_tables),
    ))

    required_message_columns = {
        "business_id", "lead_id", "recipient", "status", "provider",
        "provider_message_id", "send_attempts", "last_attempt_at",
    }
    message_columns = _column_names(conn, "outbound_messages") if "outbound_messages" in _table_names(conn) else set()
    missing_columns = sorted(required_message_columns - message_columns)
    checks.append(CheckResult(
        "schema_columns", "Automation schema",
        "pass" if not missing_columns else "fail",
        "Execution tracking fields are present." if not missing_columns else "Missing: " + ", ".join(missing_columns),
    ))

    fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    checks.append(CheckResult(
        "foreign_keys", "Relationship integrity",
        "pass" if not fk_issues else "fail",
        "No broken foreign-key relationships found." if not fk_issues else f"{len(fk_issues)} foreign-key issue(s) found.",
    ))

    mismatched_messages = _count(conn, """
        SELECT COUNT(*)
        FROM outbound_messages m
        JOIN leads l ON l.id = m.lead_id
        WHERE m.business_id IS NULL OR l.business_id IS NULL OR m.business_id != l.business_id
    """)
    checks.append(CheckResult(
        "tenant_messages", "Message tenant isolation",
        "pass" if mismatched_messages == 0 else "fail",
        "Every message matches its lead's client." if mismatched_messages == 0 else f"{mismatched_messages} message(s) have unsafe client ownership.",
    ))

    mismatched_exec = _count(conn, """
        SELECT COUNT(*)
        FROM automation_executions e
        JOIN leads l ON l.id = e.lead_id
        WHERE e.business_id IS NULL OR l.business_id IS NULL OR e.business_id != l.business_id
    """)
    checks.append(CheckResult(
        "tenant_executions", "Execution tenant isolation",
        "pass" if mismatched_exec == 0 else "fail",
        "Execution records stay inside their client boundary." if mismatched_exec == 0 else f"{mismatched_exec} execution record(s) cross or miss a client boundary.",
    ))

    orphan_appointments = _count(conn, """
        SELECT COUNT(*) FROM appointments a
        LEFT JOIN leads l ON l.id = a.lead_id
        WHERE l.id IS NULL
    """)
    checks.append(CheckResult(
        "appointments", "Appointment links",
        "pass" if orphan_appointments == 0 else "fail",
        "Every appointment points to a real lead." if orphan_appointments == 0 else f"{orphan_appointments} orphan appointment(s) found.",
    ))

    active_clients = _count(conn, "SELECT COUNT(*) FROM businesses WHERE status='Client'")
    mapped_clients = _count(conn, """
        SELECT COUNT(*) FROM businesses
        WHERE status='Client' AND TRIM(COALESCE(retell_agent_id,'')) != ''
    """)
    mapping_status = "pass" if active_clients == 0 or mapped_clients == active_clients else "warn"
    checks.append(CheckResult(
        "retell_mapping", "Receptionist routing",
        mapping_status,
        f"{mapped_clients}/{active_clients} active client(s) have a Retell mapping." if active_clients else "No active clients require mapping yet.",
    ))

    secret_configured = bool(os.getenv("BUSINESS_OS_SECRET_KEY", "").strip())
    debug_enabled = os.getenv("BUSINESS_OS_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    checks.append(CheckResult(
        "runtime_config", "Runtime safety",
        "pass" if secret_configured and not debug_enabled else "warn",
        "Production secret configured and debug disabled." if secret_configured and not debug_enabled
        else "Local mode is safe for development, but production must set BUSINESS_OS_SECRET_KEY and keep BUSINESS_OS_DEBUG off.",
    ))

    recent_failures = _count(conn, """
        SELECT COUNT(*) FROM outbound_messages
        WHERE status='Failed' AND COALESCE(last_attempt_at, created_at) >= ?
    """, ((datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds"),))
    checks.append(CheckResult(
        "recent_failures", "Recent automation failures",
        "pass" if recent_failures == 0 else "warn",
        "No failed messages in the last 24 hours." if recent_failures == 0 else f"{recent_failures} failed message(s) in the last 24 hours.",
    ))

    failures = sum(1 for c in checks if c.status == "fail")
    warnings = sum(1 for c in checks if c.status == "warn")
    if failures:
        overall = "Fail"
    elif warnings:
        overall = "Attention"
    else:
        overall = "Pass"

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
            (
                overall,
                f"{result['passes']}/{result['total']} checks passed; {warnings} warning(s); {failures} failure(s).",
                json.dumps(result["checks"]),
                result["created_at"],
            ),
        )
        conn.commit()

    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_database_snapshot(reason="Manual", *, retention=MAX_SNAPSHOTS):
    """Create a consistent SQLite snapshot using SQLite's backup API."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"business_os-{stamp}.db"
    path = BACKUP_DIR / filename

    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

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
    conn.execute(
        """
        INSERT INTO data_snapshots(filename, size_bytes, checksum, reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (filename, size, checksum, reason, now_iso()),
    )
    conn.commit()
    conn.close()

    snapshots = sorted(BACKUP_DIR.glob("business_os-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in snapshots[max(1, int(retention)):]:
        old.unlink(missing_ok=True)

    return {
        "filename": filename,
        "path": str(path),
        "size_bytes": size,
        "checksum": checksum,
        "reason": reason,
    }


def ensure_daily_snapshot():
    """Create at most one automatic snapshot per calendar day."""
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
    """Persist a concise incident record for later diagnosis."""
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO system_events(severity, event_type, title, details, business_id, lead_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (severity, event_type, title, str(details or "")[:4000], business_id, lead_id, now_iso()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def reliability_dashboard(conn):
    latest_run = conn.execute(
        "SELECT * FROM reliability_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    snapshots = conn.execute(
        "SELECT * FROM data_snapshots ORDER BY id DESC LIMIT 8"
    ).fetchall()
    recent_events = conn.execute(
        "SELECT * FROM system_events ORDER BY id DESC LIMIT 20"
    ).fetchall()

    backup_exists = any(BACKUP_DIR.glob("business_os-*.db"))
    last_snapshot = snapshots[0] if snapshots else None
    critical_events = sum(1 for row in recent_events if row["severity"] in {"Error", "Critical"})

    return {
        "latest_run": latest_run,
        "snapshots": snapshots,
        "recent_events": recent_events,
        "backup_exists": backup_exists,
        "last_snapshot": last_snapshot,
        "critical_events": critical_events,
        "backup_dir": str(BACKUP_DIR),
    }
