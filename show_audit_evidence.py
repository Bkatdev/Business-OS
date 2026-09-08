import sqlite3

connection = sqlite3.connect("business_os.db")
connection.row_factory = sqlite3.Row

rows = connection.execute(
    """
    SELECT name, audit_evidence
    FROM businesses
    WHERE audit_status = 'completed'
    AND name NOT LIKE 'Example %'
    ORDER BY name
    """
).fetchall()

for row in rows:
    print()
    print("=" * 70)
    print(row["name"])
    print("=" * 70)
    print(row["audit_evidence"])

connection.close()