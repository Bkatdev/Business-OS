import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'business_os.db'

EXTRA_COLUMNS = {
    'address': "TEXT DEFAULT ''",
    'google_place_id': "TEXT DEFAULT ''",
    'source': "TEXT DEFAULT 'manual'",
    'audit_status': "TEXT DEFAULT 'not_audited'",
    'audited_at': "TEXT DEFAULT ''",
    'audit_evidence': "TEXT DEFAULT ''",
    'audit_pages_checked': "INTEGER DEFAULT 0",
    'website_type': "TEXT DEFAULT ''",
    'estimate_offered': "INTEGER DEFAULT 0",
    'scheduling_mentioned': "INTEGER DEFAULT 0",
    'audit_confidence': "TEXT DEFAULT ''"
}

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect()
    con.execute('''CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, city TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Local Service Business',
        reviews INTEGER NOT NULL DEFAULT 0, rating REAL NOT NULL DEFAULT 0,
        website TEXT DEFAULT '', phone TEXT DEFAULT '', email TEXT DEFAULT '',
        online_booking INTEGER NOT NULL DEFAULT 0,
        emergency_service INTEGER NOT NULL DEFAULT 0,
        website_chat INTEGER NOT NULL DEFAULT 0,
        estimate_form INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Not Contacted',
        notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, business_id INTEGER,
        title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL
    )''')
    existing = {r['name'] for r in con.execute('PRAGMA table_info(businesses)')}
    for name, definition in EXTRA_COLUMNS.items():
        if name not in existing:
            con.execute(f'ALTER TABLE businesses ADD COLUMN {name} {definition}')
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_place_id ON businesses(google_place_id) WHERE google_place_id IS NOT NULL AND google_place_id != ''")
    con.commit(); con.close()

def now_iso():
    return datetime.now().isoformat(timespec='seconds')
