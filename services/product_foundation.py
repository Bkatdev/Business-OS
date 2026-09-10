import json
from services.db import connect, now_iso
from services.business_config import ensure_business_config_schema, list_services

REQUIRED_PROFILE_FIELDS = (
    ("services", "Services", "What the business actually offers"),
    ("business_hours", "Business hours", "When normal calls and appointments can be handled"),
    ("service_area", "Service area", "Where the business accepts work"),
    ("emergency_rules", "Safety + emergency rules", "When AI must stop and escalate"),
    ("escalation_instructions", "Escalation path", "Who receives exceptions and urgent cases"),
    ("scheduling_policy", "Scheduling policy", "What can be scheduled versus requested"),
)


def ensure_product_schema(conn=None):
    own = conn is None
    conn = conn or connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_profiles (
            business_id INTEGER PRIMARY KEY,
            services TEXT NOT NULL DEFAULT '',
            business_hours TEXT NOT NULL DEFAULT '',
            service_area TEXT NOT NULL DEFAULT '',
            emergency_rules TEXT NOT NULL DEFAULT '',
            escalation_instructions TEXT NOT NULL DEFAULT '',
            scheduling_policy TEXT NOT NULL DEFAULT '',
            messaging_tone TEXT NOT NULL DEFAULT 'Professional, warm, concise',
            onboarding_notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_activation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            from_stage TEXT NOT NULL DEFAULT '',
            to_stage TEXT NOT NULL,
            readiness_score INTEGER NOT NULL DEFAULT 0,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
    """)
    ensure_business_config_schema(conn)
    conn.commit()
    if own:
        conn.close()


def _profile(conn, business_id):
    ensure_product_schema(conn)
    row = conn.execute("SELECT * FROM client_profiles WHERE business_id = ?", (business_id,)).fetchone()
    if row:
        return dict(row)
    return {
        "business_id": business_id, "services": "", "business_hours": "", "service_area": "",
        "emergency_rules": "", "escalation_instructions": "", "scheduling_policy": "",
        "messaging_tone": "Professional, warm, concise", "onboarding_notes": "", "industry": "", "updated_at": "",
    }


def readiness_for_business(conn, business):
    b = dict(business)
    profile = _profile(conn, b["id"])
    checks = []
    for key, label, help_text in REQUIRED_PROFILE_FIELDS:
        if key == "services":
            structured = list_services(conn, b["id"], include_inactive=False)
            legacy_ok = bool((profile.get("services") or "").strip())
            ok = bool(structured) or legacy_ok
            if structured:
                label = "Service catalog"
                help_text = f"{len(structured)} active structured service(s) configured"
            elif legacy_ok:
                label = "Service catalog"
                help_text = "Legacy service text exists; convert to structured services when convenient"
        else:
            ok = bool((profile.get(key) or "").strip())
        checks.append({"key": key, "label": label, "help": help_text, "ok": ok, "required": True})
    industry_ok = bool((profile.get("industry") or "").strip() or (b.get("category") or "").strip())
    checks.insert(0, {"key": "industry", "label": "Industry", "help": "Industry context selects guidance, never hard-coded behavior", "ok": industry_ok, "required": True})
    identity_ok = bool((b.get("name") or "").strip() and ((b.get("phone") or "").strip() or (b.get("email") or "").strip()))
    checks.insert(0, {"key": "identity", "label": "Business identity", "help": "Name plus a real contact channel", "ok": identity_ok, "required": True})
    routing_ok = bool((b.get("retell_agent_id") or "").strip())
    checks.append({"key": "retell_agent_id", "label": "Receptionist routing", "help": "Exact Retell agent mapping", "ok": routing_ok, "required": True})
    total = len(checks)
    passed = sum(1 for c in checks if c["ok"])
    score = round((passed / total) * 100) if total else 0
    blockers = [c for c in checks if c["required"] and not c["ok"]]
    return {"score": score, "passed": passed, "total": total, "checks": checks, "blockers": blockers, "ready": not blockers, "profile": profile}


def save_profile(business_id, values):
    conn = connect()
    ensure_product_schema(conn)
    allowed = [x[0] for x in REQUIRED_PROFILE_FIELDS] + ["industry", "messaging_tone", "onboarding_notes"]
    cleaned = {k: (values.get(k) or "").strip() for k in allowed}
    conn.execute("""
        INSERT INTO client_profiles (
            business_id, services, business_hours, service_area, emergency_rules,
            escalation_instructions, scheduling_policy, messaging_tone, onboarding_notes, updated_at, industry
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(business_id) DO UPDATE SET
            services=excluded.services, business_hours=excluded.business_hours,
            service_area=excluded.service_area, emergency_rules=excluded.emergency_rules,
            escalation_instructions=excluded.escalation_instructions,
            scheduling_policy=excluded.scheduling_policy, messaging_tone=excluded.messaging_tone,
            onboarding_notes=excluded.onboarding_notes, updated_at=excluded.updated_at, industry=excluded.industry
    """, (business_id, cleaned["services"], cleaned["business_hours"], cleaned["service_area"], cleaned["emergency_rules"], cleaned["escalation_instructions"], cleaned["scheduling_policy"], cleaned["messaging_tone"], cleaned["onboarding_notes"], now_iso(), cleaned["industry"]))
    conn.commit(); conn.close()


def activate_business(business_id):
    conn = connect(); ensure_product_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    if not business:
        conn.close(); return False, "Business not found."
    readiness = readiness_for_business(conn, business)
    if not readiness["ready"]:
        conn.close(); return False, f"Activation blocked. {len(readiness['blockers'])} required readiness item(s) are incomplete."
    production_quarantine = conn.execute("SELECT COUNT(*) FROM quarantine_items WHERE business_id = ? AND status = 'Open' AND classification = 'PRODUCTION'", (business_id,)).fetchone()[0]
    if production_quarantine:
        conn.close(); return False, "Activation blocked because production data is quarantined."
    old = business["lifecycle_stage"] or "ONBOARDING"
    conn.execute("UPDATE businesses SET lifecycle_stage='ACTIVE', automation_enabled=1, activated_at=?, lifecycle_updated_at=? WHERE id=?", (now_iso(), now_iso(), business_id))
    conn.execute("INSERT INTO client_activation_events (business_id, from_stage, to_stage, readiness_score, detail, created_at) VALUES (?, ?, 'ACTIVE', ?, ?, ?)", (business_id, old, readiness["score"], "Activation passed the v9 readiness gate.", now_iso()))
    conn.commit(); conn.close(); return True, "Client activated. Production policy gates remain enforced."


def client_product_view(conn, business):
    b = dict(business)
    readiness = readiness_for_business(conn, b)
    bid = b["id"]
    counts = {
        "leads": conn.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,)).fetchone()[0],
        "open_leads": conn.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND status NOT IN ('Won','Lost')", (bid,)).fetchone()[0],
        "calls": conn.execute("SELECT COUNT(*) FROM calls WHERE business_id=?", (bid,)).fetchone()[0],
        "appointments": conn.execute("SELECT COUNT(*) FROM appointments WHERE business_id=?", (bid,)).fetchone()[0],
        "failed_messages": conn.execute("SELECT COUNT(*) FROM outbound_messages WHERE business_id=? AND status='Failed'", (bid,)).fetchone()[0],
        "quarantine": conn.execute("SELECT COUNT(*) FROM quarantine_items WHERE business_id=? AND status='Open'", (bid,)).fetchone()[0],
    }
    return {"readiness": readiness, "counts": counts, "stage": b.get("lifecycle_stage") or "ONBOARDING", "automation_enabled": bool(b.get("automation_enabled"))}


def attention_queue(conn, business_id=None, limit=50):
    items = []
    args = []
    business_clause = ""
    if business_id is not None:
        business_clause = " AND leads.business_id = ?"
        args.append(business_id)
    for row in conn.execute(f"""SELECT leads.id, leads.business_id, leads.caller_name, leads.service_type, leads.priority, leads.safety_flag, leads.created_at, businesses.name business_name FROM leads LEFT JOIN businesses ON businesses.id=leads.business_id WHERE leads.status NOT IN ('Won','Lost') AND (leads.priority='Urgent' OR COALESCE(leads.safety_flag,'')!=''){business_clause} ORDER BY leads.id DESC LIMIT 25""", args).fetchall():
        items.append({"severity":"Critical" if row["safety_flag"] else "High", "kind":"Lead", "title": row["caller_name"] or f"Lead #{row['id']}", "detail": row["safety_flag"] or f"Urgent {row['service_type']} opportunity", "business": row["business_name"] or "Unassigned", "href": f"/lead/{row['id']}"})
    qargs=[]; qclause=""
    if business_id is not None:
        qclause=" AND business_id=?"; qargs=[business_id]
    for row in conn.execute(f"SELECT * FROM quarantine_items WHERE status='Open' AND classification='PRODUCTION'{qclause} ORDER BY id DESC LIMIT 25", qargs).fetchall():
        items.append({"severity":"Critical", "kind":"Quarantine", "title":f"Production {row['entity_type']} #{row['entity_id']} blocked", "detail":row['reason_detail'], "business":f"Client #{row['business_id']}" if row['business_id'] else "Unknown client", "href":"/system-health"})
    for row in conn.execute(f"SELECT outbound_messages.id, outbound_messages.business_id, outbound_messages.error, businesses.name business_name FROM outbound_messages LEFT JOIN businesses ON businesses.id=outbound_messages.business_id WHERE outbound_messages.status='Failed'{(' AND outbound_messages.business_id=?' if business_id is not None else '')} ORDER BY outbound_messages.id DESC LIMIT 25", ([business_id] if business_id is not None else [])).fetchall():
        items.append({"severity":"High", "kind":"Delivery", "title":f"Message #{row['id']} failed", "detail":row['error'] or "Delivery failed and needs review.", "business":row['business_name'] or "Unknown client", "href":"/automation"})
    # v11 execution exceptions are provider-neutral and deep-link to the action ledger.
    try:
        action_sql = """SELECT actions.id, actions.business_id, actions.action_type, actions.status,
                               actions.outcome_detail, actions.last_error, businesses.name business_name
                        FROM actions
                        LEFT JOIN businesses ON businesses.id = actions.business_id
                        WHERE actions.status IN ('UNKNOWN','FAILED_PERMANENT')"""
        action_args = []
        if business_id is not None:
            action_sql += " AND actions.business_id = ?"
            action_args.append(business_id)
        action_sql += " ORDER BY actions.id DESC LIMIT 25"
        for row in conn.execute(action_sql, action_args).fetchall():
            items.append({
                "severity": "Critical" if row["status"] == "UNKNOWN" else "High",
                "kind": "Action",
                "title": f"{row['action_type']} action needs review",
                "detail": row["outcome_detail"] or row["last_error"] or "External action outcome needs review.",
                "business": row["business_name"] or "Unknown client",
                "href": f"/automation#action-{row['id']}",
            })
    except Exception:
        # v10.x databases remain readable before init_db creates the v11 tables.
        pass
    rank={"Critical":3,"High":2,"Medium":1}
    items.sort(key=lambda x: rank.get(x["severity"],0), reverse=True)
    return items[:limit]
