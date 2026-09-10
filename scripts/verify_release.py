"""Non-destructive Business OS release preflight.

Usage:
    python scripts/verify_release.py

Exit code 0 means the release preflight passed. A non-zero exit code means do
not deploy or enable live automation until the reported failure is fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jinja2 import Environment, FileSystemLoader
from services.db import connect, init_db
from services.reliability import run_self_test


def main():
    print("=" * 62)
    print(" BUSINESS OS · RELEASE PREFLIGHT")
    print("=" * 62)

    init_db()

    environment = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    template_errors = []
    for path in sorted((ROOT / "templates").glob("*.html")):
        try:
            environment.get_template(path.name)
        except Exception as exc:  # pragma: no cover - CLI diagnostic
            template_errors.append(f"{path.name}: {exc}")

    if template_errors:
        print("Template validation: FAIL")
        for item in template_errors:
            print("  -", item)
        return 1
    print("Template validation: PASS")

    conn = connect()
    try:
        result = run_self_test(conn, persist=False)
    finally:
        conn.close()

    for check in result["checks"]:
        icon = "PASS" if check["status"] == "pass" else check["status"].upper()
        print(f"{icon:>9}  {check['name']}: {check['detail']}")

    if result["failures"]:
        print("\nRELEASE PREFLIGHT: FAIL")
        print("Do not enable live customer actions until failures are resolved.")
        return 2

    print("\nRELEASE PREFLIGHT: PASS")
    if result["warnings"]:
        print(f"Passed with {result['warnings']} warning(s) to review.")
    else:
        print("All release-blocking checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
