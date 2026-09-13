from pathlib import Path
import sqlite3, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.v15_site_intelligence import ensure_intelligence_schema, run_site_intelligence
from services.v21_business_knowledge import ensure_v21_schema, knowledge_view
from services.v21_presentation import prepare_v21_site

def db():
 c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE businesses(id INTEGER PRIMARY KEY,name TEXT,website TEXT,city TEXT,category TEXT,reviews INTEGER,rating REAL,phone TEXT,email TEXT,emergency_service INTEGER,address TEXT)')
 c.execute("INSERT INTO businesses VALUES(1,'Fixture Co','https://fixture.test/','Town','HVAC',0,0,'555-0100','',0,'1 Main St')")
 return c

def fetch(url):
 if url.rstrip('/')=='https://fixture.test':
  return {'url':'https://fixture.test/','status':200,'content_type':'text/html','text':'''<html><head><title>Fixture Heating & Cooling</title><meta name="description" content="Heating repair and AC installation for local homes."></head><body><img src="/logo.png" alt="Fixture logo"><h1>Heating and cooling help</h1><a href="/heating-repair">Heating Repair</a><a href="tel:555-0100">Call us</a><a href="https://facebook.com/fixture">Facebook</a><details><summary>Do you repair furnaces?</summary><p>We provide furnace repair.</p></details></body></html>'''}
 return {'url':'https://fixture.test/heating-repair','status':200,'content_type':'text/html','text':'<html><head><title>Heating Repair</title></head><body><h1>Heating Repair</h1><p>Furnace diagnosis and heating repair.</p></body></html>'}

c=db(); ensure_intelligence_schema(c); ensure_v21_schema(c)
v=run_site_intelligence(c,1,fetcher=fetch,max_pages=4,allow_private=True)
k=knowledge_view(c,1,v['run']['id'])
assert len(v['pages'])==2
assert any(x['knowledge_type']=='PHONE' and '555-0100' in x['value_text'] for x in k)
assert any(x['knowledge_type']=='SERVICE_OR_TOPIC' and 'Heating Repair' in x['value_text'] for x in k)
assert any(x['knowledge_type']=='LOGO_ASSET' for x in k)
assert all(x['truth_state']=='PUBLIC_VERIFIED' for x in k)
assert any(x['source_urls'] for x in k if x['knowledge_type'] in {'PHONE','SERVICE_OR_TOPIC'})
site={'design':{'palette':{},'type_style':'modern','hero_layout':'split','radius':'12px'},'business':{'name':'Fixture Co','phone':'555-0100','city':'Town'},'hero':{'headline':'Comfort starts here','body':'Heating help','primary_cta':'Request Service'},'sections':[{'id':'services','type':'services','variant':'editorial','title':'Services','body':'The redesigned experience should convert visitors.','items':[{'title':'Heating Repair','body':'Repair help','meta':''}]}],'form':{'title':'Request service','intro':'','cta':'Send','service_options':['Heating Repair']},'nav':[]}
r=prepare_v21_site(site)
assert r['sections'][0]['body']==''
assert r['sections'][0]['layout']['density']=='compact'
assert r['render_version']=='21.0'
print(f"PASS V21: {len(v['pages'])} pages, {len(k)} persistent knowledge records, provenance + presentation QA OK")
