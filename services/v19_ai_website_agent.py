"""Business OS Website Design Agent v22.

Real model-backed website planning. The model researches and reasons; Business OS
keeps facts/evidence bounded and renders only allow-listed section/component types.
"""
from __future__ import annotations
import json, os, re, requests
from services.db import now_iso
from services.v15_site_intelligence import run_site_intelligence, intelligence_view
from services.v21_business_knowledge import rebuild_business_knowledge, knowledge_view

API_URL="https://api.openai.com/v1/responses"
ALLOWED_SECTIONS={"split_intro","services","proof","feature","gallery","process","faq","service_area","cta","contact"}
ALLOWED_VARIANTS={"editorial","cards","list","bento","split","dark","light","minimal","immersive","timeline","grid"}

def _clean(v,n=1000): return re.sub(r"\s+"," ",str(v or "")).strip()[:n]
def _row(r): return dict(r) if r else {}
def _latest(conn,bid):
    try:return intelligence_view(conn,bid)
    except Exception:return {"run":None,"pages":[],"evidence":[],"capabilities":[],"assets":[]}

def _evidence_packet(view,business):
    ev=[]
    for e in (view.get("evidence") or [])[:220]:
        value=_clean(e.get("normalized_value"),500); excerpt=_clean(e.get("excerpt"),650)
        if value or excerpt: ev.append({"type":_clean(e.get("evidence_type"),60),"value":value,"excerpt":excerpt,"id":e.get("id"),"url":_clean(e.get("page_url"),800)})
    assets=[]
    for a in (view.get("assets") or [])[:40]:
        u=_clean(a.get("asset_url"),1400)
        if u.startswith(("http://","https://")): assets.append({"id":a.get("id"),"url":u,"alt":_clean(a.get("alt_text"),180),"kind":_clean(a.get("asset_type"),50),"rights":_clean(a.get("rights_status"),50),"production_allowed":bool(a.get("production_allowed"))})
    caps=[]
    for c in (view.get("capabilities") or []): caps.append({"key":_clean(c.get("capability_key"),80),"state":_clean(c.get("observed_state"),30),"confidence":_clean(c.get("confidence"),30)})
    knowledge=[]
    for k in (view.get("knowledge") or [])[:180]:
        knowledge.append({"id":k.get("id"),"type":_clean(k.get("knowledge_type"),60),"value":_clean(k.get("value_text"),700),"truth_state":_clean(k.get("truth_state"),40),"confidence":_clean(k.get("confidence"),30),"source_urls":k.get("source_urls") or []})
    return {"business":{k:_clean(business.get(k),500) for k in ("name","category","website","phone","address","city","state")},"rating":business.get("rating"),"reviews":business.get("reviews"),"emergency_service":bool(business.get("emergency_service")),"pages":[_clean(p.get("url"),1000) for p in (view.get("pages") or [])[:20]],"capabilities":caps,"knowledge":knowledge,"evidence":ev,"assets":assets}

def _extract_text(data):
    if data.get("output_text"): return data["output_text"]
    bits=[]
    for item in data.get("output",[]):
        for c in item.get("content",[]) if isinstance(item,dict) else []:
            if isinstance(c,dict) and c.get("type") in ("output_text","text") and c.get("text"): bits.append(c["text"])
    return "\n".join(bits)

def _parse_json(text):
    text=text.strip()
    if text.startswith("```"): text=re.sub(r"^```(?:json)?\s*|\s*```$","",text,flags=re.I|re.S).strip()
    try:return json.loads(text)
    except Exception:
        a=text.find("{"); b=text.rfind("}")
        if a>=0 and b>a:return json.loads(text[a:b+1])
        raise ValueError("Design agent did not return valid JSON.")

