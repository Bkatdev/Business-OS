from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.db import connect
from services.version import VERSION, RELEASE_NAME, BUILD_ID
checks=[]
def check(name, ok):
    checks.append((name,bool(ok)))
    print(('PASS' if ok else 'FAIL').ljust(7), name)
base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
dash=(ROOT/'templates'/'dashboard.html').read_text(encoding='utf-8')
check('Version identity', VERSION=='v10.2' and BUILD_ID=='v10.2-v92-restoration')
check('v9.2 shell restored', 'class="app-shell"' in base and 'class="sidebar"' in base and 'v92_signature.css' in base)
check('v10/v10.1 presentation detached', 'v10.css' not in base and 'v101.css' not in base and 'bos-app' not in base)
check('Control Plane navigation preserved', "url_for('control_plane')" in base and "url_for('system_map')" in base and "url_for('improvements')" in base)
check('v9.2 dashboard restored', 'command-hero' in dash and 'Action Queue' in dash and 'Lead Progress' in dash)
check('Control Plane dashboard signal', 'v102-control-strip' in dash)
check('Restoration stylesheet', (ROOT/'static'/'v102_restore.css').exists())
conn=connect(); tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}; conn.close()
check('Control Plane schema preserved', {'system_ledger','policy_decisions','improvement_proposals'}.issubset(tables))
if not all(v for _,v in checks): raise SystemExit(1)
print(f'Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}')
