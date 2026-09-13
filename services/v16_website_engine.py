"""Business OS Adaptive Website Engine v18.

Evidence-first, industry-adaptive private demo generation. The renderer receives a
structured creative brief rather than a hard-coded tree-company page.
"""
from __future__ import annotations
import json, re
from services.db import now_iso
from services.v15_site_intelligence import run_site_intelligence, intelligence_view

CAPABILITY_WEIGHTS={"PHONE_CONTACT":8,"ESTIMATE_REQUEST":14,"GENERAL_CONTACT_FORM":10,"PHOTO_UPLOAD":5,"SCHEDULING_REQUEST":7,"LIVE_BOOKING":4,"AFTER_HOURS_INTAKE":5,"URGENCY_ROUTING":6,"FAQ":5,"REVIEWS":8,"SERVICE_AREA_QUALIFICATION":5,"FINANCING_CTA":3,"LEAD_ACKNOWLEDGMENT":4,"CUSTOMER_PORTAL":3,"PAYMENT":3}

PROFILES={
 "tree":{"match":("tree","arbor","stump","landscap","prun"),"label":"Tree Care & Property Services","theme":"forest","headline":"Stronger properties start with work done right.","sub":"Clear service options, direct contact, and a faster path from property problem to next step.","hero":"https://images.unsplash.com/photo-1754321860056-ca7254d5e7ac?auto=format&fit=crop&q=86&w=2200","gallery":["https://images.unsplash.com/photo-1754322449185-31f56117ed87?auto=format&fit=crop&q=84&w=1600","https://images.unsplash.com/photo-1754322449005-bdc38c631682?auto=format&fit=crop&q=84&w=1600","https://images.unsplash.com/photo-1767642321050-23f637b1f0be?auto=format&fit=crop&q=84&w=1600"],"fallback":["Tree Removal","Tree Trimming & Pruning","Emergency Service","Stump Grinding","Land & Lot Clearing","Landscaping"]},
 "home":{"match":("roof","hvac","plumb","electric","contractor","construction","remodel","painting","masonry","cleaning","pest","garage","floor"),"label":"Home & Property Services","theme":"steel","headline":"Professional work. Clear communication. A better customer experience.","sub":"Make it simple to understand the work, see the value, and take the next step with confidence.","hero":"https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&q=86&w=2200","gallery":[],"fallback":[]},
 "health":{"match":("dent","medical","clinic","therapy","chiro","health","wellness","doctor","orthodont","physical therapy"),"label":"Patient Care","theme":"calm","headline":"Care should feel clear before the first appointment.","sub":"A calmer digital experience for understanding services, finding answers, and reaching the practice.","hero":"https://images.unsplash.com/photo-1606811971618-4486d14f3f99?auto=format&fit=crop&q=86&w=2200","gallery":[],"fallback":[]},
 "restaurant":{"match":("restaurant","cafe","pizza","bakery","bar ","grill","food","catering"),"label":"Food & Hospitality","theme":"ember","headline":"Make the first impression before they reach the table.","sub":"A richer digital experience built around the menu, atmosphere, location, and the next visit.","hero":"https://images.unsplash.com/photo-1517248135467-4c7edcad34c5?auto=format&fit=crop&q=86&w=2200","gallery":[],"fallback":[]},
 "auto":{"match":("auto","mechanic","collision","body shop","tire","car wash","detailing"),"label":"Automotive Service","theme":"graphite","headline":"A sharper experience from first click to first conversation.","sub":"Put services, trust, contact, and the next step where customers can find them immediately.","hero":"https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?auto=format&fit=crop&q=86&w=2200","gallery":[],"fallback":[]},
 "professional":{"match":("law","attorney","account","financial","insurance","real estate","consult","agency","architect"),"label":"Professional Services","theme":"ink","headline":"Expertise deserves a digital presence that feels the part.","sub":"A confident, organized experience that makes the value clear and the next conversation easy.","hero":"https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&q=86&w=2200","gallery":[],"fallback":[]},
 "general":{"match":(),"label":"Local Business","theme":"forest","headline":"A better first impression. A clearer path to action.","sub":"Turn the public website into a focused experience that helps customers understand, trust, and contact the business.","hero":None,"gallery":[],"fallback":[]},
}
SERVICE_STOP={"home","about","contact","services","service","gallery","faq","reviews","testimonials","blog","request estimate","free estimate","learn more","read more","call now","get started","our work","locations","location","menu"}

def ensure_v16_schema(conn):
    conn.executescript("""CREATE TABLE IF NOT EXISTS v16_site_demos (id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER NOT NULL,intelligence_run_id INTEGER,status TEXT NOT NULL DEFAULT 'READY',design_family TEXT NOT NULL DEFAULT 'ADAPTIVE_PREMIUM',generation_quality TEXT NOT NULL DEFAULT 'STANDARD',audit_score INTEGER NOT NULL DEFAULT 0,audit_confidence TEXT NOT NULL DEFAULT 'low',site_json TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(business_id) REFERENCES businesses(id));CREATE INDEX IF NOT EXISTS idx_v16_demo_business ON v16_site_demos(business_id,id DESC);"""); conn.commit()
