from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from services.db import connect
c=connect(); rows=c.execute("SELECT id,business_id FROM v16_site_demos WHERE design_family LIKE 'AI_AGENT_V%' ORDER BY id DESC LIMIT 6").fetchall(); c.close()
if not rows:
    print('SKIP V23 saved-demo render: no AI demos found')
else:
    client=app.test_client()
    for r in rows:
        resp=client.get(f'/business/{r["business_id"]}/v16/demo/{r["id"]}')
        assert resp.status_code==200,(r['id'],resp.status_code)
        assert resp.headers.get('X-Robots-Tag')=='noindex, nofollow, noarchive'
    print(f'PASS V23 saved-demo render: {len(rows)} persisted AI demo(s), no API call')
