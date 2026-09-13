from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.db import connect
try:
    from app import app
except ModuleNotFoundError as e:
    if e.name == "flask":
        print("SKIP V21 saved-demo render: Flask unavailable in this test runtime")
        raise SystemExit(0)
    raise
c=connect(); r=c.execute("SELECT id,business_id FROM v16_site_demos WHERE design_family LIKE 'AI_AGENT_V%' ORDER BY id DESC LIMIT 1").fetchone(); c.close()
if not r:
 print('SKIP V21 saved-demo render: no persisted AI demo in this database')
 raise SystemExit(0)
client=app.test_client(); resp=client.get(f'/business/{r[1]}/v16/demo/{r[0]}'); html=resp.get_data(as_text=True)
assert resp.status_code==200,resp.status_code
assert 'v19_agent_site.css?v=21' in html
assert 'method="post"' in html and '<form' in html
assert 'noindex' in html.lower()
for bad in ('the redesigned experience','place review proof','primary conversion path'):
 assert bad not in html.lower(),bad
print(f'PASS V21 saved-demo render: demo #{r[0]}, {len(resp.data)} bytes, no API call')
