"""Business OS v15 — Prospect Website Intelligence foundation."""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from collections import deque
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 BusinessOS-WebsiteIntelligence/16"
REQUEST_TIMEOUT = 10
MAX_REDIRECTS = 4
MAX_PAGES = 12
MAX_BYTES = 2_000_000
MAX_ASSETS_PER_PAGE = 40

CAPABILITIES = (
    "PHONE_CONTACT", "GENERAL_CONTACT_FORM", "ESTIMATE_REQUEST", "PHOTO_UPLOAD",
    "SCHEDULING_REQUEST", "LIVE_BOOKING", "AFTER_HOURS_INTAKE",
    "URGENT_REQUEST_ROUTING", "FAQ", "REVIEW_DISPLAY",
    "SERVICE_AREA_QUALIFICATION", "FINANCING_CTA", "LEAD_ACKNOWLEDGMENT",
    "CUSTOMER_PORTAL", "PAYMENT",
)
BOOKING_HOSTS = (
    "calendly.com", "acuityscheduling.com", "setmore.com", "vagaro.com",
    "booksy.com", "simplybook.me", "youcanbook.me", "mindbodyonline.com",
)
PAYMENT_HOSTS = ("stripe.com", "squareup.com", "paypal.com")


def ensure_intelligence_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS site_intelligence_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        requested_url TEXT NOT NULL,
        canonical_url TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'RUNNING',
        pages_discovered INTEGER NOT NULL DEFAULT 0,
        pages_analyzed INTEGER NOT NULL DEFAULT 0,
        evidence_count INTEGER NOT NULL DEFAULT 0,
        asset_count INTEGER NOT NULL DEFAULT 0,
        error_code TEXT NOT NULL DEFAULT '',
        error_detail TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    );
    CREATE INDEX IF NOT EXISTS idx_v15_runs_business ON site_intelligence_runs(business_id, id DESC);

    CREATE TABLE IF NOT EXISTS site_intelligence_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        business_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        meta_description TEXT NOT NULL DEFAULT '',
        primary_heading TEXT NOT NULL DEFAULT '',
        word_count INTEGER NOT NULL DEFAULT 0,
        content_hash TEXT NOT NULL DEFAULT '',
        http_status INTEGER NOT NULL DEFAULT 0,
        content_type TEXT NOT NULL DEFAULT '',
        analyzed_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES site_intelligence_runs(id),
        FOREIGN KEY (business_id) REFERENCES businesses(id),
        UNIQUE(run_id, url)
    );
    CREATE INDEX IF NOT EXISTS idx_v15_pages_run ON site_intelligence_pages(run_id, id);

    CREATE TABLE IF NOT EXISTS site_intelligence_evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        business_id INTEGER NOT NULL,
        page_url TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        normalized_value TEXT NOT NULL DEFAULT '',
        excerpt TEXT NOT NULL DEFAULT '',
        source_kind TEXT NOT NULL DEFAULT 'PUBLIC_WEBSITE',
        confidence TEXT NOT NULL DEFAULT 'medium',
        observed_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES site_intelligence_runs(id),
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    );
    CREATE INDEX IF NOT EXISTS idx_v15_evidence_run ON site_intelligence_evidence(run_id, evidence_type);

    CREATE TABLE IF NOT EXISTS site_capability_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        business_id INTEGER NOT NULL,
        capability_key TEXT NOT NULL,
        observed_state TEXT NOT NULL,
        confidence TEXT NOT NULL,
        evidence_count INTEGER NOT NULL DEFAULT 0,
        rationale TEXT NOT NULL DEFAULT '',
        observed_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES site_intelligence_runs(id),
        FOREIGN KEY (business_id) REFERENCES businesses(id),
        UNIQUE(run_id, capability_key)
    );
    CREATE INDEX IF NOT EXISTS idx_v15_capabilities_run ON site_capability_observations(run_id, capability_key);

    CREATE TABLE IF NOT EXISTS site_asset_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        business_id INTEGER NOT NULL,
        page_url TEXT NOT NULL,
        asset_url TEXT NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'IMAGE',
        alt_text TEXT NOT NULL DEFAULT '',
        rights_status TEXT NOT NULL DEFAULT 'DISCOVERED_REFERENCE',
        production_allowed INTEGER NOT NULL DEFAULT 0,
        observed_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES site_intelligence_runs(id),
        FOREIGN KEY (business_id) REFERENCES businesses(id),
        UNIQUE(run_id, asset_url)
    );
    CREATE INDEX IF NOT EXISTS idx_v15_assets_run ON site_asset_observations(run_id, id);
    """)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def normalize_public_url(url):
    value = (url or "").strip()
    if not value:
        raise ValueError("Website URL is required.")
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP/HTTPS website URLs are supported.")
    clean, _ = urldefrag(value)
    return clean


def _host_key(url):
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def same_site(a, b):
    return _host_key(a) == _host_key(b)


def _validate_public_host(url, resolver=None):
    host = urlparse(url).hostname
    if not host:
        raise ValueError("Website URL has no hostname.")
    if host.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("Local/private targets are blocked by Website Intelligence.")
    resolver = resolver or socket.getaddrinfo
    try:
        rows = resolver(host, None)
    except socket.gaierror as exc:
        raise ValueError("Website hostname could not be resolved.") from exc
    addresses = {row[4][0] for row in rows}
    if not addresses:
        raise ValueError("Website hostname could not be resolved.")
    for raw in addresses:
        if not ipaddress.ip_address(raw).is_global:
            raise ValueError("Local/private network targets are blocked by Website Intelligence.")


def _network_fetch(url, resolver=None, allow_private=False, allow_text=False):
    current = normalize_public_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        if not allow_private:
            _validate_public_host(current, resolver=resolver)
        response = requests.get(
            current,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            stream=True,
        )
        if 300 <= response.status_code < 400 and response.headers.get("Location"):
            nxt = urljoin(current, response.headers["Location"])
            if not same_site(current, nxt):
                raise ValueError("Cross-site redirects are not followed by Website Intelligence.")
            current = normalize_public_url(nxt)
            continue
        if response.status_code >= 400:
            raise ValueError(f"Website returned HTTP {response.status_code}.")
        ctype = (response.headers.get("Content-Type") or "").lower()
        length = response.headers.get("Content-Length")
        if length and length.isdigit() and int(length) > MAX_BYTES:
            raise ValueError("Page exceeded Website Intelligence size limit.")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError("Page exceeded Website Intelligence size limit.")

        # Some otherwise-valid public sites vary Content-Type by user-agent/CDN.
        # Accept declared HTML, and safely sniff HTML only when the body itself
        # clearly begins as an HTML document. This keeps binary/media targets out.
        is_html = "text/html" in ctype or "application/xhtml+xml" in ctype
        is_text = "text/plain" in ctype
        prefix = bytes(data[:2048]).lstrip().lower()
        sniffed_html = (
            prefix.startswith(b"<!doctype html")
            or prefix.startswith(b"<html")
            or b"<html" in prefix[:1024]
            or b"<head" in prefix[:1024]
        )
        if not is_html and not sniffed_html and not (allow_text and is_text):
            detail = ctype or "missing Content-Type"
            raise ValueError(f"Target did not return an allowed webpage content type ({detail}).")

        encoding = response.encoding or "utf-8"
        return {"url": response.url or current, "status": response.status_code,
                "content_type": ctype or ("text/html; sniffed" if sniffed_html else ""),
                "text": data.decode(encoding, errors="replace")}
    raise ValueError("Website exceeded redirect limit.")


def _robots_allowed(base_url, fetcher):
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        result = fetcher(robots_url)
    except Exception:
        return True
    text = result.get("text", "") if isinstance(result, dict) else ""
    if not text:
        return True
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    return parser.can_fetch(USER_AGENT, base_url)


def _clean_text(value, limit=500):
    return re.sub(r"\s+", " ", unescape(value or "")).strip()[:limit]


def _visible_text(soup):
    clone = BeautifulSoup(str(soup), "html.parser")
    for node in clone(["script", "style", "noscript", "svg"]):
        node.decompose()
    return _clean_text(" ".join(clone.stripped_strings), 12000)


def _form_text(form):
    bits = list(form.stripped_strings)
    for node in form.find_all(["input", "textarea", "select", "button"]):
        for key in ("type", "name", "id", "placeholder", "aria-label", "value"):
            if node.get(key):
                bits.append(str(node.get(key)))
    return _clean_text(" ".join(bits), 1200).lower().replace("_", " ").replace("-", " ")


def _page_observations(url, html):
    soup = BeautifulSoup(html, "html.parser")
    visible = _visible_text(soup)
    low = visible.lower()
    title = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "", 240)
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_desc = _clean_text(meta.get("content", "") if meta else "", 500)
    h1 = soup.find("h1")
    primary_heading = _clean_text(h1.get_text(" ", strip=True) if h1 else "", 300)
    evidence, assets = [], []
    present = {key: [] for key in CAPABILITIES}

    def add(kind, value="", excerpt="", confidence="high"):
        evidence.append({"type": kind, "value": _clean_text(value, 300),
                         "excerpt": _clean_text(excerpt, 500), "confidence": confidence})

    if title: add("PAGE_TITLE", title, url, "high")
    if meta_desc: add("META_DESCRIPTION", meta_desc, url, "high")
    if primary_heading: add("PRIMARY_HEADING", primary_heading, url, "high")
    # Persist bounded visible-page context so later design passes can preserve useful
    # source-site information without re-crawling or depending on model memory.
    if visible: add("PAGE_TEXT", visible[:4000], url, "medium")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        label = _clean_text(a.get_text(" ", strip=True), 180)
        lower_href = href.lower()
        combined = f"{label} {href}".lower()
        if any(host in lower_href for host in ("facebook.com","instagram.com","linkedin.com","youtube.com","tiktok.com","x.com","twitter.com")):
            add("SOCIAL_LINK", href, label or href, "high")
        if lower_href.startswith("tel:"):
            add("CONTACT_PHONE", href[4:], label or href)
            present["PHONE_CONTACT"].append(label or href)
        elif lower_href.startswith("mailto:"):
            add("CONTACT_EMAIL", href[7:].split("?")[0], label or href)
        if label:
            add("CTA", label, href, "medium")
        if any(term in combined for term in ("estimate", "quote")):
            present["ESTIMATE_REQUEST"].append(label or href)
        if any(term in combined for term in ("schedule", "appointment", "book")):
            present["SCHEDULING_REQUEST"].append(label or href)
        if any(host in lower_href for host in BOOKING_HOSTS):
            present["LIVE_BOOKING"].append(href)
        if any(term in combined for term in ("login", "client portal", "customer portal", "my account")):
            present["CUSTOMER_PORTAL"].append(label or href)
        if any(host in lower_href for host in PAYMENT_HOSTS) or any(term in combined for term in ("pay online", "make a payment")):
            present["PAYMENT"].append(label or href)
        if "financ" in combined:
            present["FINANCING_CTA"].append(label or href)

    for form in soup.find_all("form"):
        context = _form_text(form)
        add("FORM", form.get("action", ""), context)
        contact_hits = sum(word in context for word in ("name", "email", "phone", "message", "address"))
        if contact_hits >= 2:
            present["GENERAL_CONTACT_FORM"].append(context[:160])
            present["AFTER_HOURS_INTAKE"].append("web form available")
        if "estimate" in context or "quote" in context:
            present["ESTIMATE_REQUEST"].append(context[:160])
        if form.find("input", attrs={"type": "file"}):
            present["PHOTO_UPLOAD"].append(context[:160])
        if any(term in context for term in ("schedule", "appointment", "preferred date", "preferred time")):
            present["SCHEDULING_REQUEST"].append(context[:160])
        if any(term in context for term in ("urgent", "emergency", "immediate")):
            present["URGENT_REQUEST_ROUTING"].append(context[:160])
        if any(term in context for term in ("zip", "postal", "service area")):
            present["SERVICE_AREA_QUALIFICATION"].append(context[:160])

    if any(term in low for term in ("frequently asked questions", "faq")) or soup.find("details"):
        present["FAQ"].append("FAQ content detected")
        for d in soup.find_all("details")[:20]:
            q=d.find("summary"); qtext=_clean_text(q.get_text(" ",strip=True) if q else "",260)
            full=_clean_text(d.get_text(" ",strip=True),700)
            if qtext: add("FAQ_QA",qtext,full,"high")
    if any(term in low for term in ("testimonial", "what our customers say", "customer reviews", "google reviews")):
        present["REVIEW_DISPLAY"].append("review/testimonial language detected")
    if any(term in low for term in ("financing available", "financing options", "payment plans")):
        present["FINANCING_CTA"].append("financing language detected")

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        payload = _clean_text(script.string or script.get_text(" "), 2500)
        if payload:
            add("STRUCTURED_DATA", "json-ld", payload, "medium")
            if "FAQPage" in payload:
                present["FAQ"].append("FAQPage structured data")
            if "AggregateRating" in payload or "Review" in payload:
                present["REVIEW_DISPLAY"].append("review structured data")

    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = _clean_text(heading.get_text(" ", strip=True), 220)
        if text:
            add("HEADING", text, url, "medium")

    for img in soup.find_all("img", src=True)[:MAX_ASSETS_PER_PAGE]:
        src = urljoin(url, img.get("src", "").strip())
        if src.startswith(("http://", "https://")):
            alt = _clean_text(img.get("alt", ""), 240)
            typ = "LOGO" if "logo" in (src + " " + alt).lower() else "IMAGE"
            assets.append({"url": src, "type": typ, "alt": alt})

    links = []
    for a in soup.find_all("a", href=True):
        absolute, _ = urldefrag(urljoin(url, a.get("href", "").strip()))
        path_low = urlparse(absolute).path.lower()
        obvious_nonpage = (
            path_low.endswith((".xml", ".rss", ".atom", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip"))
            or "/feed/" in path_low
            or path_low.endswith("/feed")
        )
        if (
            absolute.startswith(("http://", "https://"))
            and same_site(url, absolute)
            and not obvious_nonpage
            and absolute not in links
        ):
            links.append(absolute)

    return {
        "title": title, "meta_description": meta_desc, "primary_heading": primary_heading,
        "word_count": len(visible.split()),
        "content_hash": hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest(),
        "evidence": evidence, "assets": assets, "capabilities": present, "links": links,
    }


def _capability_summary(collected, pages_analyzed):
    output = []
    for key in CAPABILITIES:
        items = []
        for page in collected:
            items.extend(page["analysis"]["capabilities"].get(key, []))
        count = len(items)
        if key == "LEAD_ACKNOWLEDGMENT":
            state, confidence, rationale = "UNKNOWN", "low", "Cannot be proven by static website observation alone."
        elif count:
            state = "PRESENT"
            confidence = "high" if count >= 2 or key in {"PHONE_CONTACT", "PHOTO_UPLOAD", "LIVE_BOOKING", "PAYMENT"} else "medium"
            rationale = _clean_text(items[0], 260)
        elif pages_analyzed >= 2:
            state, confidence, rationale = "NOT_DETECTED", "medium", f"Not detected across {pages_analyzed} analyzed public pages."
        else:
            state, confidence, rationale = "UNKNOWN", "low", "Insufficient public-page coverage to call this missing."
        output.append({"key": key, "state": state, "confidence": confidence, "count": count, "rationale": rationale})
    return output


def run_site_intelligence(conn, business_id, *, fetcher=None, resolver=None, max_pages=MAX_PAGES, allow_private=False):
    ensure_intelligence_schema(conn)
    business = conn.execute("SELECT id, name, website FROM businesses WHERE id = ?", (business_id,)).fetchone()
    if not business:
        raise LookupError("Business not found.")
    start_url = normalize_public_url(business["website"])
    network = fetcher or (lambda url: _network_fetch(url, resolver=resolver, allow_private=allow_private))
    if fetcher is None and not allow_private:
        _validate_public_host(start_url, resolver=resolver)

    cur = conn.execute(
        "INSERT INTO site_intelligence_runs (business_id, requested_url, started_at) VALUES (?, ?, ?)",
        (business_id, start_url, _now()),
    )
    run_id = cur.lastrowid
    conn.commit()
    try:
        robots_fetcher = network if fetcher is not None else (
            lambda url: _network_fetch(url, resolver=resolver, allow_private=allow_private, allow_text=True)
        )
        if not _robots_allowed(start_url, robots_fetcher):
            raise ValueError("Website robots.txt does not allow this crawler to fetch the supplied URL.")
        queue, seen, seen_final, collected = deque([start_url]), set(), set(), []
        canonical = start_url
        while queue and len(collected) < max(1, min(int(max_pages), MAX_PAGES)):
            target = queue.popleft()
            if target in seen:
                continue
            seen.add(target)
            try:
                result = network(target)
            except ValueError as exc:
                # A normal HTML page can link to RSS/Atom feeds, XML sitemaps,
                # PDFs, images, or other same-site resources. Those resources are
                # not webpage-analysis failures. Only the starting URL must be a
                # usable webpage; unsupported child resources are skipped.
                if collected and "allowed webpage content type" in str(exc).lower():
                    continue
                raise
            final_url = normalize_public_url(result.get("url", target))
            if not same_site(start_url, final_url):
                continue
            # Different discovered URLs can redirect/canonicalize to the same final
            # webpage (for example trailing-slash or WordPress aliases). Persist a
            # final canonical page only once per run so duplicate redirects cannot
            # violate the (run_id, url) uniqueness invariant.
            if final_url in seen_final:
                continue
            seen_final.add(final_url)
            html = result.get("text", "")
            if not html:
                continue
            analysis = _page_observations(final_url, html)
            if not collected:
                canonical = final_url
            collected.append({"url": final_url, "status": int(result.get("status", 200)),
                              "content_type": result.get("content_type", "text/html"), "analysis": analysis})
            for link in analysis["links"]:
                if link not in seen and same_site(start_url, link):
                    queue.append(link)

        observed_at = _now()
        for page in collected:
            a = page["analysis"]
            conn.execute("""INSERT INTO site_intelligence_pages
                (run_id,business_id,url,title,meta_description,primary_heading,word_count,content_hash,http_status,content_type,analyzed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id,business_id,page["url"],a["title"],a["meta_description"],a["primary_heading"],a["word_count"],a["content_hash"],page["status"],page["content_type"],observed_at))
            for ev in a["evidence"]:
                conn.execute("""INSERT INTO site_intelligence_evidence
                    (run_id,business_id,page_url,evidence_type,normalized_value,excerpt,confidence,observed_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (run_id,business_id,page["url"],ev["type"],ev["value"],ev["excerpt"],ev["confidence"],observed_at))
            for asset in a["assets"]:
                conn.execute("""INSERT OR IGNORE INTO site_asset_observations
                    (run_id,business_id,page_url,asset_url,asset_type,alt_text,observed_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (run_id,business_id,page["url"],asset["url"],asset["type"],asset["alt"],observed_at))

        for cap in _capability_summary(collected, len(collected)):
            conn.execute("""INSERT INTO site_capability_observations
                (run_id,business_id,capability_key,observed_state,confidence,evidence_count,rationale,observed_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (run_id,business_id,cap["key"],cap["state"],cap["confidence"],cap["count"],cap["rationale"],observed_at))
        evidence_count = conn.execute("SELECT COUNT(*) FROM site_intelligence_evidence WHERE run_id=?", (run_id,)).fetchone()[0]
        asset_count = conn.execute("SELECT COUNT(*) FROM site_asset_observations WHERE run_id=?", (run_id,)).fetchone()[0]
        conn.execute("""UPDATE site_intelligence_runs SET canonical_url=?, status='COMPLETED', pages_discovered=?, pages_analyzed=?, evidence_count=?, asset_count=?, completed_at=? WHERE id=?""",
                     (canonical, len(seen), len(collected), evidence_count, asset_count, _now(), run_id))
        conn.commit()
        from services.v21_business_knowledge import rebuild_business_knowledge
        rebuild_business_knowledge(conn, business_id, run_id)
        return intelligence_view(conn, business_id, run_id=run_id)
    except Exception as exc:
        conn.execute("UPDATE site_intelligence_runs SET status='FAILED', error_code=?, error_detail=?, completed_at=? WHERE id=?",
                     (type(exc).__name__, str(exc)[:800], _now(), run_id))
        conn.commit()
        raise


def intelligence_view(conn, business_id, run_id=None):
    ensure_intelligence_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise LookupError("Business not found.")
    if run_id is None:
        run = conn.execute("SELECT * FROM site_intelligence_runs WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)).fetchone()
    else:
        run = conn.execute("SELECT * FROM site_intelligence_runs WHERE id=? AND business_id=?", (run_id,business_id)).fetchone()
    if not run:
        return {"business": dict(business), "run": None, "pages": [], "capabilities": [], "evidence": [], "assets": []}
    rid = run["id"]
    return {
        "business": dict(business), "run": dict(run),
        "pages": [dict(r) for r in conn.execute("SELECT * FROM site_intelligence_pages WHERE run_id=? ORDER BY id", (rid,)).fetchall()],
        "capabilities": [dict(r) for r in conn.execute("SELECT * FROM site_capability_observations WHERE run_id=? ORDER BY capability_key", (rid,)).fetchall()],
        "evidence": [dict(r) for r in conn.execute("SELECT * FROM site_intelligence_evidence WHERE run_id=? ORDER BY id LIMIT 120", (rid,)).fetchall()],
        "assets": [dict(r) for r in conn.execute("SELECT * FROM site_asset_observations WHERE run_id=? ORDER BY id LIMIT 80", (rid,)).fetchall()],
    }
