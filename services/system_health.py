from datetime import datetime, timedelta


def build_health_report(conn):
    def count(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    unassigned_leads = count("SELECT COUNT(*) FROM leads WHERE business_id IS NULL")
    unassigned_calls = count("SELECT COUNT(*) FROM calls WHERE business_id IS NULL")
    unassigned_messages = count("SELECT COUNT(*) FROM outbound_messages WHERE business_id IS NULL")
    failed_messages = count("SELECT COUNT(*) FROM outbound_messages WHERE status = 'Failed'")
    pending_messages = count("SELECT COUNT(*) FROM outbound_messages WHERE status = 'Pending Approval'")
    blocked_24h = count("SELECT COUNT(*) FROM automation_executions WHERE status = 'Blocked' AND created_at >= ?", ((datetime.now()-timedelta(hours=24)).isoformat(timespec='seconds'),))
    clients = count("SELECT COUNT(*) FROM businesses WHERE status = 'Client'")
    mapped_clients = count("SELECT COUNT(*) FROM businesses WHERE status = 'Client' AND TRIM(COALESCE(retell_agent_id,'')) != ''")
    orphan_appointments = count("SELECT COUNT(*) FROM appointments a LEFT JOIN leads l ON l.id=a.lead_id WHERE l.id IS NULL")

    checks = [
        {"name":"Database", "ok": True, "detail":"SQLite connection and health queries passed."},
        {"name":"Client ownership", "ok": unassigned_messages == 0, "detail": f"{unassigned_messages} outbound message(s) missing client ownership." if unassigned_messages else "Every outbound message has client ownership."},
        {"name":"Receptionist mapping", "ok": clients == 0 or mapped_clients == clients, "detail": f"{mapped_clients}/{clients} client(s) have a Retell agent mapping."},
        {"name":"Automation failures", "ok": failed_messages == 0, "detail": f"{failed_messages} failed message(s) need attention." if failed_messages else "No failed messages waiting."},
        {"name":"Data integrity", "ok": orphan_appointments == 0, "detail": f"{orphan_appointments} orphan appointment(s) found." if orphan_appointments else "Appointment links are intact."},
    ]
    healthy = sum(1 for item in checks if item["ok"])
    return {
        "status": "Healthy" if healthy == len(checks) else "Attention",
        "healthy_checks": healthy, "total_checks": len(checks), "checks": checks,
        "unassigned_leads": unassigned_leads, "unassigned_calls": unassigned_calls,
        "unassigned_messages": unassigned_messages, "failed_messages": failed_messages,
        "pending_messages": pending_messages, "blocked_24h": blocked_24h,
        "clients": clients, "mapped_clients": mapped_clients,
    }
