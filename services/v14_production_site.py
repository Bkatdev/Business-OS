"""Validated production design layer: verified truth -> safe blueprint -> render model."""
import json
from services.db import now_iso
from services.v13_creative_director import generate_concept_blueprint
from services.v13_blueprints import validate_blueprint, clean_brief
from services.website_renderer import build_preview_render_model

def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS production_site_designs(id INTEGER PRIMARY KEY AUTOINCREMENT,business_id INTEGER NOT NULL,website_version_id INTEGER NOT NULL,creative_brief TEXT NOT NULL DEFAULT '',blueprint_json TEXT NOT NULL,generation_mode TEXT NOT NULL,critic_score INTEGER NOT NULL,critic_json TEXT NOT NULL DEFAULT '[]',selected INTEGER NOT NULL DEFAULT 0 CHECK(selected IN(0,1)),created_at TEXT NOT NULL,FOREIGN KEY(business_id) REFERENCES businesses(id) ON DELETE CASCADE,FOREIGN KEY(website_version_id) REFERENCES website_versions(id) ON DELETE CASCADE)''')



def _lines(value):
    text=str(value or '').replace('\r','\n')
    out=[]
    for chunk in text.replace(';','\n').split('\n'):
        item=' '.join(chunk.strip().split())
        if item and item.lower() not in {'service area:', 'hours:'}:
            out.append(item)
    return out


def _strip_label(value, labels):
    text=str(value or '').strip()
    low=text.lower()
    for label in labels:
        if low.startswith(label.lower()):
            return text[len(label):].strip(' :')
    return text


def _service_areas(value):
    """Turn owner-entered service-area text into human-readable places.

    Supports newlines/semicolons, simple comma-separated city lists, and repeated
    City, ST pairs without leaking a raw configuration string into the website.
    """
    import re
    raw=str(value or '').replace('\r','\n').strip()
    if not raw:
        return []
    raw=re.sub(r'^\s*(service area|serving)\s*:\s*', '', raw, flags=re.I)
    chunks=[]
    for block in re.split(r'[;\n]+', raw):
        block=' '.join(block.strip().split())
        if not block:
            continue
        # Preserve a single "City, ST" item, but parse repeated City, ST pairs.
        pairs=re.findall(r'([^,]+?),\s*([A-Z]{2})(?=\s*,|$)', block)
        if pairs and len(pairs) * 2 >= len([x for x in block.split(',') if x.strip()]):
            chunks.extend(f"{city.strip()}, {state}" for city,state in pairs)
        elif ',' in block:
            chunks.extend(x.strip() for x in block.split(',') if x.strip())
        else:
            chunks.append(block)
    cleaned=[_strip_label(x, ('Service Area', 'Serving')) for x in chunks]
    return list(dict.fromkeys(x for x in cleaned if x))


def _hours(value):
    """Present compact owner-entered hours as one readable schedule line per entry."""
    import re
    raw=str(value or '').replace('\r','\n').strip()
    if not raw:
        return []
    raw=re.sub(r'^\s*hours\s*:\s*', '', raw, flags=re.I)
    parts=[]
    for item in re.split(r'[,;\n]+', raw):
        item=' '.join(item.strip().split())
        if item:
            parts.append(_strip_label(item, ('Hours',)))
    return list(dict.fromkeys(parts))

def _public_email(value):
    email=str(value or '').strip()
    return '' if email.lower().endswith('.example') else email


def _presentation_services(services):
    """Add presentation-only copy without inventing business claims.

    The service name itself must already be owner-verified. Fallback descriptions
    only explain what information a customer can share; they never add capability,
    pricing, certification, timing, warranty, or outcome claims.
    """
    safe_prompts = {
        'tree removal': 'Share the tree location, what concerns you, and any access details that may help the team review the request.',
        'tree trimming': 'Tell us which trees or branches you would like reviewed and what you want to accomplish on the property.',
        'stump grinding': 'Share the stump location, approximate size if known, and any access details for the property.',
        'storm cleanup': 'Describe the storm-related tree debris or damage you would like the team to review.',
    }
    result=[]
    for item in services:
        row=dict(item)
        description=str(row.get('description') or '').strip()
        if not description:
            name=str(row.get('name') or 'service').strip()
            row['display_description']=safe_prompts.get(
                name.lower(),
                f"Tell us what you need for {name.lower()} and include any property details that may help the team review your request.",
            )
        else:
            row['display_description']=description
        result.append(row)
    return result

def _facts(site):
    b,p=site['business'],site['profile']
    return {'id':b['id'],'name':b['name'],'category':p.get('industry') or b.get('category') or 'Local Service','city':b.get('city') or '', 'phone':b.get('phone') or '', 'rating':None,'reviews':0,'audit_status':'OWNER_VERIFIED','estimate_form':True,'online_booking':False,'website_chat':False,'emergency_service':False,'scheduling_mentioned':False}

def _critic(site,bp):
    score=100; notes=[]
    for cond,penalty,note in [(not site.get('services'),35,'No verified services.'),(not site['presentation'].get('about_copy'),12,'About copy is missing.'),(not site['profile'].get('service_area'),10,'Service area is missing.'),(len(site['hero'].get('supporting_text') or '')<35,6,'Hero copy is thin.')]:
        if cond: score-=penalty; notes.append(note)
    if bp['layout_family'] in ('cinematic','editorial'): notes.append('Decorative media is used until a licensed or owner-provided asset is attached.')
    return max(score,0),notes

def generate_design(conn,business_id,brief=''):
    ensure_schema(conn); site=build_preview_render_model(conn,business_id)
    if not site.get('customer_ready'): raise ValueError('Select a customer-ready reviewed preview first.')
    result=generate_concept_blueprint(_facts(site),clean_brief(brief),1); validate_blueprint(result.blueprint)
    score,notes=_critic(site,result.blueprint); conn.execute('UPDATE production_site_designs SET selected=0 WHERE business_id=?',(business_id,))
    conn.execute('INSERT INTO production_site_designs(business_id,website_version_id,creative_brief,blueprint_json,generation_mode,critic_score,critic_json,selected,created_at) VALUES(?,?,?,?,?,?,?,1,?)',(business_id,site['version']['id'],clean_brief(brief),json.dumps(result.blueprint),result.generation_mode,score,json.dumps(notes),now_iso())); conn.commit(); return selected_design(conn,business_id)

def selected_design(conn,business_id):
    ensure_schema(conn); r=conn.execute('SELECT * FROM production_site_designs WHERE business_id=? AND selected=1 ORDER BY id DESC LIMIT 1',(business_id,)).fetchone()
    if not r:return None
    d=dict(r); d['blueprint']=json.loads(d['blueprint_json']); d['critic']=json.loads(d['critic_json']); return d

def production_model(conn,business_id):
    site=build_preview_render_model(conn,business_id); d=selected_design(conn,business_id)
    if not d: raise ValueError('Generate a production design first.')
    if int(d['website_version_id'])!=int(site['version']['id']): raise ValueError('Design is stale; regenerate for the selected preview.')
    site=dict(site)
    site['design']=d
    site['blueprint']=d['blueprint']
    site['service_areas']=_service_areas(site['profile'].get('service_area'))
    site['hours_lines']=_hours(site['profile'].get('business_hours'))
    site['services']=_presentation_services(site.get('services') or [])
    site['public_email']=_public_email(site['business'].get('email'))
    return site
