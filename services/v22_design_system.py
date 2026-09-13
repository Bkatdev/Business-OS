"""V22 deterministic design architecture and QA.
Turns persisted AI plans + observed business assets into a coherent render model.
No model calls. No owner-truth mutation. Public assets remain demo references only.
"""
from __future__ import annotations
import colorsys, json, re
from copy import deepcopy
from services.db import now_iso
from services.v21_presentation import prepare_v21_site

HEX=re.compile(r'^#[0-9a-fA-F]{6}$')
COMPOSITIONS={
 'split_intro':['audience-pathways','editorial-split'], 'services':['service-explorer','image-led-services'],
 'proof':['proof-band','testimonial-feature'], 'gallery':['project-showcase','image-mosaic'],
 'process':['process-timeline','horizontal-process'], 'faq':['faq-editorial'],
 'service_area':['local-area','editorial-list'], 'cta':['emergency-cta','conversion-panel'],
 'feature':['feature-story','bento'], 'contact':['contact-estimate']}

def ensure_v22_schema(conn):
 conn.executescript('''
 CREATE TABLE IF NOT EXISTS site_design_artifacts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER NOT NULL,demo_id INTEGER NOT NULL,
  artifact_type TEXT NOT NULL,artifact_json TEXT NOT NULL,created_at TEXT NOT NULL,
  UNIQUE(business_id,demo_id,artifact_type));
 CREATE TABLE IF NOT EXISTS site_design_qa(
  id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER NOT NULL,demo_id INTEGER NOT NULL,
  status TEXT NOT NULL,report_json TEXT NOT NULL,created_at TEXT NOT NULL,
  UNIQUE(business_id,demo_id));
 '''); conn.commit()

def _hex(v, fallback): return v if isinstance(v,str) and HEX.fullmatch(v) else fallback

def _rgb(h): return tuple(int(h[i:i+2],16)/255 for i in (1,3,5))
def _lum(h):
 def f(x): return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
 r,g,b=_rgb(h); return .2126*f(r)+.7152*f(g)+.0722*f(b)
def contrast(a,b):
 x,y=sorted((_lum(a),_lum(b)),reverse=True); return (x+.05)/(y+.05)
def _mix(a,b,t):
 aa=[int(a[i:i+2],16) for i in (1,3,5)]; bb=[int(b[i:i+2],16) for i in (1,3,5)]
 return '#'+''.join(f'{round(x+(y-x)*t):02x}' for x,y in zip(aa,bb))
def _text_on(bg): return '#ffffff' if contrast(bg,'#ffffff')>=4.5 else '#111713'

def _assets(conn,bid,run_id=None):
 if not bid:return []
 if run_id is None:
  r=conn.execute("SELECT id FROM site_intelligence_runs WHERE business_id=? AND status='COMPLETED' ORDER BY id DESC LIMIT 1",(bid,)).fetchone(); run_id=r['id'] if r else None
 if not run_id:return []
 rows=conn.execute("SELECT id,page_url,asset_url,asset_type,alt_text,rights_status,production_allowed FROM site_asset_observations WHERE business_id=? AND run_id=? ORDER BY id",(bid,run_id)).fetchall()
 out=[]
 for rr in rows:
  a=dict(rr); u=(a.get('asset_url') or '').lower(); alt=(a.get('alt_text') or '').lower(); hay=u+' '+alt
  if any(x in hay for x in ('logo','brandmark','wordmark')): role='logo'
  elif any(x in hay for x in ('icon','favicon','sprite','.svg')): role='icon'
  elif any(x in hay for x in ('team','crew','staff','owner','technician')): role='people'
  elif any(x in hay for x in ('project','gallery','work','before','after','tree','truck','crane','service','install','repair')): role='work'
  else: role='general'
  a['role']=role; out.append(a)
 return out

def _pick_assets(assets):
 usable=[a for a in assets if (a.get('asset_url') or '').startswith(('http://','https://'))]
 logo=next((a for a in usable if a['role']=='logo'),None)
 photos=[a for a in usable if a['role'] not in {'logo','icon'}]
 work=[a for a in photos if a['role'] in {'work','people'}]
 ordered=[]
 for a in work+photos:
  if a['asset_url'] not in [x['asset_url'] for x in ordered]: ordered.append(a)
 return logo,ordered[:18]

