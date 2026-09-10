from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.db import connect
from services.operator_search import search_operator_records
from services.customer_continuity import customer_continuity
from services.version import VERSION, RELEASE_NAME, BUILD_ID


def check(name, ok, detail=''):
    marker = 'PASS' if ok else 'FAIL'
    suffix = f' · {detail}' if detail else ''
    print(f'{marker} · {name}{suffix}')
    if not ok:
        raise SystemExit(1)


def static_checks():
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
    lead = (ROOT / 'templates' / 'lead_detail.html').read_text(encoding='utf-8')
    search = (ROOT / 'templates' / 'search_results.html').read_text(encoding='utf-8')
    css = (ROOT / 'static' / 'v105.css').read_text(encoding='utf-8')
    op = (ROOT / 'services' / 'operator_search.py').read_text(encoding='utf-8')
    continuity = (ROOT / 'services' / 'customer_continuity.py').read_text(encoding='utf-8')

    check('Version identity', VERSION == 'v10.5' and RELEASE_NAME == 'Operator Experience' and BUILD_ID == 'v10.5-operator-experience', f'{VERSION} · {RELEASE_NAME} · {BUILD_ID}')
    check('Global search route', '@app.route("/search")' in app and 'search_operator_records' in app)
    check('Search is read-only', all(token not in op for token in ['INSERT INTO', 'UPDATE ', 'DELETE FROM']))
    check('Search result cap', 'PER_GROUP_LIMIT = 8' in op and 'min(int(per_group), 20)' in op)
    check('Customer continuity wired', 'customer_continuity(conn, lead_id)' in app and 'CUSTOMER CONTINUITY' in lead)
    check('Continuity boundary declared', 'WHERE business_id=?' in continuity and 'normalize_phone' in continuity)
    check('No fuzzy merge language', 'fuzzy' not in continuity.lower() and 'merge' in continuity.lower())
    check('Topbar search', "url_for('global_search')" in base and 'role="search"' in base)
    check('v10.5 visual layer', 'v105.css' in base and 'Business OS v10.5' in css)
    check('Context anchors', all(anchor in lead for anchor in ['id="customer-story"', 'id="customer-communication"', 'id="scheduling"']))
    check('Search truthfulness copy', 'never merges customer records' in search.lower())
    check('No provider unlocks', all(token not in op + continuity for token in ['execute_sms', 'retell', 'requests.post', 'httpx', 'twilio']))


def fixture_checks():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
    CREATE TABLE businesses(id INTEGER PRIMARY KEY,name TEXT,city TEXT,category TEXT,phone TEXT,email TEXT,status TEXT,lifecycle_stage TEXT);
    CREATE TABLE leads(id INTEGER PRIMARY KEY,business_id INTEGER,caller_name TEXT,phone TEXT,address TEXT,service_type TEXT,issue_description TEXT,status TEXT,priority TEXT,quarantine_status TEXT,created_at TEXT);
    CREATE TABLE calls(id INTEGER PRIMARY KEY,business_id INTEGER,lead_id INTEGER,caller_phone TEXT,summary TEXT,call_status TEXT,created_at TEXT);
    CREATE TABLE appointments(id INTEGER PRIMARY KEY,business_id INTEGER,lead_id INTEGER,start_at TEXT,status TEXT,service_type TEXT,address TEXT,updated_at TEXT,created_at TEXT);
    CREATE TABLE outbound_messages(id INTEGER PRIMARY KEY,business_id INTEGER,lead_id INTEGER,recipient TEXT,body TEXT,status TEXT,created_at TEXT,sent_at TEXT,approved_at TEXT);
    ''')
    conn.execute("INSERT INTO businesses VALUES(1,'Acme Tree','Edison','Tree Care','732-555-1111','a@example.com','Client','ACTIVE')")
    conn.execute("INSERT INTO businesses VALUES(2,'Beta Plumbing','Woodbridge','Plumbing','732-555-2222','b@example.com','Client','ACTIVE')")
    conn.execute("INSERT INTO leads VALUES(1,1,'John Smith','(732) 555-9000','1 Main','Tree Removal','Large oak','New','Normal','Not Required','2026-09-10T10:00')")
    conn.execute("INSERT INTO leads VALUES(2,1,'John Smith','7325559000','1 Main','Stump Removal','Old stump','Won','Normal','Not Required','2026-08-01T10:00')")
    conn.execute("INSERT INTO leads VALUES(3,2,'Other Person','7325559000','2 Main','Leak','Pipe leak','New','Normal','Not Required','2026-09-10T11:00')")
    conn.execute("INSERT INTO calls VALUES(1,1,1,'732-555-9000','Asked about oak removal','Completed','2026-09-10T10:01')")
    conn.execute("INSERT INTO appointments VALUES(1,1,1,'2026-09-12T09:00','Scheduled','Tree Removal','1 Main','','2026-09-10T10:05')")
    conn.execute("INSERT INTO outbound_messages VALUES(1,1,1,'7325559000','Thanks John','Pending Approval','2026-09-10T10:06','','')")
    conn.commit()

    result = search_operator_records(conn, '7325559000')
    names = {group['name'] for group in result['groups']}
    check('Normalized phone search', {'Leads','Calls','Appointments','Messages'}.issubset(names), ', '.join(sorted(names)))

    scoped = search_operator_records(conn, '7325559000', business_id=1)
    leaked = [item for group in scoped['groups'] for item in group['results'] if item.get('business_id') not in (None, 1)]
    check('Search business scope', not leaked, f'leaks={len(leaked)}')

    context = customer_continuity(conn, 1)
    ids = {row['id'] for row in context['related_leads']}
    check('Continuity exact same-business phone', ids == {1,2}, f'lead_ids={sorted(ids)}')
    check('Continuity cross-business isolation', 3 not in ids)
    conn.close()


def live_db_checks():
    conn = connect()
    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    check('Database integrity', integrity == 'ok', integrity)

    fk_violations = conn.execute('PRAGMA foreign_key_check').fetchall()
    check('Foreign keys', len(fk_violations) == 0, f'violations={len(fk_violations)}')

    # v10.5 adds no schema migration; existing v10.4 front-office tables must remain.
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'businesses','leads','calls','appointments','outbound_messages','lead_service_links','lead_intake_answers'}
    check('v10.4 schema preserved', required.issubset(tables), f'missing={sorted(required - tables)}')
    conn.close()


if __name__ == '__main__':
    static_checks()
    fixture_checks()
    live_db_checks()
    print('Business OS v10.5 · Operator Experience · v10.5-operator-experience')