def _clean(s,n=500): return re.sub(r"\s+"," ",str(s or "")).strip()[:n]
def _dict(r): return dict(r) if r is not None else {}
def _latest_view(conn,bid):
    try:return intelligence_view(conn,bid)
    except Exception:return {"run":None,"pages":[],"evidence":[],"capabilities":[],"assets":[]}
def _cap_map(v): return {str(x.get("capability_key")):x for x in (v.get("capabilities") or [])}
def reliable_audit_score(v,b):
    caps=_cap_map(v); earned=0; possible=14; observed=0
    for key,w in CAPABILITY_WEIGHTS.items():
        possible+=w; state=(caps.get(key) or {}).get("observed_state","UNKNOWN")
        if state=="PRESENT": earned+=w; observed+=1
    if _clean(b.get("website")): earned+=5
    if _clean(b.get("phone")): earned+=4
    if float(b.get("rating") or 0)>0 and int(b.get("reviews") or 0)>0: earned+=5
    pages=len(v.get("pages") or [])
    return {"score":round(100*earned/max(1,possible)),"confidence":"high" if pages>=5 else ("medium" if pages>=2 else "low"),"pages":pages,"observed_capabilities":observed,"note":"Unknown capabilities are neutral."}
def _evidence(v):
    out=[]
    for e in v.get("evidence") or []:
        out.append({"type":_clean(e.get("evidence_type"),80),"value":_clean(e.get("normalized_value"),300),"excerpt":_clean(e.get("excerpt"),500)})
    return out
def _text(v,b): return (" ".join([_clean(b.get("category")),_clean(b.get("name"))]+[x["value"]+" "+x["excerpt"] for x in _evidence(v)])).lower()
def _profile(v,b):
    t=_text(v,b)
    for key,p in PROFILES.items():
        if key!="general" and any(x in t for x in p["match"]): return key,p
    return "general",PROFILES["general"]
def _candidate_services(v):
    vals=[]
    for e in _evidence(v):
        if e["type"].upper() in ("HEADING","CTA","NAVIGATION","LINK"):
            raw=e["value"] or e["excerpt"]
            for part in re.split(r"[|•·\n]",raw):
                s=_clean(part,70).strip(" -–—:|")
                lo=s.lower()
                if 3<=len(s)<=55 and lo not in SERVICE_STOP and not any(z in lo for z in ("cookie","privacy","copyright","facebook","instagram","linkedin","click here")):
                    if any(k in lo for k in ("service","repair","install","removal","trim","prun","grind","clear","landscap","therapy","treatment","clean","roof","plumb","electric","paint","dental","consult","catering","detail","collision","inspection","maintenance","design")):
                        vals.append(s)
    out=[]
    for s in vals:
        if s.lower() not in [x.lower() for x in out]: out.append(s)
    return out[:8]
def _services(v,b,key,p):
    found=_candidate_services(v)
    if key=="tree":
        t=_text(v,b); found=[]
        checks=[("Tree Removal",("tree removal","remove tree")),("Tree Trimming & Pruning",("tree trimming","tree pruning","pruning")),("24/7 Emergency Tree Service",("24/7 emergency","emergency tree","emergency service")),("Stump Grinding",("stump grinding","stump removal")),("Land & Lot Clearing",("lot clearing","land clearing")),("Landscaping",("landscaping","landscape service"))]
        for label,terms in checks:
            if any(x in t for x in terms) or (label.startswith("24/7") and b.get("emergency_service")): found.append(label)
    if not found and p["fallback"]: found=p["fallback"][:]
    if not found: found=[_clean(b.get("category"),70) or "Primary Service"]
    return [{"name":x,"description":f"Learn about {x.lower()} and contact the team for details."} for x in found[:8]]
def _areas(v,b):
    text=_text(v,b); out=[]
    for c in ("Union","Middlesex","Essex","Morris","Hunterdon","Somerset","Monmouth","Mercer"):
        if f"{c.lower()} county" in text: out.append(f"{c} County")
    city=_clean(b.get("city"),100)
    if city and city not in out: out.insert(0,city)
    return out[:10] or ([city] if city else [])
def _photos(v):
    out=[]
    for a in v.get("assets") or []:
        u=_clean(a.get("asset_url"),1500); alt=_clean(a.get("alt_text"),180); lo=u.lower()
        if u.startswith(("http://","https://")) and not any(x in lo for x in ("logo","icon","favicon","sprite",".svg","badge")):
            out.append({"url":u,"alt":alt or "Public website reference","source":"Prospect public website","demo_only":True})
    return out[:8]
