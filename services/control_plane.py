import json
from datetime import datetime, timedelta
from services.db import connect, now_iso

SEVERITY_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Info": 1}


def ensure_control_plane_schema(conn=None):
    own = conn is None
    conn = conn or connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS system_ledger (
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
    CREATE INDEX IF NOT EXISTS idx_system_ledger_created ON system_ledger(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_system_ledger_business ON system_ledger(business_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS policy_decisions (
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
    CREATE INDEX IF NOT EXISTS idx_policy_decisions_created ON policy_decisions(created_at DESC);

    CREATE TABLE IF NOT EXISTS improvement_proposals (
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
    """)
    conn.commit()
    if own:
        conn.close()


def ledger_event(event_type, title, detail="", severity="Info", source="Business OS", business_id=None, lead_id=None, outcome=""):
    conn = connect(); ensure_control_plane_schema(conn)
    cur = conn.execute("""INSERT INTO system_ledger(event_type,severity,source,business_id,lead_id,title,detail,outcome,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)""", (event_type,severity,source,business_id,lead_id,title,detail,outcome,now_iso()))
    conn.commit(); event_id=cur.lastrowid; conn.close(); return event_id


def policy_decision(action_type, decision, reason, *, business_id=None, lead_id=None, context=None):
    decision = decision.upper().strip()
    if decision not in {"ALLOW","APPROVAL","BLOCK"}:
        raise ValueError("Policy decision must be ALLOW, APPROVAL, or BLOCK")
    conn=connect(); ensure_control_plane_schema(conn)
    cur=conn.execute("""INSERT INTO policy_decisions(action_type,business_id,lead_id,decision,reason,context_json,created_at)
        VALUES(?,?,?,?,?,?,?)""",(action_type,business_id,lead_id,decision,reason,json.dumps(context or {},sort_keys=True),now_iso()))
    conn.commit(); did=cur.lastrowid; conn.close()
    ledger_event("Policy", f"{decision}: {action_type}", reason, "High" if decision=="BLOCK" else "Info", "Policy Engine", business_id, lead_id, decision)
    return did


def _count(conn, sql, args=()): return conn.execute(sql,args).fetchone()[0]

def sync_improvement_proposals(conn):
    ensure_control_plane_schema(conn)
    candidates=[]
    failed=_count(conn,"SELECT COUNT(*) FROM outbound_messages WHERE status='Failed'")
    if failed:
        candidates.append(("delivery-failures","High","Delivery Reliability","Repeated delivery failures need review",f"{failed} outbound message(s) are currently failed.","Review provider errors and recovery policy before enabling live delivery.",failed))
    prodq=_count(conn,"SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND UPPER(COALESCE(classification,''))='PRODUCTION'")
    if prodq:
        candidates.append(("production-quarantine","Critical","Data Governance","Production records are quarantined",f"{prodq} production item(s) are blocked by quarantine.","Resolve ownership/classification evidence before any automation proceeds.",prodq))
    legacy=_count(conn,"SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND UPPER(COALESCE(classification,''))!='PRODUCTION'")
    if legacy:
        candidates.append(("legacy-quarantine","Info","Data Governance","Legacy records remain safely isolated",f"{legacy} legacy/test/unverified item(s) remain quarantined.","Keep isolated unless ownership can be proven. No action is required for production readiness.",legacy))
    onboarding=_count(conn,"SELECT COUNT(*) FROM businesses WHERE status='Client' AND UPPER(COALESCE(lifecycle_stage,''))!='ACTIVE'")
    if onboarding:
        candidates.append(("client-readiness","Medium","Client Readiness","Clients still need activation readiness",f"{onboarding} client record(s) are not ACTIVE.","Complete onboarding requirements and activate only after the readiness gate passes.",onboarding))
    now=now_iso()
    for fp,sev,area,title,obs,rec,count in candidates:
        conn.execute("""INSERT INTO improvement_proposals(fingerprint,severity,area,title,observation,recommendation,evidence_count,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,'Proposed',?,?) ON CONFLICT(fingerprint) DO UPDATE SET severity=excluded.severity,area=excluded.area,title=excluded.title,observation=excluded.observation,recommendation=excluded.recommendation,evidence_count=excluded.evidence_count,updated_at=excluded.updated_at""",(fp,sev,area,title,obs,rec,count,now,now))
    conn.commit()


def control_plane_overview(conn):
    ensure_control_plane_schema(conn); sync_improvement_proposals(conn)
    active=_count(conn,"SELECT COUNT(*) FROM businesses WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE'")
    attention=_count(conn,"SELECT COUNT(*) FROM leads WHERE status NOT IN ('Won','Lost') AND (priority='Urgent' OR COALESCE(safety_flag,'')!='')")
    prodq=_count(conn,"SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND UPPER(COALESCE(classification,''))='PRODUCTION'")
    failures=_count(conn,"SELECT COUNT(*) FROM outbound_messages WHERE status='Failed'")
    action_failures = 0
    try:
        action_failures = _count(conn,"SELECT COUNT(*) FROM actions WHERE status IN ('UNKNOWN','FAILED_PERMANENT')")
    except Exception:
        action_failures = 0
    approvals=_count(conn,"SELECT COUNT(*) FROM approvals WHERE status='Pending'") + _count(conn,"SELECT COUNT(*) FROM outbound_messages WHERE status='Pending Approval'")
    improvements=_count(conn,"SELECT COUNT(*) FROM improvement_proposals WHERE status='Proposed'")
    ledger=conn.execute("SELECT * FROM system_ledger ORDER BY id DESC LIMIT 12").fetchall()
    decisions=conn.execute("SELECT * FROM policy_decisions ORDER BY id DESC LIMIT 8").fetchall()
    proposals=conn.execute("SELECT * FROM improvement_proposals ORDER BY CASE severity WHEN 'Critical' THEN 4 WHEN 'High' THEN 3 WHEN 'Medium' THEN 2 ELSE 1 END DESC, id DESC LIMIT 8").fetchall()
    blockers=prodq+failures+action_failures
    state="Protected" if blockers==0 else "Attention"
    return {"state":state,"active_clients":active,"attention":attention + action_failures,"production_quarantine":prodq,"failed_messages":failures,"action_failures":action_failures,"pending_approvals":approvals,"improvements":improvements,"ledger":ledger,"decisions":decisions,"proposals":proposals}


def command_center_summary(conn):
    ensure_control_plane_schema(conn); sync_improvement_proposals(conn)
    return {
      "active_clients": _count(conn,"SELECT COUNT(*) FROM businesses WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE'"),
      "calls": _count(conn,"SELECT COUNT(*) FROM calls"),
      "appointments": _count(conn,"SELECT COUNT(*) FROM appointments WHERE status='Scheduled'"),
      "attention": _count(conn,"SELECT COUNT(*) FROM leads WHERE status NOT IN ('Won','Lost') AND (priority='Urgent' OR COALESCE(safety_flag,'')!='')") + _count(conn,"SELECT COUNT(*) FROM outbound_messages WHERE status='Failed'") + (_count(conn,"SELECT COUNT(*) FROM actions WHERE status IN ('UNKNOWN','FAILED_PERMANENT')") if 'actions' in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} else 0),
      "quarantine": _count(conn,"SELECT COUNT(*) FROM quarantine_items WHERE status='Open'"),
      "prod_quarantine": _count(conn,"SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND UPPER(COALESCE(classification,''))='PRODUCTION'"),
      "improvements": _count(conn,"SELECT COUNT(*) FROM improvement_proposals WHERE status='Proposed'"),
      "ledger_events": _count(conn,"SELECT COUNT(*) FROM system_ledger"),
      "recent_activity": conn.execute("""SELECT 'Lead' kind, COALESCE(caller_name,'Lead #'||id) title, COALESCE(service_type,'New opportunity') detail, created_at FROM leads UNION ALL SELECT 'Call', COALESCE(caller_name,'Call #'||calls.id), COALESCE(summary,'Call captured'), calls.created_at FROM calls LEFT JOIN leads ON leads.id=calls.lead_id ORDER BY created_at DESC LIMIT 7""").fetchall(),
      "today_schedule": conn.execute("""SELECT appointments.*, leads.caller_name, businesses.name business_name FROM appointments LEFT JOIN leads ON leads.id=appointments.lead_id LEFT JOIN businesses ON businesses.id=appointments.business_id WHERE appointments.status='Scheduled' AND date(appointments.start_at)=date('now','localtime') ORDER BY appointments.start_at LIMIT 6""").fetchall(),
    }


def review_improvement(proposal_id, status, note=""):
    if status not in {"Accepted","Dismissed","Proposed"}: return False
    conn=connect(); ensure_control_plane_schema(conn)
    row=conn.execute("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,)).fetchone()
    if not row: conn.close(); return False
    conn.execute("UPDATE improvement_proposals SET status=?,review_note=?,updated_at=? WHERE id=?",(status,note.strip(),now_iso(),proposal_id)); conn.commit(); conn.close()
    ledger_event("Improvement", f"Improvement proposal {status.lower()}", row['title'], "Info", "Human Review", outcome=status)
    return True