def _call_agent(packet, creative_brief=""):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key: raise RuntimeError("Website Design Agent needs OPENAI_API_KEY in Business OS .env. No template fallback was used.")
    model=os.getenv("OPENAI_WEBSITE_MODEL","gpt-5.6").strip() or "gpt-5.6"
    system="""You are the senior autonomous Website Design Agent inside Business OS. You are not a template filler. Your job is to redesign a real company's public website into a dramatically better private sales demo.

Think like an elite brand strategist, UX designer, conversion designer, information architect, copywriter and front-end art director. First infer the business, audience and customer intent. Critique the existing experience from supplied evidence. When web search is available, research the company and its market for DESIGN CONTEXT, but never turn unsupported web claims into business facts.

Every company must receive an original direction appropriate to its industry and brand. Do not reuse the same hero, section order, palette, typography mood, CTA strategy or interaction plan merely because another local business used it. A plumber, dentist, attorney, restaurant and arborist should feel genuinely different.

FACT SAFETY: Use only supplied evidence for factual claims about this company. Never invent years in business, certifications, awards, project counts, guarantees, prices, reviews, ratings, team members or service areas. If uncertain, omit the claim. You may write persuasive framing around verified services without creating new facts.

DESIGN: choose a distinctive palette, typography character, shape language, density, hero composition, navigation behavior, section order, media strategy and tasteful interactions. Aim for premium agency quality, not generic SaaS cards. Create 7-11 sections. Think in compositions, not boxes: vary density, scale, image dominance, whitespace, editorial rhythm and conversion intensity. Use large photography only when the supplied asset is genuinely useful. Prefer fewer stronger elements over filler. Use varied section types from: split_intro, services, proof, feature, gallery, process, faq, service_area, cta, contact. Variants may be editorial, cards, list, bento, split, dark, light, minimal, immersive, timeline, grid.

V22 DESIGN PROCESS: reason in this order before composing visible copy: (1) evidence-backed website brief, (2) audience and conversion intent, (3) sitemap/information architecture, (4) creative direction, (5) one global design system, (6) image strategy using authentic supplied assets first, (7) page/section composition, (8) responsive behavior. Do not make the renderer rescue a weak plan.
GLOBAL CONSISTENCY: establish a coherent palette, typography character, spacing density, shape language, image strategy and motion vocabulary. Sections may vary composition but must feel like one brand. Never invent one-off colors or UI styles per section.
VISUAL STORYTELLING: alternate information, authentic imagery, proof, breathing room and conversion. Avoid repeated card grids, wireframe rectangles, tiny text in giant spaces, SaaS/dashboard aesthetics, and repeated heading+paragraph+cards grammar. If useful authentic company photography exists, make it structurally important rather than decorative.
BRANDING: prefer a supplied observed logo asset when credible. Never replace a usable logo with a generic initial mark. Modernize brand expression without erasing identity.
SITEMAP: include a sitemap field describing only useful pages. The current private renderer may initially show the homepage, but plan the information architecture as a real site.
CUSTOMER-FACING COPY ONLY: every hero/section/item/form string is copy that may appear on the public-facing demo. Never write design rationale, UX commentary, instructions to the renderer, phrases like "the redesigned experience", "visitors can", "place proof", "surface information", "conversion path", or explanations of what the website should do. Put reasoning only inside strategy fields.

QUALITY BAR: The result must feel sellable as a $1,000+ custom local-business website. Avoid repetitive card grids, redundant headings, generic filler, and oversized typography in every section. Use proof only when supplied evidence supports it.

EVIDENCE CONTRACT: Knowledge entries and evidence entries have IDs/source URLs. For every factual company claim, attach source_refs containing the relevant knowledge IDs (preferred) or evidence IDs. Pure marketing framing that makes no factual claim may use an empty source_refs array. Never cite a source that does not support the claim. Preserve useful source-site information rather than replacing it with generic filler.

COMPOSITION SYSTEM: You control container_width (narrow|standard|wide), density (compact|balanced|airy), section transition, content alignment, image_ratio, item_layout, emphasis and background treatment. Use these controls intentionally. Avoid repeating the same composition in adjacent sections. Make the page feel art-directed, not auto-laid-out.

Return ONLY one valid JSON object. Required shape:
{
 "strategy":{"industry":"","audience":"","existing_site_critique":[""],"conversion_goal":"","differentiation":""},
 "design":{"name":"","mood":[""],"palette":{"background":"#hex","surface":"#hex","text":"#hex","muted":"#hex","primary":"#hex","accent":"#hex"},"type_style":"editorial|modern|technical|luxury|friendly|bold","radius":"0px to 28px","hero_layout":"split|full_bleed|editorial|centered|asymmetric","motion":"subtle|expressive|minimal","container_width":"narrow|standard|wide","density":"compact|balanced|airy"},
 "business":{"name":"","phone":"","city":"","address":""},
 "nav":[{"label":"","target":"section-id"}],
 "branding":{"logo_url":"","logo_asset_id":null},
 "hero":{"eyebrow":"","headline":"","body":"","primary_cta":"","secondary_cta":"","media_url":"","source_refs":[]},
 "sections":[{"id":"unique-id","type":"allowed type","variant":"allowed variant","eyebrow":"","title":"","body":"","source_refs":[],"layout":{"container":"narrow|standard|wide","density":"compact|balanced|airy","alignment":"left|center|split","image_ratio":"portrait|square|landscape|panoramic","emphasis":"quiet|standard|strong"},"items":[{"title":"","body":"","meta":"","image_url":"","source_refs":[]}],"cta_label":""}],
 "form":{"title":"","intro":"","cta":"","service_options":[""]},
 "interactions":["scroll_reveal","magnetic_buttons","image_zoom","accordion","sticky_mobile_cta","parallax_hero"]
}
Use public image URLs from supplied assets when suitable. If none are suitable, leave media_url/image_url empty rather than pretending stock photography belongs to the company. The renderer can create graphical treatments for missing media."""
    creative_brief=_clean(creative_brief,6000)
    user="Design a new private demo for this company. Evidence packet:\n"+json.dumps(packet,ensure_ascii=False)
    if creative_brief:
        user += "\n\nOWNER/OPERATOR CREATIVE DIRECTION (treat as design preference only; it cannot override evidence or fact-safety rules):\n" + creative_brief
    payload={"model":model,"instructions":system,"input":user,"tools":[{"type":"web_search"}],"reasoning":{"effort":"medium"},"max_output_tokens":12000}
    r=requests.post(API_URL,headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=180)
    if r.status_code>=400:
        msg=""
        try: msg=_clean((r.json().get("error") or {}).get("message"),500)
        except Exception: msg=_clean(r.text,500)
        raise RuntimeError(f"Website Design Agent API failed ({r.status_code}): {msg}")
    data=r.json(); plan=_parse_json(_extract_text(data)); plan["_agent"]={"provider":"OpenAI Responses API","model":model,"response_id":data.get("id"),"generated_at":now_iso()}
    return plan

