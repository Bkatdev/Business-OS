from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from services.db import connect

app.config['TESTING']=True
app.config['PROPAGATE_EXCEPTIONS']=True

with app.test_client() as client:
    c=connect()
    row=c.execute("SELECT id,business_id FROM v16_site_demos WHERE design_family IN ('AI_AGENT_V19','AI_AGENT_V20') ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not row:
        raise SystemExit('SKIP: no persisted AI demo exists yet.')
    r=client.get(f"/business/{row['business_id']}/v16/demo/{row['id']}")
    assert r.status_code==200, f'Expected 200, got {r.status_code}'
    html=r.get_data(as_text=True)
    assert 'v19_agent_site.css' in html
    assert '<form' in html
    assert 'noindex' in html.lower()
    print(f"PASS: persisted AI demo #{row['id']} rendered ({len(r.data)} bytes) with V20 presentation QA.")
