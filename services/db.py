import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "business_os.db"

EXTRA_COLUMNS = {
    "address": "TEXT DEFAULT ''",
    "google_place_id": "TEXT DEFAULT ''",
    "source": "TEXT DEFAULT 'manual'",
    "audit_status": "TEXT DEFAULT 'not_audited'",
    "audited_at": "TEXT DEFAULT ''",
    "audit_evidence": "TEXT DEFAULT ''",
    "audit_pages_checked": "INTEGER DEFAULT 0",
    "website_type": "TEXT DEFAULT ''",
    "estimate_offered": "INTEGER DEFAULT 0",
    "scheduling_mentioned": "INTEGER DEFAULT 0",
    "audit_confidence": "TEXT DEFAULT ''",
    "retell_agent_id": "TEXT DEFAULT ''",
}


def connect():
    # SQLite is our local development database. These settings make writes
    # safer under concurrent webhook/UI activity and enforce declared FKs.
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 10000")
    return con


def init_db():
    con = connect()
    # WAL prevents ordinary readers from blocking a writer and is a safer
    # local-development default for simultaneous UI + webhook traffic.
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Local Service Business',
            reviews INTEGER NOT NULL DEFAULT 0,
            rating REAL NOT NULL DEFAULT 0,
            website TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            online_booking INTEGER NOT NULL DEFAULT 0,
            emergency_service INTEGER NOT NULL DEFAULT 0,
            website_chat INTEGER NOT NULL DEFAULT 0,
            estimate_form INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Not Contacted',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            caller_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            service_type TEXT NOT NULL DEFAULT '',
            issue_description TEXT NOT NULL DEFAULT '',
            lead_type TEXT NOT NULL DEFAULT 'New Lead',
            priority TEXT NOT NULL DEFAULT 'Normal',
            safety_flag TEXT NOT NULL DEFAULT '',
            preferred_time TEXT NOT NULL DEFAULT '',
            appointment_status TEXT NOT NULL DEFAULT 'Not Scheduled',
            status TEXT NOT NULL DEFAULT 'New',
            source TEXT NOT NULL DEFAULT 'AI Receptionist',
            retell_call_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            lead_id INTEGER,
            retell_call_id TEXT NOT NULL DEFAULT '',
            caller_phone TEXT NOT NULL DEFAULT '',
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT '',
            transcript TEXT NOT NULL DEFAULT '',
            call_status TEXT NOT NULL DEFAULT 'Completed',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )


    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL DEFAULT 'Status',
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id
        ON lead_activities(lead_id)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_created_at
        ON lead_activities(created_at)
        """
    )

    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_created_activity
        AFTER INSERT ON leads
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Created',
                'Lead captured',
                'Lead entered Business OS.',
                NEW.created_at
            );
        END
        """
    )

    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_status_activity
        AFTER UPDATE OF status ON leads
        WHEN OLD.status != NEW.status
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Status',
                'Status changed to ' || NEW.status,
                'Previous status: ' || OLD.status,
                datetime('now', 'localtime')
            );
        END
        """
    )

    lead_existing = {
        row["name"]
        for row in con.execute("PRAGMA table_info(leads)")
    }

    lead_extra_columns = {
        "updated_at": "TEXT DEFAULT ''",
        "last_contacted_at": "TEXT DEFAULT ''",
        "next_follow_up_at": "TEXT DEFAULT ''",
        "duplicate_of_lead_id": "INTEGER",
    }

    for name, definition in lead_extra_columns.items():
        if name not in lead_existing:
            con.execute(
                f"ALTER TABLE leads ADD COLUMN {name} {definition}"
            )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_notes_lead_id
        ON lead_notes(lead_id)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_leads_next_follow_up_at
        ON leads(next_follow_up_at)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_leads_phone_business
        ON leads(business_id, phone)
        """
    )


    con.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            lead_id INTEGER NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Scheduled',
            service_type TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'Business OS',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appointments_start_at
        ON appointments(start_at)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appointments_business_start
        ON appointments(business_id, start_at)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_appointments_lead_id
        ON appointments(lead_id)
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS outbound_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL DEFAULT 'SMS',
            recipient TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending Approval',
            automation_key TEXT NOT NULL DEFAULT 'manual_follow_up',
            created_at TEXT NOT NULL,
            approved_at TEXT NOT NULL DEFAULT '',
            sent_at TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outbound_messages_status
        ON outbound_messages(status)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outbound_messages_business
        ON outbound_messages(business_id, created_at)
        """
    )

    message_existing = {
        row["name"]
        for row in con.execute("PRAGMA table_info(outbound_messages)")
    }
    message_extra_columns = {
        "provider": "TEXT NOT NULL DEFAULT ''",
        "provider_message_id": "TEXT NOT NULL DEFAULT ''",
        "send_attempts": "INTEGER NOT NULL DEFAULT 0",
        "last_attempt_at": "TEXT NOT NULL DEFAULT ''",
        "delivered_at": "TEXT NOT NULL DEFAULT ''",
        "scheduled_for": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in message_extra_columns.items():
        if name not in message_existing:
            con.execute(f"ALTER TABLE outbound_messages ADD COLUMN {name} {definition}")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            lead_id INTEGER,
            business_id INTEGER,
            channel TEXT NOT NULL DEFAULT 'SMS',
            mode TEXT NOT NULL DEFAULT 'simulation',
            status TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            provider TEXT NOT NULL DEFAULT '',
            provider_message_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (message_id) REFERENCES outbound_messages(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_automation_executions_message ON automation_executions(message_id, created_at)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_automation_executions_status ON automation_executions(status, created_at)"
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL DEFAULT 'Info',
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            business_id INTEGER,
            lead_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_system_events_created ON system_events(created_at)"
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS reliability_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL DEFAULT 'Self Test',
            status TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_reliability_runs_created ON reliability_runs(created_at)"
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS data_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            checksum TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT 'Manual',
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_data_snapshots_created ON data_snapshots(created_at)"
    )

    existing = {
        row["name"]
        for row in con.execute("PRAGMA table_info(businesses)")
    }

    for name, definition in EXTRA_COLUMNS.items():
        if name not in existing:
            con.execute(
                f"ALTER TABLE businesses ADD COLUMN {name} {definition}"
            )

    con.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_place_id
        ON businesses(google_place_id)
        WHERE google_place_id IS NOT NULL
          AND google_place_id != ''
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_leads_created_at
        ON leads(created_at)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_leads_priority
        ON leads(priority)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_calls_created_at
        ON calls(created_at)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_calls_retell_call_id
        ON calls(retell_call_id)
        """
    )

    # ---- v8: governance, lifecycle, and quarantine ---------------------
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )

    business_existing = {row["name"] for row in con.execute("PRAGMA table_info(businesses)")}
    business_governance_columns = {
        "lifecycle_stage": "TEXT NOT NULL DEFAULT 'PROSPECT'",
        "automation_enabled": "INTEGER NOT NULL DEFAULT 0",
        "activated_at": "TEXT NOT NULL DEFAULT ''",
        "lifecycle_updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in business_governance_columns.items():
        if name not in business_existing:
            con.execute(f"ALTER TABLE businesses ADD COLUMN {name} {definition}")

    entity_governance = {
        "leads": {
            "data_classification": "TEXT NOT NULL DEFAULT 'LEGACY'",
            "quarantine_status": "TEXT NOT NULL DEFAULT 'Not Required'",
            "quarantine_reason": "TEXT NOT NULL DEFAULT ''",
            "source_agent_id": "TEXT NOT NULL DEFAULT ''",
        },
        "calls": {
            "data_classification": "TEXT NOT NULL DEFAULT 'LEGACY'",
            "quarantine_status": "TEXT NOT NULL DEFAULT 'Not Required'",
            "quarantine_reason": "TEXT NOT NULL DEFAULT ''",
            "source_agent_id": "TEXT NOT NULL DEFAULT ''",
        },
        "outbound_messages": {
            "data_classification": "TEXT NOT NULL DEFAULT 'LEGACY'",
            "quarantine_status": "TEXT NOT NULL DEFAULT 'Not Required'",
            "quarantine_reason": "TEXT NOT NULL DEFAULT ''",
        },
        "automation_executions": {
            "data_classification": "TEXT NOT NULL DEFAULT 'LEGACY'",
            "quarantine_status": "TEXT NOT NULL DEFAULT 'Not Required'",
            "quarantine_reason": "TEXT NOT NULL DEFAULT ''",
        },
    }
    for table, columns in entity_governance.items():
        existing_cols = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing_cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS quarantine_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            business_id INTEGER,
            classification TEXT NOT NULL DEFAULT 'UNVERIFIED',
            reason_code TEXT NOT NULL,
            reason_detail TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            resolved_at TEXT NOT NULL DEFAULT '',
            resolution_note TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_quarantine_status ON quarantine_items(status, created_at)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_quarantine_entity ON quarantine_items(entity_type, entity_id)"
    )
    con.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_quarantine_open_reason
        ON quarantine_items(entity_type, entity_id, reason_code)
        WHERE status = 'Open'
        """
    )

    # One receptionist agent must never route to two clients.
    con.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_retell_agent_mapping
        ON businesses(retell_agent_id)
        WHERE TRIM(COALESCE(retell_agent_id, '')) != ''
        """
    )

    migrated = con.execute(
        "SELECT value FROM app_meta WHERE key = 'v8_governance_migrated'"
    ).fetchone()
    if migrated is None:
        timestamp = datetime.now().isoformat(timespec="seconds")

        # Preserve the old CRM status while introducing a stricter operational
        # lifecycle. A legacy 'Client' is ONBOARDING, never silently ACTIVE.
        con.execute(
            """
            UPDATE businesses
            SET lifecycle_stage = CASE
                WHEN status = 'Qualified' THEN 'QUALIFIED'
                WHEN status = 'Demo' THEN 'DEMO'
                WHEN status = 'Client' THEN 'ONBOARDING'
                WHEN status = 'Lost' THEN 'CANCELLED'
                ELSE 'PROSPECT'
            END,
            automation_enabled = 0,
            lifecycle_updated_at = ?
            """,
            (timestamp,),
        )

        # Existing records predate governance metadata. Keep them truthful as
        # LEGACY; never rewrite them as production data.
        for table in ("leads", "calls", "outbound_messages", "automation_executions"):
            con.execute(f"UPDATE {table} SET data_classification = 'LEGACY'")

        # Any old record without a provable owner is quarantined instead of
        # being guessed into a client account.
        for table in ("leads", "calls", "outbound_messages", "automation_executions"):
            con.execute(
                f"""
                UPDATE {table}
                SET quarantine_status = 'Open',
                    quarantine_reason = 'Legacy record has no provable client ownership.'
                WHERE business_id IS NULL
                """
            )
            rows = con.execute(
                f"SELECT id, business_id FROM {table} WHERE business_id IS NULL"
            ).fetchall()
            entity_type = table[:-1] if table.endswith('s') else table
            for row in rows:
                con.execute(
                    """
                    INSERT OR IGNORE INTO quarantine_items
                        (entity_type, entity_id, business_id, classification,
                         reason_code, reason_detail, status, created_at)
                    VALUES (?, ?, ?, 'LEGACY', 'legacy_unassigned',
                            'Pre-governance record has no provable client ownership.', 'Open', ?)
                    """,
                    (entity_type, row["id"], row["business_id"], timestamp),
                )

        con.execute(
            """
            INSERT INTO app_meta(key, value, updated_at)
            VALUES ('v8_governance_migrated', '1', ?)
            """,
            (timestamp,),
        )

    con.commit()
    con.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")