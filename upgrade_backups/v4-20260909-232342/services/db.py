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
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = connect()

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

    con.commit()
    con.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")