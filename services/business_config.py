import json
import re
from services.db import connect, now_iso

QUESTION_TYPES = {
    "short_text", "long_text", "phone", "email", "address",
    "choice", "yes_no", "date_time_preference", "photo_request",
}


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_business_config_schema(conn=None):
    own = conn is None
    conn = conn or connect()

    # Extend the existing profile rather than create another source of truth.
    cols = _columns(conn, "client_profiles") if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='client_profiles'"
    ).fetchone() else set()
    if cols and "industry" not in cols:
        conn.execute("ALTER TABLE client_profiles ADD COLUMN industry TEXT NOT NULL DEFAULT ''")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS business_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            public INTEGER NOT NULL DEFAULT 1 CHECK(public IN (0,1)),
            bookable INTEGER NOT NULL DEFAULT 0 CHECK(bookable IN (0,1)),
            requires_estimate INTEGER NOT NULL DEFAULT 1 CHECK(requires_estimate IN (0,1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE (business_id, name)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_business_services_business ON business_services(business_id, active, sort_order, id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS intake_schemas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT 'Default Intake',
            status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Active','Archived')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intake_schemas_business ON intake_schemas(business_id, status, id)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS intake_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_id INTEGER NOT NULL,
            service_id INTEGER,
            question_key TEXT NOT NULL,
            label TEXT NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'short_text',
            required INTEGER NOT NULL DEFAULT 0 CHECK(required IN (0,1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            options_json TEXT NOT NULL DEFAULT '[]',
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (schema_id) REFERENCES intake_schemas(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES business_services(id) ON DELETE SET NULL,
            UNIQUE (schema_id, question_key)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intake_questions_schema ON intake_questions(schema_id, active, sort_order, id)")

    conn.commit()
    if own:
        conn.close()


def _business_exists(conn, business_id):
    return conn.execute("SELECT 1 FROM businesses WHERE id=?", (business_id,)).fetchone() is not None


def get_or_create_default_schema(conn, business_id):
    ensure_business_config_schema(conn)
    row = conn.execute(
        "SELECT * FROM intake_schemas WHERE business_id=? AND status!='Archived' ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, id LIMIT 1",
        (business_id,),
    ).fetchone()
    if row:
        return row
    ts = now_iso()
    cur = conn.execute(
        "INSERT INTO intake_schemas(business_id,name,status,created_at,updated_at) VALUES(?, 'Default Intake', 'Draft', ?, ?)",
        (business_id, ts, ts),
    )
    conn.commit()
    return conn.execute("SELECT * FROM intake_schemas WHERE id=?", (cur.lastrowid,)).fetchone()


def list_services(conn, business_id, include_inactive=True):
    ensure_business_config_schema(conn)
    sql = "SELECT * FROM business_services WHERE business_id=?"
    if not include_inactive:
        sql += " AND active=1"
    sql += " ORDER BY sort_order, id"
    return conn.execute(sql, (business_id,)).fetchall()


def add_service(business_id, name, description="", public=True, bookable=False, requires_estimate=True):
    name = (name or "").strip()
    description = (description or "").strip()
    if not name:
        return False, "Service name is required."
    if len(name) > 120:
        return False, "Service name must be 120 characters or fewer."
    conn = connect(); ensure_business_config_schema(conn)
    if not _business_exists(conn, business_id):
        conn.close(); return False, "Business not found."
    if conn.execute("SELECT 1 FROM business_services WHERE business_id=? AND lower(name)=lower(?)", (business_id, name)).fetchone():
        conn.close(); return False, "That service already exists for this business."
    ts = now_iso()
    order = conn.execute("SELECT COALESCE(MAX(sort_order),0)+10 FROM business_services WHERE business_id=?", (business_id,)).fetchone()[0]
    conn.execute("""
        INSERT INTO business_services(business_id,name,description,active,public,bookable,requires_estimate,sort_order,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (business_id, name, description, 1, int(bool(public)), int(bool(bookable)), int(bool(requires_estimate)), order, ts, ts))
    conn.commit(); conn.close()
    return True, "Service added. It does not change live automation until a governed workflow consumes it."


def toggle_service(business_id, service_id):
    conn = connect(); ensure_business_config_schema(conn)
    row = conn.execute("SELECT id, active FROM business_services WHERE id=? AND business_id=?", (service_id, business_id)).fetchone()
    if not row:
        conn.close(); return False, "Service not found for this business."
    new_value = 0 if row["active"] else 1
    conn.execute("UPDATE business_services SET active=?, updated_at=? WHERE id=? AND business_id=?", (new_value, now_iso(), service_id, business_id))
    conn.commit(); conn.close()
    return True, "Service enabled." if new_value else "Service disabled. Historical data was preserved."


def _safe_key(label):
    key = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")[:50]
    return key or "question"


def add_intake_question(business_id, label, question_type="short_text", required=False, service_id=None, options=None):
    label = (label or "").strip()
    if not label:
        return False, "Question text is required."
    if len(label) > 240:
        return False, "Question text must be 240 characters or fewer."
    if question_type not in QUESTION_TYPES:
        return False, "Unsupported intake question type."
    conn = connect(); ensure_business_config_schema(conn)
    if not _business_exists(conn, business_id):
        conn.close(); return False, "Business not found."
    schema = get_or_create_default_schema(conn, business_id)
    if service_id:
        linked = conn.execute("SELECT id FROM business_services WHERE id=? AND business_id=?", (service_id, business_id)).fetchone()
        if not linked:
            conn.close(); return False, "Selected service does not belong to this business."
    base = _safe_key(label); key = base; suffix = 2
    while conn.execute("SELECT 1 FROM intake_questions WHERE schema_id=? AND question_key=?", (schema["id"], key)).fetchone():
        key = f"{base}_{suffix}"; suffix += 1
    clean_options = []
    if options:
        clean_options = [x.strip() for x in options if x and x.strip()][:25]
    if question_type == "choice" and len(clean_options) < 2:
        conn.close(); return False, "Choice questions need at least two options."
    order = conn.execute("SELECT COALESCE(MAX(sort_order),0)+10 FROM intake_questions WHERE schema_id=?", (schema["id"],)).fetchone()[0]
    ts = now_iso()
    conn.execute("""
        INSERT INTO intake_questions(schema_id,service_id,question_key,label,question_type,required,sort_order,options_json,active,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,1,?,?)
    """, (schema["id"], service_id, key, label, question_type, int(bool(required)), order, json.dumps(clean_options), ts, ts))
    conn.commit(); conn.close()
    return True, "Intake question added. It remains configuration only until a channel explicitly uses this schema."


def toggle_intake_question(business_id, question_id):
    conn = connect(); ensure_business_config_schema(conn)
    row = conn.execute("""
        SELECT q.id, q.active FROM intake_questions q
        JOIN intake_schemas s ON s.id=q.schema_id
        WHERE q.id=? AND s.business_id=?
    """, (question_id, business_id)).fetchone()
    if not row:
        conn.close(); return False, "Intake question not found for this business."
    new_value = 0 if row["active"] else 1
    conn.execute("UPDATE intake_questions SET active=?, updated_at=? WHERE id=?", (new_value, now_iso(), question_id))
    conn.commit(); conn.close()
    return True, "Question enabled." if new_value else "Question disabled. Historical configuration was preserved."


def configuration_view(conn, business_id):
    ensure_business_config_schema(conn)
    services = list_services(conn, business_id, include_inactive=True)
    schema = get_or_create_default_schema(conn, business_id)
    questions = conn.execute("""
        SELECT q.*, bs.name service_name
        FROM intake_questions q
        LEFT JOIN business_services bs ON bs.id=q.service_id
        WHERE q.schema_id=?
        ORDER BY q.sort_order, q.id
    """, (schema["id"],)).fetchall()
    profile = conn.execute("SELECT * FROM client_profiles WHERE business_id=?", (business_id,)).fetchone()
    return {
        "services": services,
        "active_services": sum(1 for s in services if s["active"]),
        "schema": schema,
        "questions": questions,
        "active_questions": sum(1 for q in questions if q["active"]),
        "profile": dict(profile) if profile else {},
        "question_types": sorted(QUESTION_TYPES),
    }
