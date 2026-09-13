"""Business OS v21 persistent evidence-backed Business Knowledge layer."""
from __future__ import annotations
import json, re
from urllib.parse import urlparse
from services.db import now_iso

TRUTH_STATES={"OWNER_VERIFIED","PUBLIC_VERIFIED","PUBLIC_UNVERIFIED","LIKELY","NOT_DETECTED","UNKNOWN"}

SERVICE_HINTS=("service","repair","install","installation","replacement","maintenance","plumbing","heating","cooling","air conditioning","hvac","drain","water heater","tree","landscap","roof","electric","dental","cleaning")
SOCIAL_HOSTS=("facebook.com","instagram.com","linkedin.com","youtube.com","tiktok.com","x.com","twitter.com")

def ensure_v21_schema(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS site_business_knowledge (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      business_id INTEGER NOT NULL,
      run_id INTEGER,
      knowledge_type TEXT NOT NULL,
      knowledge_key TEXT NOT NULL,
      value_text TEXT NOT NULL DEFAULT '',
      truth_state TEXT NOT NULL DEFAULT 'PUBLIC_VERIFIED',
      confidence TEXT NOT NULL DEFAULT 'medium',
      source_evidence_ids TEXT NOT NULL DEFAULT '[]',
      source_urls TEXT NOT NULL DEFAULT '[]',
      observed_at TEXT NOT NULL,
      UNIQUE(business_id,run_id,knowledge_type,knowledge_key,value_text)
    );
    CREATE INDEX IF NOT EXISTS idx_v21_knowledge_business ON site_business_knowledge(business_id,run_id,knowledge_type);
    ''')
    conn.commit()

def _clean(v,n=700): return re.sub(r"\s+"," ",str(v or "")).strip()[:n]
def _key(v): return re.sub(r"[^a-z0-9]+","-",_clean(v,180).lower()).strip("-")

def rebuild_business_knowledge(conn,business_id,run_id=None):
    ensure_v21_schema(conn)
    if run_id is None:
        r=conn.execute("SELECT id FROM site_intelligence_runs WHERE business_id=? AND status='COMPLETED' ORDER BY id DESC LIMIT 1",(business_id,)).fetchone()
        if not r:return []
        run_id=r[0]
    conn.execute("DELETE FROM site_business_knowledge WHERE business_id=? AND run_id=?",(business_id,run_id))
    rows=conn.execute("SELECT id,page_url,evidence_type,normalized_value,excerpt,confidence FROM site_intelligence_evidence WHERE business_id=? AND run_id=? ORDER BY id",(business_id,run_id)).fetchall()
    pages=conn.execute("SELECT id,url,title,meta_description,primary_heading FROM site_intelligence_pages WHERE business_id=? AND run_id=? ORDER BY id",(business_id,run_id)).fetchall()
    assets=conn.execute("SELECT id,page_url,asset_url,asset_type,alt_text,rights_status,production_allowed FROM site_asset_observations WHERE business_id=? AND run_id=? ORDER BY id",(business_id,run_id)).fetchall()
    facts={}
    def add(typ,val,url="",eid=None,confidence="medium",state="PUBLIC_VERIFIED",key=None):
        val=_clean(val)
        if not val:return
        k=(typ,key or _key(val),val.lower())
        f=facts.setdefault(k,{"type":typ,"key":key or _key(val),"value":val,"state":state,"confidence":confidence,"eids":[],"urls":[]})
        if eid and eid not in f["eids"]:f["eids"].append(eid)
        if url and url not in f["urls"]:f["urls"].append(url)
        if confidence=="high":f["confidence"]="high"
    for e in rows:
        eid,url,typ,val,excerpt,conf=e
        if typ=="CONTACT_PHONE": add("PHONE",val,url,eid,conf)
        elif typ=="CONTACT_EMAIL": add("EMAIL",val,url,eid,conf)
        elif typ=="SOCIAL_LINK": add("SOCIAL_LINK",val,url,eid,conf)
        elif typ=="FAQ_QA": add("FAQ",excerpt or val,url,eid,conf)
        elif typ in {"HOURS","ADDRESS","SERVICE_AREA","OFFER","WARRANTY","CERTIFICATION","MEMBERSHIP","FINANCING","REVIEW","TEAM"}: add(typ,val or excerpt,url,eid,conf)
        elif typ=="HEADING":
            low=(val or "").lower()
            if any(h in low for h in SERVICE_HINTS) and 2<=len(val.split())<=12:add("SERVICE_OR_TOPIC",val,url,eid,conf)
    for p in pages:
        _,url,title,meta,h1=p
        path=urlparse(url).path.strip("/")
        label=h1 or title
        if path and label and any(h in (path+" "+label).lower() for h in SERVICE_HINTS):
            add("SERVICE_OR_TOPIC",label,url,None,"medium")
        if meta:add("PAGE_DESCRIPTION",meta,url,None,"medium",key=_key(path or "home"))
    for a in assets:
        aid,page_url,asset_url,asset_type,alt,rights,allowed=a
        typ="LOGO_ASSET" if asset_type=="LOGO" else "IMAGE_ASSET"
        add(typ,asset_url,page_url,None,"high" if asset_type=="LOGO" else "medium",key=str(aid))
    now=now_iso()
    for f in facts.values():
        conn.execute('''INSERT OR IGNORE INTO site_business_knowledge
          (business_id,run_id,knowledge_type,knowledge_key,value_text,truth_state,confidence,source_evidence_ids,source_urls,observed_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)''',(business_id,run_id,f["type"],f["key"],f["value"],f["state"],f["confidence"],json.dumps(f["eids"]),json.dumps(f["urls"]),now))
    conn.commit()
    return knowledge_view(conn,business_id,run_id)

def knowledge_view(conn,business_id,run_id=None):
    ensure_v21_schema(conn)
    if run_id is None:
        r=conn.execute("SELECT id FROM site_intelligence_runs WHERE business_id=? AND status='COMPLETED' ORDER BY id DESC LIMIT 1",(business_id,)).fetchone()
        if not r:return []
        run_id=r[0]
    out=[]
    for r in conn.execute("SELECT * FROM site_business_knowledge WHERE business_id=? AND run_id=? ORDER BY knowledge_type,id",(business_id,run_id)).fetchall():
        d=dict(r); d["source_evidence_ids"]=json.loads(d.get("source_evidence_ids") or "[]"); d["source_urls"]=json.loads(d.get("source_urls") or "[]"); out.append(d)
    return out
