from __future__ import annotations
import sqlite3, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from services.v22_design_system import ensure_v22_schema,prepare_v22_site,contrast

def main():
 c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
 c.executescript('''CREATE TABLE site_intelligence_runs(id INTEGER PRIMARY KEY,business_id INTEGER,status TEXT);CREATE TABLE site_asset_observations(id INTEGER PRIMARY KEY,run_id INTEGER,business_id INTEGER,page_url TEXT,asset_url TEXT,asset_type TEXT,alt_text TEXT,rights_status TEXT,production_allowed INTEGER);''')
 c.execute("INSERT INTO site_intelligence_runs VALUES(7,1,'COMPLETED')")
 for row in [(1,7,1,'https://x.test','https://x.test/logo.png','IMAGE','Company logo','DISCOVERED_REFERENCE',0),(2,7,1,'https://x.test','https://x.test/tree-work.jpg','IMAGE','Tree service project','DISCOVERED_REFERENCE',0),(3,7,1,'https://x.test','https://x.test/crew.jpg','IMAGE','Crew at work','DISCOVERED_REFERENCE',0)]:c.execute('INSERT INTO site_asset_observations VALUES(?,?,?,?,?,?,?,?,?)',row)
 site={'business':{'name':'Fixture Co','phone':'555-0100','city':'Testville'},'design':{'palette':{'background':'#f4f0e7','surface':'#ffffff','text':'#152019','muted':'#66706a','primary':'#173b31','accent':'#d6a04c'},'radius':'12px'},'branding':{},'hero':{'eyebrow':'LOCAL SERVICE','headline':'Care for the property around you.','body':'Evidence-bound fixture copy.','primary_cta':'Request an Estimate','secondary_cta':'Call'},'nav':[], 'sections':[{'id':'services','type':'services','variant':'editorial','eyebrow':'SERVICES','title':'How we can help','body':'','items':[{'title':'Service One','body':'Fixture body','image_url':''}]},{'id':'work','type':'gallery','variant':'editorial','eyebrow':'WORK','title':'See the work','body':'','items':[{'title':'Project','body':'Fixture body','image_url':''}]},{'id':'faq','type':'faq','variant':'editorial','eyebrow':'FAQ','title':'Questions','body':'','items':[{'title':'Question?','body':'Answer.'}]}], 'form':{'title':'Request help','intro':'Tell us what you need.','cta':'Send','service_options':['Service One']},'_knowledge_snapshot':{'run_id':7}}
 out=prepare_v22_site(c,1,99,site)
 assert out['render_version']=='22.0'; assert out['branding']['logo_url'].endswith('logo.png'); assert out['hero']['media_url'].endswith('tree-work.jpg'); assert out['sections'][0]['items'][0]['image_url']; assert out['design_system']['color']['primary_text']; assert contrast(out['design_system']['color']['primary'],out['design_system']['color']['primary_text'])>=4.5
 assert c.execute("select count(*) from site_design_artifacts").fetchone()[0]==3; assert c.execute("select count(*) from site_design_qa").fetchone()[0]==1
 print('PASS V22 architecture: brief + tokens + authentic asset strategy + compositions + QA persisted')
if __name__=='__main__':main()
