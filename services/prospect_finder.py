import os, requests
from dotenv import load_dotenv
from .db import BASE_DIR, connect, now_iso

load_dotenv(BASE_DIR / '.env')
URL = 'https://places.googleapis.com/v1/places:searchText'

def _key():
    key = os.getenv('GOOGLE_PLACES_API_KEY')
    if not key:
        raise RuntimeError('GOOGLE_PLACES_API_KEY was not found in .env')
    return key

def _city(address):
    parts = [p.strip() for p in (address or '').split(',')]
    return parts[-3] if len(parts) >= 4 else (parts[1] if len(parts) >= 2 else '')

def discover(query, page_size=10, fallback_category='Local Service Business'):
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': _key(),
        'X-Goog-FieldMask': ','.join([
            'places.id','places.displayName','places.formattedAddress','places.rating',
            'places.userRatingCount','places.websiteUri','places.nationalPhoneNumber',
            'places.primaryTypeDisplayName'])
    }
    res = requests.post(URL, headers=headers, json={'textQuery': query, 'pageSize': max(1,min(int(page_size),20))}, timeout=25)
    if not res.ok:
        raise RuntimeError(f'Google Places returned {res.status_code}: {res.text[:500]}')
    places = res.json().get('places', [])
    con = connect(); added=[]; skipped=[]
    for p in places:
        name = p.get('displayName',{}).get('text','Unknown')
        pid = p.get('id',''); phone=p.get('nationalPhoneNumber',''); website=p.get('websiteUri','')
        duplicate = None
        if pid:
            duplicate = con.execute('SELECT id FROM businesses WHERE google_place_id=?',(pid,)).fetchone()
        if not duplicate and phone:
            duplicate = con.execute('SELECT id FROM businesses WHERE phone=? AND LOWER(name)=LOWER(?)',(phone,name)).fetchone()
        if duplicate:
            skipped.append(name); continue
        address=p.get('formattedAddress','')
        category=p.get('primaryTypeDisplayName',{}).get('text') or fallback_category
        cur=con.execute('''INSERT INTO businesses
            (name,city,category,reviews,rating,website,phone,email,online_booking,emergency_service,
             website_chat,estimate_form,status,notes,created_at,address,google_place_id,source,audit_status)
            VALUES (?,?,?,?,?,?,?,'',0,0,0,0,'Not Contacted','',?,?,?,'google_places','not_audited')''',
            (name,_city(address),category,p.get('userRatingCount') or 0,p.get('rating') or 0,website,phone,now_iso(),address,pid))
        added.append((cur.lastrowid,name))
    con.commit(); con.close()
    return {'returned':len(places),'added':added,'skipped':skipped}
