from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
try:
 from app import app
 from services.db import connect
except Exception as e:
 print('SKIP V22 saved-demo browser render: '+str(e)); raise SystemExit(0)
c=connect(); rows=c.execute("SELECT id,business_id,design_family FROM v16_site_demos WHERE design_family LIKE 'AI_AGENT_V%' ORDER BY id DESC LIMIT 2").fetchall(); c.close()
if not rows: print('SKIP V22 saved-demo render: no persisted AI demos'); raise SystemExit(0)
client=app.test_client()
for r in rows:
 res=client.get(f'/business/{r["business_id"]}/v16/demo/{r["id"]}')
 assert res.status_code==200,(r['id'],res.status_code)
 body=res.get_data(as_text=True)
 assert 'v19_agent_site.css?v=22' in body
 assert 'PRIVATE WEBSITE CONCEPT' in body and 'name="message"' in body
 assert res.headers.get('X-Robots-Tag')=='noindex, nofollow, noarchive'
 print(f'PASS V22 saved-demo render: demo #{r["id"]}, {len(res.data)} bytes')
