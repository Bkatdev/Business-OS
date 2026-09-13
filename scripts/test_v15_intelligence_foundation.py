import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
import sqlite3

from services.v15_site_intelligence import (
    _validate_public_host,
    ensure_intelligence_schema,
    intelligence_view,
    normalize_public_url,
    run_site_intelligence,
)

con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys = ON")
con.execute(
    """
    CREATE TABLE businesses (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        city TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        website TEXT DEFAULT '',
        online_booking INTEGER NOT NULL DEFAULT 0,
        emergency_service INTEGER NOT NULL DEFAULT 0,
        website_chat INTEGER NOT NULL DEFAULT 0,
        estimate_form INTEGER NOT NULL DEFAULT 0,
        estimate_offered INTEGER NOT NULL DEFAULT 0,
        scheduling_mentioned INTEGER NOT NULL DEFAULT 0,
        audit_status TEXT DEFAULT 'not_audited',
        audit_evidence TEXT DEFAULT ''
    )
    """
)
con.execute(
    "INSERT INTO businesses(id,name,city,category,website,audit_status,audit_evidence) VALUES (1,?,?,?,?,?,?)",
    ("Acme Tree", "East Brunswick", "Tree Care", "https://acmetree.test", "not_audited", "ORIGINAL"),
)
con.execute(
    "INSERT INTO businesses(id,name,city,category,website) VALUES (2,?,?,?,?)",
    ("Other Co", "Marlboro", "Roofing", "https://other.test"),
)
ensure_intelligence_schema(con)

pages = {
    "https://acmetree.test/robots.txt": {
        "url": "https://acmetree.test/robots.txt",
        "status": 200,
        "content_type": "text/plain",
        "text": "User-agent: *\nAllow: /",
    },
    "https://acmetree.test": {
        "url": "https://acmetree.test",
        "status": 200,
        "content_type": "text/html",
        "text": """
        <html><head><title>Acme Tree Care</title><meta name='description' content='Local tree care'>
        <script type='application/ld+json'>{"@type":"LocalBusiness"}</script></head>
        <body><nav><a href='tel:7325550100'>Call now</a><a href='/services'>Services</a>
        <a href='/contact'>Request an estimate</a></nav><h1>Professional Tree Care</h1>
        <img src='/crew.jpg' alt='Acme crew trimming a tree'>
        <section><h2>Tree Removal</h2><h2>Tree Trimming</h2></section>
        <p>See what our customers say in our Google reviews.</p></body></html>
        """,
    },
    "https://acmetree.test/services": {
        "url": "https://acmetree.test/services",
        "status": 200,
        "content_type": "text/html",
        "text": "<html><head><title>Services</title></head><body><h1>Tree Services</h1><a href='/contact'>Get a quote</a><h2>Storm Cleanup</h2><h2>Stump Grinding</h2></body></html>",
    },
    "https://acmetree.test/contact": {
        "url": "https://acmetree.test/contact",
        "status": 200,
        "content_type": "text/html",
        "text": """
        <html><head><title>Estimate</title></head><body><h1>Request an Estimate</h1>
        <form action='/thanks'><input name='name'><input name='phone'><input name='email'>
        <select name='service'><option>Tree Removal</option></select><input type='file' name='photos'>
        <select name='urgency'><option>Emergency</option></select><input name='preferred_date' type='date'>
        <button>Send estimate request</button></form><p>Financing options available.</p></body></html>
        """,
    },
}

def fetch(url):
    if url in pages:
        return pages[url]
    raise ValueError("not found")

before = con.execute(
    "SELECT audit_status,audit_evidence,estimate_form,online_booking FROM businesses WHERE id=1"
).fetchone()
view = run_site_intelligence(con, 1, fetcher=fetch, max_pages=8)
after = con.execute(
    "SELECT audit_status,audit_evidence,estimate_form,online_booking FROM businesses WHERE id=1"
).fetchone()

assert view["run"]["status"] == "COMPLETED"
assert view["run"]["pages_analyzed"] == 3
assert before["audit_status"] == after["audit_status"] == "not_audited"
assert before["audit_evidence"] == after["audit_evidence"] == "ORIGINAL"
assert before["estimate_form"] == after["estimate_form"] == 0

caps = {row["capability_key"]: row for row in view["capabilities"]}
for key in (
    "PHONE_CONTACT", "GENERAL_CONTACT_FORM", "ESTIMATE_REQUEST", "PHOTO_UPLOAD",
    "SCHEDULING_REQUEST", "AFTER_HOURS_INTAKE", "URGENT_REQUEST_ROUTING",
    "REVIEW_DISPLAY", "FINANCING_CTA",
):
    assert caps[key]["observed_state"] == "PRESENT", key
assert caps["LEAD_ACKNOWLEDGMENT"]["observed_state"] == "UNKNOWN"

assert view["assets"]
assert all(row["rights_status"] == "DISCOVERED_REFERENCE" for row in view["assets"])
assert all(row["production_allowed"] == 0 for row in view["assets"])
assert any(row["evidence_type"] == "CONTACT_PHONE" for row in view["evidence"])
assert all(row["business_id"] == 1 for row in view["pages"])
assert all(row["business_id"] == 1 for row in view["evidence"])
assert intelligence_view(con, 2)["run"] is None

run2 = run_site_intelligence(con, 1, fetcher=fetch, max_pages=2)
assert run2["run"]["id"] != view["run"]["id"]
assert con.execute("SELECT COUNT(*) FROM site_intelligence_runs WHERE business_id=1").fetchone()[0] == 2
assert normalize_public_url("example.com") == "https://example.com"

try:
    _validate_public_host("http://127.0.0.1")
    raise AssertionError("private host should fail")
except ValueError:
    pass

for table in (
    "site_intelligence_runs", "site_intelligence_pages", "site_intelligence_evidence",
    "site_capability_observations", "site_asset_observations",
):
    con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchall()

print("ALL V15 INTELLIGENCE FOUNDATION TESTS PASSED")
