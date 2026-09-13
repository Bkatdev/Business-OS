from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import services.db as db


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


with tempfile.TemporaryDirectory(prefix="business-os-v15-block2-") as temp_dir:
    db.DB_PATH = Path(temp_dir) / "business_os.db"
    from app import app
    from services.v15_site_intelligence import run_site_intelligence
    from services.v15_upgrade_engine import upgrade_workspace_view

    db.init_db()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO businesses(name,city,category,website,phone,status,created_at)
        VALUES ('Acme Tree Care','East Brunswick','Tree Care','https://acme.test',
                '732-555-0100','Researching','2026-09-13T01:00:00')
        """
    )
    bid = conn.execute("SELECT id FROM businesses WHERE name='Acme Tree Care'").fetchone()[0]
    conn.execute(
        """
        INSERT INTO businesses(name,city,category,website,status,created_at)
        VALUES ('Other Salon','Marlboro','Hair Salon','https://other.test',
                'Researching','2026-09-13T01:00:00')
        """
    )
    other_id = conn.execute("SELECT id FROM businesses WHERE name='Other Salon'").fetchone()[0]
    conn.commit()

    pages = {
        "https://acme.test/robots.txt": {"url": "https://acme.test/robots.txt", "status": 200, "content_type": "text/plain", "text": "User-agent: *\nAllow: /"},
        "https://acme.test": {"url": "https://acme.test", "status": 200, "content_type": "text/html", "text": """
            <html><head><title>Acme Tree Care</title></head><body>
            <a href='tel:7325550100'>Call Acme</a><a href='/contact'>Contact us</a>
            <h1>Acme Tree Care</h1><h2>Tree Removal</h2><h2>Tree Trimming</h2>
            <p>Read our customer reviews.</p></body></html>
        """},
        "https://acme.test/contact": {"url": "https://acme.test/contact", "status": 200, "content_type": "text/html", "text": """
            <html><head><title>Contact</title></head><body><h1>Contact us</h1>
            <form><input name='name'><input name='phone'><textarea name='message'></textarea><button>Send</button></form>
            </body></html>
        """},
    }

    def fetch(url):
        if url in pages:
            return pages[url]
        raise ValueError("not found")

    run_site_intelligence(conn, bid, fetcher=fetch)
    conn.close()

    app.config.update(TESTING=True, SECRET_KEY="block2-test-only")
    client = app.test_client()

    response = client.get(f"/business/{bid}/intelligence")
    check("intelligence route renders the Block 2 build gate", response.status_code == 200 and b"Build Upgrade Blueprint" in response.data)
    check("blueprint creation is POST-only", client.get(f"/business/{bid}/upgrade/build").status_code == 405)

    response = client.post(f"/business/{bid}/upgrade/build", follow_redirects=True)
    check("blueprint route creates and renders the decision", response.status_code == 200 and b"THE DECISION" in response.data)
    check("focused upgrade includes structured estimate path", b"structured estimate" in response.data.lower())
    check("UI explains that evidence does not change production", b"Nothing here changes the website" in response.data)

    response = client.get(f"/business/{bid}/sales")
    check("sales workspace exposes the evidence-backed decision", response.status_code == 200 and b"EVIDENCE-BACKED SALES DECISION" in response.data)

    response = client.post(
        f"/business/{bid}/upgrade/verify",
        data={"claim_key": "CONTACT_PHONE", "decision": "CONFIRMED", "confirmed_value": "732-555-0100", "note": "Owner confirmed."},
        follow_redirects=True,
    )
    check("owner answer creates a refreshed blueprint in the UI", response.status_code == 200 and b"OWNER CONFIRMED" in response.data)

    conn = db.connect()
    current = upgrade_workspace_view(conn, bid)
    other = upgrade_workspace_view(conn, other_id)
    check("integration keeps blueprint data tenant-scoped", current["blueprint"] is not None and other["blueprint"] is None)
    state = conn.execute(
        "SELECT status,lifecycle_stage,automation_enabled FROM businesses WHERE id=?", (bid,)
    ).fetchone()
    check("build and verification do not activate or convert the prospect", state["status"] == "Researching" and state["lifecycle_stage"] != "ACTIVE" and state["automation_enabled"] == 0)
    check("no outbound provider work was created", conn.execute("SELECT COUNT(*) FROM outbound_messages").fetchone()[0] == 0)
    verification_count = conn.execute("SELECT COUNT(*) FROM owner_truth_verifications WHERE business_id=?", (bid,)).fetchone()[0]
    conn.close()

    response = client.post(
        f"/business/{bid}/upgrade/verify",
        data={"claim_key": "DROP_TABLE", "decision": "MAGIC", "confirmed_value": "bad"},
        follow_redirects=True,
    )
    conn = db.connect()
    check("malformed verification fails closed at the route", response.status_code == 200 and conn.execute("SELECT COUNT(*) FROM owner_truth_verifications WHERE business_id=?", (bid,)).fetchone()[0] == verification_count)

    run_site_intelligence(conn, bid, fetcher=fetch)
    stale = upgrade_workspace_view(conn, bid)
    check("a newer crawl marks the old blueprint stale", stale["stale"] is True)
    conn.close()

print("ALL V15 BLOCK 2 INTEGRATION TESTS PASSED")
