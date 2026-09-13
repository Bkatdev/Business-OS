from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.db import connect
from services.v21_business_knowledge import ensure_v21_schema,rebuild_business_knowledge
c=connect(); ensure_v21_schema(c)
rows=c.execute("SELECT r.business_id,r.id FROM site_intelligence_runs r JOIN (SELECT business_id,MAX(id) id FROM site_intelligence_runs WHERE status='COMPLETED' GROUP BY business_id) x ON x.id=r.id ORDER BY r.business_id").fetchall()
total=0
for bid,rid in rows: total+=len(rebuild_business_knowledge(c,bid,rid))
c.close(); print(f'PASS V21 knowledge backfill: {len(rows)} businesses, {total} persistent knowledge records')
