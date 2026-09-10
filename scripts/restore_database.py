"""Safe local SQLite recovery helper.

List snapshots:
    python scripts/restore_database.py --list

Restore one snapshot (Flask should be stopped first):
    python scripts/restore_database.py business_os-YYYYMMDD-HHMMSS.db --confirm
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.db import DB_PATH
from services.reliability import BACKUP_DIR, create_database_snapshot


def valid_snapshot(path: Path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def list_snapshots():
    paths = sorted(BACKUP_DIR.glob("business_os-*.db"), reverse=True)
    if not paths:
        print("No database snapshots found.")
        return
    for path in paths:
        print(f"{path.name}  {path.stat().st_size:,} bytes")


def restore(filename: str, confirmed: bool):
    if not confirmed:
        print("Restore blocked. Re-run with --confirm after stopping Flask.")
        return 2
    source = (BACKUP_DIR / Path(filename).name).resolve()
    if source.parent != BACKUP_DIR.resolve() or not source.exists():
        print("Snapshot not found in the Business OS backup directory.")
        return 2
    if not valid_snapshot(source):
        print("Restore blocked: selected snapshot failed integrity_check.")
        return 3

    safety = create_database_snapshot("Pre-restore safety snapshot")
    src = sqlite3.connect(source)
    dst = sqlite3.connect(DB_PATH)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    print("Restore complete.")
    print("Restored:", source.name)
    print("Pre-restore safety snapshot:", safety["filename"])
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.list:
        list_snapshots()
        return 0
    if not args.snapshot:
        parser.print_help()
        return 1
    return restore(args.snapshot, args.confirm)


if __name__ == "__main__":
    raise SystemExit(main())
