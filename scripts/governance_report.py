"""Read-only governance report for Business OS.

Usage: python scripts/governance_report.py
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.db import connect, init_db


def main():
    init_db()
    conn = connect()
    try:
        print("=" * 64)
        print(" BUSINESS OS · DATA GOVERNANCE REPORT")
        print("=" * 64)
        print("\nCLIENT LIFECYCLE")
        for row in conn.execute("SELECT lifecycle_stage, COUNT(*) n FROM businesses GROUP BY lifecycle_stage ORDER BY lifecycle_stage"):
            print(f"  {row['lifecycle_stage']:<12} {row['n']}")
        print("\nLEAD CLASSIFICATION")
        for row in conn.execute("SELECT data_classification, COUNT(*) n FROM leads GROUP BY data_classification ORDER BY data_classification"):
            print(f"  {row['data_classification']:<12} {row['n']}")
        print("\nOPEN QUARANTINE")
        rows = conn.execute("SELECT * FROM quarantine_items WHERE status='Open' ORDER BY id").fetchall()
        if not rows:
            print("  None")
        for row in rows:
            print(f"  #{row['id']} {row['entity_type']}:{row['entity_id']} [{row['classification']}] {row['reason_code']}")
            print(f"      {row['reason_detail']}")
        print("\nNo records are changed by this report.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