def _media(v,p):
    discovered=_photos(v); hero={"url":p["hero"],"alt":"Professional concept photography","source":"Curated concept media","demo_only":True} if p["hero"] else (discovered[0] if discovered else None)
    gallery=[]
    for u in p["gallery"]: gallery.append({"url":u,"alt":"Professional concept photography","source":"Curated concept media","demo_only":True})
    gallery += [x for x in discovered if not hero or x["url"]!=hero["url"]]
    return hero,gallery[:6]
def _site_spec(v,b,audit):
    key,p=_profile(v,b); name=_clean(b.get("name"),200) or "Local Business"; phone=_clean(b.get("phone"),80); city=_clean(b.get("city"),120)
    services=_services(v,b,key,p); hero,gallery=_media(v,p); emergency=bool(b.get("emergency_service")) or any("emergency" in x["name"].lower() for x in services)
    primary="Request a Free Estimate" if key in ("tree","home","auto") else ("Request an Appointment" if key=="health" else ("Contact Us" if key in ("professional","general") else "Plan Your Visit"))
    return {"schema_version":3,"engine_version":"18.0","truth_state":"PUBLIC_UNVERIFIED","private_preview":True,"industry":key,"theme":p["theme"],
      "design":{"family":"ADAPTIVE_PREMIUM","motion":"cinematic_reveal","interaction":"micro_interactions","media_policy":"role_aware","visual_qa":"client_runtime_checks"},
      "business":{"name":name,"phone":phone,"city":city,"address":_clean(b.get("address"),300),"website":_clean(b.get("website"),1000)},
      "hero":{"eyebrow":p["label"]+(f" · {city.upper()}" if city else ""),"headline":p["headline"],"body":p["sub"],"primary_cta":primary,"secondary_cta":f"Call {phone}" if phone else "Contact"},
      "services":services,"areas":_areas(v,b),"hero_media":hero,"gallery":gallery,"emergency":emergency,"audit":audit,
      "estimate_form":{"fields":["service","property_type","address","project_details","name","phone","email"],"tenant_business_id":b.get("id")},
      "faq":[{"q":"What is the best way to get started?","a":"Choose the service you need and send the details through the contact form so the team has useful context before following up."},{"q":"Can I contact the team directly?","a":f"Yes. Call {phone} for direct contact." if phone else "Use the contact form to reach the team."},{"q":"What information should I include?","a":"Share the service you need, location, timing, and the details that will help the team understand the request."}],
      "generation_notes":["Private sales concept.","Concept media is not represented as the prospect's completed work.","Production requires owner verification and approved media rights."]}
def generate_v16_demo(conn,business_id,*,refresh_intelligence=True,fetcher=None):
    ensure_v16_schema(conn); row=conn.execute("SELECT * FROM businesses WHERE id=?",(business_id,)).fetchone()
    if not row: raise ValueError("Business does not exist.")
    b=_dict(row); warning=""
    if refresh_intelligence and b.get("website"):
        try: run_site_intelligence(conn,business_id,fetcher=fetcher,max_pages=12)
        except Exception as exc: warning=_clean(exc,300)
    v=_latest_view(conn,business_id); audit=reliable_audit_score(v,b)
    if warning:audit["refresh_warning"]="Fresh crawl was unavailable; latest durable evidence was used."
    spec=_site_spec(v,b,audit); run=v.get("run") or {}
    cur=conn.execute("""INSERT INTO v16_site_demos (business_id,intelligence_run_id,status,design_family,generation_quality,audit_score,audit_confidence,site_json,created_at) VALUES (?,?,'READY','ADAPTIVE_PREMIUM',?,?,?,?,?)""",(business_id,run.get("id"),"FULL" if audit["pages"]>=3 else "DEGRADED",audit["score"],audit["confidence"],json.dumps(spec),now_iso()))
    conn.commit(); return get_v16_demo(conn,business_id,cur.lastrowid)
def list_v16_demos(conn,business_id,limit=20):
    ensure_v16_schema(conn)
    rows=conn.execute("SELECT * FROM v16_site_demos WHERE business_id=? ORDER BY id DESC LIMIT ?",(business_id,int(limit))).fetchall()
    out=[]
    for row in rows:
        d=dict(row); d["site"]=json.loads(d.pop("site_json")); out.append(d)
    return out

def get_v16_demo(conn,business_id,demo_id=None):
    ensure_v16_schema(conn); row=conn.execute("SELECT * FROM v16_site_demos WHERE id=? AND business_id=?",(demo_id,business_id)).fetchone() if demo_id else conn.execute("SELECT * FROM v16_site_demos WHERE business_id=? ORDER BY id DESC LIMIT 1",(business_id,)).fetchone()
    if not row:return None
    d=dict(row); d["site"]=json.loads(d.pop("site_json")); return d
