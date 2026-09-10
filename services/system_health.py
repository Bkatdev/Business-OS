from datetime import datetime, timedelta


def build_health_report(conn):
    def count(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    unassigned_leads = count("SELECT COUNT(*) FROM leads WHERE business_id IS NULL")
    unassigned_calls = count("SELECT COUNT(*) FROM calls WHERE business_id IS NULL")
    failed_messages = count("SELECT COUNT(*) FROM outbound_messages WHERE status='Failed'")
    pending_messages = count("SELECT COUNT(*) FROM outbound_messages WHERE status='Pending Approval'")
    blocked_24h = count("SELECT COUNT(*) FROM automation_executions WHERE status='Blocked' AND created_at >= ?",
                       ((datetime.now()-timedelta(hours=24)).isoformat(timespec='seconds'),))
    active_clients = count("SELECT COUNT(*) FROM businesses WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE'")
    mapped_clients = count("SELECT COUNT(*) FROM businesses WHERE UPPER(COALESCE(lifecycle_stage,''))='ACTIVE' AND TRIM(COALESCE(retell_agent_id,''))!=''")
    orphan_appointments = count("SELECT COUNT(*) FROM appointments a LEFT JOIN leads l ON l.id=a.lead_id WHERE l.id IS NULL")
    open_quarantine = count("SELECT COUNT(*) FROM quarantine_items WHERE status='Open'")
    production_quarantine = count("SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND UPPER(COALESCE(classification,''))='PRODUCTION'")

    checks = [
        {"name":"Database", "ok": True, "detail":"SQLite connection and health queries passed."},
        {"name":"Production quarantine", "ok": production_quarantine == 0,
         "detail": f"{production_quarantine} production quarantine item(s) require attention." if production_quarantine else f"No production data is quarantined. {open_quarantine} non-production item(s) remain safely isolated."},
        {"name":"Active-client routing", "ok": active_clients == mapped_clients,
         "detail": f"{mapped_clients}/{active_clients} ACTIVE client(s) have exact Retell routing." if active_clients else "No ACTIVE clients require production routing yet."},
        {"name":"Automation failures", "ok": failed_messages == 0,
         "detail": f"{failed_messages} failed message(s) need attention." if failed_messages else "No failed messages waiting."},
        {"name":"Data integrity", "ok": orphan_appointments == 0,
         "detail": f"{orphan_appointments} orphan appointment(s) found." if orphan_appointments else "Appointment links are intact."},
    ]
    healthy = sum(1 for item in checks if item["ok"])
    return {
        "status": "Healthy" if healthy == len(checks) else "Attention",
        "healthy_checks": healthy, "total_checks": len(checks), "checks": checks,
        "unassigned_leads": unassigned_leads, "unassigned_calls": unassigned_calls,
        "failed_messages": failed_messages, "pending_messages": pending_messages,
        "blocked_24h": blocked_24h, "clients": active_clients, "mapped_clients": mapped_clients,
        "open_quarantine": open_quarantine, "production_quarantine": production_quarantine,
    }
