from services.db import connect, init_db
from services.system_health import build_health_report

init_db()
conn = connect()
report = build_health_report(conn)
conn.close()
print("BUSINESS OS RELIABILITY CHECK")
print("=" * 36)
for item in report["checks"]:
    print(("PASS" if item["ok"] else "CHECK") + "  " + item["name"] + " - " + item["detail"])
print("=" * 36)
print(f"{report['healthy_checks']}/{report['total_checks']} checks passing · {report['status']}")