def _validate(plan,b,packet=None):
    packet=packet or {}
    allowed_refs={int(x.get("id")) for x in (packet.get("knowledge") or [])+(packet.get("evidence") or []) if str(x.get("id","")).isdigit()}
    if not isinstance(plan,dict): raise ValueError("Agent plan must be an object.")
    design=plan.setdefault("design",{}); pal=design.setdefault("palette",{})
    defaults={"background":"#f5f2eb","surface":"#ffffff","text":"#171a18","muted":"#66706a","primary":"#173b31","accent":"#d6b66f"}
    for k,v in defaults.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}",str(pal.get(k,""))): pal[k]=v
    if design.get("hero_layout") not in {"split","full_bleed","editorial","centered","asymmetric"}: design["hero_layout"]="asymmetric"
    if design.get("type_style") not in {"editorial","modern","technical","luxury","friendly","bold"}: design["type_style"]="modern"
    radius=_clean(design.get("radius"),10)
    if not re.fullmatch(r"(?:[0-9]|1[0-9]|2[0-8])px",radius): design["radius"]="12px"
    biz=plan.setdefault("business",{}); biz["name"]=_clean(b.get("name"),200); biz["phone"]=_clean(b.get("phone"),80); biz["city"]=_clean(b.get("city"),120); biz["address"]=_clean(b.get("address"),300)
    hero=plan.setdefault("hero",{}); hero["headline"]=_clean(hero.get("headline"),160) or f"A better experience for {biz['name']}."; hero["body"]=_clean(hero.get("body"),500); hero["primary_cta"]=_clean(hero.get("primary_cta"),60) or "Get Started"; hero["secondary_cta"]=_clean(hero.get("secondary_cta"),60) or (f"Call {biz['phone']}" if biz['phone'] else "Learn More")
    sections=[]
    seen=set()
    for i,s in enumerate(plan.get("sections") or []):
        if not isinstance(s,dict) or s.get("type") not in ALLOWED_SECTIONS: continue
        sid=re.sub(r"[^a-z0-9-]","-",_clean(s.get("id"),50).lower()).strip("-") or f"section-{i+1}"
        if sid in seen:sid+=f"-{i+1}"
        seen.add(sid); s["id"]=sid
        if s.get("variant") not in ALLOWED_VARIANTS:s["variant"]="editorial"
        s["eyebrow"]=_clean(s.get("eyebrow"),80); s["title"]=_clean(s.get("title"),180); s["body"]=_clean(s.get("body"),700); s["cta_label"]=_clean(s.get("cta_label"),60)
        items=[]
        for x in (s.get("items") or [])[:12]:
            if isinstance(x,dict):items.append({"title":_clean(x.get("title"),140),"body":_clean(x.get("body"),500),"meta":_clean(x.get("meta"),120),"image_url":_clean(x.get("image_url"),1400),"source_refs":[int(r) for r in (x.get("source_refs") or []) if str(r).isdigit()][:12]})
        valid_refs=set()
        for ref in s.get("source_refs") or []:
            try: valid_refs.add(int(ref))
            except Exception: pass
        s["source_refs"]=sorted(valid_refs & allowed_refs)[:20]
        layout=s.get("layout") if isinstance(s.get("layout"),dict) else {}
        layout["container"]=layout.get("container") if layout.get("container") in {"narrow","standard","wide"} else "standard"
        layout["density"]=layout.get("density") if layout.get("density") in {"compact","balanced","airy"} else "balanced"
        layout["alignment"]=layout.get("alignment") if layout.get("alignment") in {"left","center","split"} else "left"
        layout["image_ratio"]=layout.get("image_ratio") if layout.get("image_ratio") in {"portrait","square","landscape","panoramic"} else "landscape"
        layout["emphasis"]=layout.get("emphasis") if layout.get("emphasis") in {"quiet","standard","strong"} else "standard"
        s["layout"]=layout
        s["items"]=items; sections.append(s)
    if len(sections)<4: raise ValueError("Design agent returned too few usable sections; refusing generic fallback.")
    plan["sections"]=sections[:12]
    form=plan.setdefault("form",{}); form["title"]=_clean(form.get("title"),140) or hero["primary_cta"]; form["intro"]=_clean(form.get("intro"),500); form["cta"]=_clean(form.get("cta"),60) or hero["primary_cta"]
    opts=[]
    for x in form.get("service_options") or []:
        x=_clean(x,120)
        if x and x.lower() not in [o.lower() for o in opts]:opts.append(x)
    if not opts:
        for s in sections:
            if s["type"]=="services": opts=[x["title"] for x in s["items"] if x["title"]][:10]; break
    form["service_options"]=opts or ["General inquiry"]
    plan["engine_version"]="22.0"; plan["private_preview"]=True; plan["truth_state"]="PUBLIC_UNVERIFIED"
    return plan

