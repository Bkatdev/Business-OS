from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.db import connect
from services.business_config import ensure_business_config_schema
from services.version import VERSION, RELEASE_NAME, BUILD_ID

checks = []

def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))

conn = connect()
ensure_business_config_schema(conn)

tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required = {"business_services", "intake_schemas", "intake_questions", "client_profiles"}
check("Configuration schema", required.issubset(tables), f"missing={sorted(required-tables)}")

profile_cols = {r[1] for r in conn.execute("PRAGMA table_info(client_profiles)")}
check("Industry profile field", "industry" in profile_cols)
check("Foreign keys", conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1)
check("Database integrity", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
check("Production quarantine unchanged", conn.execute("SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND classification='PRODUCTION'").fetchone()[0] == 0)
conn.close()

check("Version identity", VERSION == "v10.3" and RELEASE_NAME == "Business Configuration Foundation" and BUILD_ID == "v10.3-business-config")

# Prove the universal model can represent multiple industries without changing schema.
mem = sqlite3.connect(":memory:")
mem.row_factory = sqlite3.Row
mem.execute("PRAGMA foreign_keys=ON")
mem.execute("CREATE TABLE businesses (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
mem.execute("CREATE TABLE client_profiles (business_id INTEGER PRIMARY KEY, services TEXT NOT NULL DEFAULT '', business_hours TEXT NOT NULL DEFAULT '', service_area TEXT NOT NULL DEFAULT '', emergency_rules TEXT NOT NULL DEFAULT '', escalation_instructions TEXT NOT NULL DEFAULT '', scheduling_policy TEXT NOT NULL DEFAULT '', messaging_tone TEXT NOT NULL DEFAULT '', onboarding_notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE)")
ensure_business_config_schema(mem)
examples = [
    (1, "Tree Co", "Tree Removal", "Are utility lines involved?"),
    (2, "Plumbing Co", "Drain Cleaning", "Is water actively leaking?"),
    (3, "Dental Co", "Emergency Exam", "Are you a new or existing patient?"),
]
for bid, name, service, question in examples:
    mem.execute("INSERT INTO businesses(id,name) VALUES(?,?)", (bid,name))
    ts = "test"
    cur = mem.execute("INSERT INTO business_services(business_id,name,created_at,updated_at) VALUES(?,?,?,?)", (bid,service,ts,ts))
    schema = mem.execute("INSERT INTO intake_schemas(business_id,name,status,created_at,updated_at) VALUES(?,?,'Draft',?,?)", (bid,'Default Intake',ts,ts)).lastrowid
    mem.execute("INSERT INTO intake_questions(schema_id,service_id,question_key,label,question_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (schema,cur.lastrowid,'q1',question,'yes_no',ts,ts))
mem.commit()
check("Multi-industry model", mem.execute("SELECT COUNT(*) FROM business_services").fetchone()[0] == 3 and mem.execute("SELECT COUNT(*) FROM intake_questions").fetchone()[0] == 3)
mem.close()

# Forward-compatible regression guard for the v10.2 restoration.
# The historical verify_v102.py correctly pins VERSION==v10.2 and therefore
# should not be expected to pass after a legitimate later release changes version.py.
base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
dash = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
check("v9.2 shell preserved", 'class="app-shell"' in base and 'class="sidebar"' in base and "v92_signature.css" in base)
check("v10.2 restoration stylesheet", "v102_restore.css" in base and (ROOT / "static" / "v102_restore.css").exists())
check("v10.3 stylesheet layered", "v103.css" in base and (ROOT / "static" / "v103.css").exists())
check("Old experimental shells detached", "v10.css" not in base and "v101.css" not in base and "v10.js" not in base and "v101.js" not in base and "bos-app" not in base)
check("Control Plane navigation preserved", "url_for('control_plane')" in base and "url_for('system_map')" in base and "url_for('improvements')" in base)
check("v9.2 dashboard preserved", "command-hero" in dash and "Action Queue" in dash and "Lead Progress" in dash)
check("Control Plane dashboard signal", "v102-control-strip" in dash)

failed = [x for x in checks if not x[1]]
for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL':7} {name}" + (f" · {detail}" if detail else ""))
print(f"Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}")
if failed:
    raise SystemExit(1)
