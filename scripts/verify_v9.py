from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.db import connect
from services.version import VERSION, RELEASE_NAME, BUILD_ID
from services.product_foundation import ensure_product_schema
c=connect(); ensure_product_schema(c)
tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required={'client_profiles','client_activation_events','quarantine_items','reliability_runs','data_snapshots'}
missing=sorted(required-tables)
print(f"Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}")
print(f"Project root: {ROOT}")
print(f"Database: {ROOT/'business_os.db'}")
print('Product schema:', 'PASS' if not missing else 'FAIL '+', '.join(missing))
print('Foreign keys:', c.execute('PRAGMA foreign_keys').fetchone()[0])
print('Journal mode:', c.execute('PRAGMA journal_mode').fetchone()[0])
print('Client profiles:', c.execute('SELECT COUNT(*) FROM client_profiles').fetchone()[0])
c.close()
raise SystemExit(1 if missing else 0)