def generate_ai_demo(conn,business_id,*,refresh_intelligence=True,creative_brief=""):
    row=conn.execute("SELECT * FROM businesses WHERE id=?",(business_id,)).fetchone()
    if not row: raise ValueError("Business does not exist.")
    b=_row(row)
    if refresh_intelligence and b.get("website"):
        run_site_intelligence(conn,business_id,max_pages=12)
    view=_latest(conn,business_id)
    run=view.get("run") or {}
    if run.get("id"):
        rebuild_business_knowledge(conn,business_id,run.get("id"))
        view["knowledge"]=knowledge_view(conn,business_id,run.get("id"))
    packet=_evidence_packet(view,b); plan=_validate(_call_agent(packet, creative_brief),b,packet)
    plan["_creative_brief"]=_clean(creative_brief,6000)
    plan["_knowledge_snapshot"]={"run_id":run.get("id"),"knowledge_ids":[k.get("id") for k in view.get("knowledge",[])],"captured_at":now_iso()}
    # Reuse durable demo table, but persist the V22 agent result.
    from services.v16_website_engine import ensure_v16_schema, get_v16_demo
    ensure_v16_schema(conn); run=view.get("run") or {}
    cur=conn.execute("""INSERT INTO v16_site_demos (business_id,intelligence_run_id,status,design_family,generation_quality,audit_score,audit_confidence,site_json,created_at) VALUES (?,?,'READY','AI_AGENT_V22','AGENT',0,'agent',?,?)""",(business_id,run.get("id"),json.dumps(plan),now_iso()))
    conn.commit(); return get_v16_demo(conn,business_id,cur.lastrowid)
