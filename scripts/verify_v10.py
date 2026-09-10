from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.db import connect
from services.control_plane import ensure_control_plane_schema, control_plane_overview
from services.version import VERSION,RELEASE_NAME,BUILD_ID
c=connect(); ensure_control_plane_schema(c)
tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; required={'system_ledger','policy_decisions','improvement_proposals','client_profiles','quarantine_items','reliability_runs'}; missing=required-tables
overview=control_plane_overview(c)
print(f"Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}")
print('Control Plane schema:', 'PASS' if not missing else 'FAIL '+','.join(sorted(missing)))
print('Foreign keys:',c.execute('PRAGMA foreign_keys').fetchone()[0]); print('Journal mode:',c.execute('PRAGMA journal_mode').fetchone()[0]); print('System state:',overview['state']); print('Improvement proposals:',overview['improvements']); print('Production quarantine:',overview['production_quarantine']); c.close(); raise SystemExit(1 if missing else 0)