def _tokens(site):
 d=site.get('design') or {}; p=d.get('palette') or {}
 bg=_hex(p.get('background'),'#f5f2eb'); primary=_hex(p.get('primary'),'#173b31'); accent=_hex(p.get('accent'),'#d6b66f')
 surface=_hex(p.get('surface'),'#ffffff'); text=_hex(p.get('text'),'#171a18'); muted=_hex(p.get('muted'),'#66706a')
 if contrast(bg,text)<7:text=_text_on(bg)
 if contrast(surface,text)<7:text='#111713'
 return {'color':{'background':bg,'surface':surface,'surface_alt':_mix(bg,primary,.06),'primary':primary,'primary_text':_text_on(primary),'accent':accent,'accent_text':_text_on(accent),'text':text,'muted':muted,'border':_mix(text,bg,.84)},
 'type':{'display':'clamp(3.4rem,7vw,7.5rem)','h1':'clamp(3.1rem,6vw,6.8rem)','h2':'clamp(2.35rem,4vw,4.5rem)','h3':'clamp(1.25rem,1.8vw,1.65rem)','body_large':'clamp(1.1rem,1.3vw,1.3rem)','body':'clamp(1rem,1.05vw,1.125rem)','small':'.86rem'},
 'space':{'section':'clamp(5.5rem,9vw,10rem)','gutter':'clamp(1.25rem,4vw,4.5rem)','gap':'clamp(1.25rem,2.4vw,2.75rem)'},
 'layout':{'content':'1240px','wide':'1540px','reading':'760px'},'shape':{'radius':d.get('radius') or '14px'}}

def _brief(site,assets):
 biz=site.get('business') or {}; sections=site.get('sections') or []
 return {'company':biz.get('name'),'city':biz.get('city'),'audiences':[x.get('title') for s in sections if s.get('type')=='split_intro' for x in s.get('items',[])][:6],
 'services':[x.get('title') for s in sections if s.get('type')=='services' for x in s.get('items',[])][:12],
 'conversion_goal':(site.get('hero') or {}).get('primary_cta'),'image_strategy':'photography-dominant' if len(assets)>=3 else ('restrained-photography' if assets else 'graphic-editorial'),
 'authentic_asset_count':len(assets),'source':'persisted AI plan + observed public website assets','truth_state':'PUBLIC_UNVERIFIED'}

def prepare_v22_site(conn,business_id,demo_id,site):
 s=prepare_v21_site(deepcopy(site or {})); run_id=(s.get('_knowledge_snapshot') or {}).get('run_id')
 assets=_assets(conn,business_id,run_id); logo,photos=_pick_assets(assets); tokens=_tokens(s); brief=_brief(s,photos)
 s['design_system']=tokens; s['website_brief']=brief; s['render_version']='22.0'
 branding=s.setdefault('branding',{})
 if logo and not branding.get('logo_url'): branding['logo_url']=logo['asset_url']; branding['logo_source_asset_id']=logo['id']
 hero=s.setdefault('hero',{})
 if photos and not hero.get('media_url'): hero['media_url']=photos[0]['asset_url']; hero['media_source_asset_id']=photos[0]['id']
 # Allocate authentic observed media without inventing what it depicts.
 pi=1 if hero.get('media_url') else 0
 used=[]
 for idx,sec in enumerate(s.get('sections') or []):
  sec['composition']=(COMPOSITIONS.get(sec.get('type')) or ['editorial'])[idx % len(COMPOSITIONS.get(sec.get('type')) or ['editorial'])]
  if sec.get('type') in {'gallery','proof','feature','split_intro','services'}:
   for item in sec.get('items') or []:
    if not item.get('image_url') and photos:
     a=photos[pi % len(photos)]; pi+=1; item['image_url']=a['asset_url']; item['image_source_asset_id']=a['id']; used.append(a['id'])
 s['_asset_strategy']={'logo_asset_id':logo['id'] if logo else None,'photo_asset_ids':[a['id'] for a in photos],'used_asset_ids':used,'rights_note':'Observed public-site media is demo-reference only until production approval.'}
 qa=qa_report(s)
 ensure_v22_schema(conn)
 for typ,obj in [('WEBSITE_BRIEF',brief),('DESIGN_SYSTEM',tokens),('ASSET_STRATEGY',s['_asset_strategy'])]:
  conn.execute("INSERT OR REPLACE INTO site_design_artifacts(business_id,demo_id,artifact_type,artifact_json,created_at) VALUES(?,?,?,?,?)",(business_id,demo_id,typ,json.dumps(obj),now_iso()))
 conn.execute("INSERT OR REPLACE INTO site_design_qa(business_id,demo_id,status,report_json,created_at) VALUES(?,?,?,?,?)",(business_id,demo_id,qa['status'],json.dumps(qa),now_iso())); conn.commit()
 return s

def qa_report(s):
 t=s.get('design_system') or _tokens(s); c=t['color']; issues=[]
 for bg,fg,label in [(c['background'],c['text'],'page text'),(c['surface'],c['text'],'surface text'),(c['primary'],c['primary_text'],'primary button')]:
  if contrast(bg,fg)<4.5:issues.append(f'contrast:{label}')
 secs=s.get('sections') or []; comps=[x.get('composition') for x in secs]
 if any(comps[i]==comps[i-1] for i in range(1,len(comps))):issues.append('adjacent-composition-repeat')
 if not (s.get('branding') or {}).get('logo_url'):issues.append('logo-not-observed')
 if not (s.get('hero') or {}).get('media_url'):issues.append('hero-media-not-observed')
 return {'status':'PASS' if not [x for x in issues if x.startswith('contrast:')] else 'FAIL','issues':issues,'checks':{'contrast':True,'token_source':True,'composition_count':len(set(comps)),'section_count':len(secs)},'generated_at':now_iso()}
