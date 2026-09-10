from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.version import VERSION, RELEASE_NAME, BUILD_ID
required = [
    ROOT/'static'/'v101.css', ROOT/'static'/'v101.js', ROOT/'static'/'business-os-mark.svg',
    ROOT/'templates'/'base.html', ROOT/'templates'/'dashboard.html',
    ROOT/'services'/'control_plane.py', ROOT/'scripts'/'verify_v10.py'
]
missing=[str(p.relative_to(ROOT)) for p in required if not p.exists()]
base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
dash=(ROOT/'templates'/'dashboard.html').read_text(encoding='utf-8')
checks={
 'Version identity': VERSION=='v10.1' and BUILD_ID=='v10.1-executive-console',
 'Executive shell': 'data-command-open' in base and 'AI FRONT OFFICE' in base,
 'Command palette': 'data-command-results' in base and 'v101.js' in base,
 'Operating brief': 'OPERATING BRIEF' in dash and 'What needs you now' in dash,
 'Control Plane preserved': "url_for('control_plane')" in base and "url_for('control_plane')" in dash,
 'Improvement loop preserved': "url_for('improvements')" in base and "url_for('improvements')" in dash,
 'Required assets': not missing,
}
print(f'Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}')
for name,ok in checks.items(): print(('PASS' if ok else 'FAIL').ljust(6), name)
if missing: print('Missing:', ', '.join(missing))
raise SystemExit(0 if all(checks.values()) else 1)
