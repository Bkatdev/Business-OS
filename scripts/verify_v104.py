from pathlib import Path
import sqlite3, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.db import connect
from services.business_config import ensure_business_config_schema
from services.front_office_intelligence import ensure_front_office_schema, lead_intelligence
from services.version import VERSION, RELEASE_NAME, BUILD_ID
checks=[]
def check(name,ok,detail=''): checks.append((name,bool(ok),detail))
c=connect(); ensure_business_config_schema(c); ensure_front_office_schema(c)
tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required={'lead_service_links','lead_intake_answers','business_services','intake_schemas','intake_questions'}
check('Front-office schema',required.issubset(tables),f"missing={sorted(required-tables)}")
check('Foreign keys',c.execute('PRAGMA foreign_keys').fetchone()[0]==1)
check('Database integrity',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
# Tenant-boundary assertions for persisted intelligence records.
viol_links=c.execute('''SELECT COUNT(*) FROM lead_service_links lsl JOIN leads l ON l.id=lsl.lead_id JOIN business_services s ON s.id=lsl.service_id WHERE l.business_id!=lsl.business_id OR s.business_id!=lsl.business_id''').fetchone()[0]
viol_answers=c.execute('''SELECT COUNT(*) FROM lead_intake_answers a JOIN leads l ON l.id=a.lead_id JOIN intake_questions q ON q.id=a.question_id JOIN intake_schemas s ON s.id=q.schema_id WHERE l.business_id!=a.business_id OR s.business_id!=a.business_id''').fetchone()[0]
check('Lead service tenant isolation',viol_links==0,f'violations={viol_links}')
check('Intake answer tenant isolation',viol_answers==0,f'violations={viol_answers}')
check('Production quarantine unchanged',c.execute("SELECT COUNT(*) FROM quarantine_items WHERE status='Open' AND classification='PRODUCTION'").fetchone()[0]==0)
c.close()
check('Version identity',VERSION=='v10.4' and RELEASE_NAME=='Front Office Intelligence' and BUILD_ID=='v10.4-front-office-intelligence')
base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8'); lead=(ROOT/'templates'/'lead_detail.html').read_text(encoding='utf-8'); dash=(ROOT/'templates'/'dashboard.html').read_text(encoding='utf-8')
check('v9.2 shell preserved','class="app-shell"' in base and 'v92_signature.css' in base)
check('v10.2 visual authority','v102_restore.css' in base and 'v10.css' not in base and 'v101.css' not in base)
check('v10.3 configuration preserved','v103.css' in base and (ROOT/'services'/'business_config.py').exists())
check('v10.4 layer','v104.css' in base and (ROOT/'static'/'v104.css').exists())
check('Configuration-aware lead workspace','FRONT OFFICE INTELLIGENCE' in lead and 'Structured service + intake' in lead)
check('Unified customer timeline','CUSTOMER STORY' in lead and 'Unified timeline' in lead)
check('Command Center preserved','Action Queue' in dash and 'Lead Progress' in dash)
failed=[x for x in checks if not x[1]]
for name,ok,detail in checks: print(f"{'PASS' if ok else 'FAIL':7} {name}"+(f' · {detail}' if detail else ''))
print(f'Business OS {VERSION} · {RELEASE_NAME} · {BUILD_ID}')
raise SystemExit(1 if failed else 0)
