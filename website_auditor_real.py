import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "business_os.db"

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152 Safari/537.36"
    )
}


# ---------------------------------------------------------
# DETECTION RULES
# ---------------------------------------------------------

ESTIMATE_TERMS = [
    "free estimate",
    "request an estimate",
    "request estimate",
    "get an estimate",
    "get estimate",
    "free quote",
    "request a quote",
    "request quote",
    "get a quote",
    "get quote",
]

BOOKING_TERMS = [
    "book now",
    "book online",
    "schedule online",
    "schedule now",
    "schedule an appointment",
    "book an appointment",
    "make an appointment",
    "request appointment",
]

EMERGENCY_TERMS = [
    "24/7 emergency",
    "24 hour emergency",
    "24-hour emergency",
    "emergency tree service",
    "emergency service",
    "emergency services",
    "storm damage",
    "storm cleanup",
    "storm clean up",
    "emergency tree removal",
]

CHAT_TERMS = [
    "live chat",
    "chat with us",
    "chat now",
    "start chat",
    "message us",
]

CHAT_TECHNOLOGY_TERMS = [
    "intercom",
    "tawk.to",
    "tidio",
    "crisp.chat",
    "livechat",
    "livechatinc",
    "drift",
    "drift.com",
    "olark",
    "chatra",
    "zendesk",
    "zopim",
    "hubspot-messages",
    "hubspot conversations",
    "freshchat",
]

RELEVANT_LINK_TERMS = [
    "estimate",
    "quote",
    "contact",
    "schedule",
    "booking",
    "appointment",
    "emergency",
    "storm",
]


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def prepare_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    columns = cursor.execute(
        "PRAGMA table_info(businesses)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    migrations = {
        "audit_status": "TEXT DEFAULT 'not_audited'",
        "audited_at": "TEXT DEFAULT ''",
        "audit_evidence": "TEXT DEFAULT ''",
        "audit_pages_checked": "INTEGER DEFAULT 0",
    }

    for column_name, column_definition in migrations.items():
        if column_name not in column_names:
            print(f"Adding database field: {column_name}")
            cursor.execute(
                f"""
                ALTER TABLE businesses
                ADD COLUMN {column_name} {column_definition}
                """
            )

    connection.commit()
    connection.close()


def get_businesses():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    businesses = connection.execute(
        """
        SELECT *
        FROM businesses
        WHERE website IS NOT NULL
        AND TRIM(website) != ''
        ORDER BY id
        """
    ).fetchall()

    connection.close()

    return businesses


def update_audit(
    business_id,
    status,
    online_booking=None,
    emergency_service=None,
    website_chat=None,
    estimate_form=None,
    evidence=None,
    pages_checked=0,
):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    audited_at = datetime.now().isoformat(timespec="seconds")

    if status == "completed":
        cursor.execute(
            """
            UPDATE businesses
            SET online_booking = ?,
                emergency_service = ?,
                website_chat = ?,
                estimate_form = ?,
                audit_status = ?,
                audited_at = ?,
                audit_evidence = ?,
                audit_pages_checked = ?
            WHERE id = ?
            """,
            (
                int(bool(online_booking)),
                int(bool(emergency_service)),
                int(bool(website_chat)),
                int(bool(estimate_form)),
                status,
                audited_at,
                json.dumps(evidence or {}, indent=2),
                pages_checked,
                business_id,
            ),
        )

    else:
        # If the website could not be reliably audited,
        # do NOT overwrite the feature fields.
        cursor.execute(
            """
            UPDATE businesses
            SET audit_status = ?,
                audited_at = ?,
                audit_evidence = ?,
                audit_pages_checked = ?
            WHERE id = ?
            """,
            (
                status,
                audited_at,
                json.dumps(evidence or {}, indent=2),
                pages_checked,
                business_id,
            ),
        )

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# WEBSITE HELPERS
# ---------------------------------------------------------

def normalize_url(url):
    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def same_domain(url_a, url_b):
    domain_a = urlparse(url_a).netloc.lower().replace("www.", "")
    domain_b = urlparse(url_b).netloc.lower().replace("www.", "")

    return domain_a == domain_b


def fetch_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if "text/html" not in content_type:
        raise ValueError("Response was not an HTML webpage")

    return response.url, response.text


def clean_text(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    return " ".join(soup.stripped_strings).lower()


def find_matching_terms(text, terms):
    matches = []

    for term in terms:
        if term.lower() in text:
            matches.append(term)

    return sorted(set(matches))


def find_relevant_links(soup, base_url):
    links = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        anchor_text = " ".join(anchor.stripped_strings).lower()

        if not href:
            continue

        absolute_url = urljoin(base_url, href)

        if not absolute_url.startswith(("http://", "https://")):
            continue

        if not same_domain(base_url, absolute_url):
            continue

        combined = f"{anchor_text} {absolute_url}".lower()

        if any(term in combined for term in RELEVANT_LINK_TERMS):
            clean_url = absolute_url.split("#")[0]

            if clean_url not in links:
                links.append(clean_url)

    return links[:5]


# ---------------------------------------------------------
# FEATURE DETECTION
# ---------------------------------------------------------

def analyze_html(url, html):
    soup = BeautifulSoup(html, "html.parser")

    visible_text = clean_text(BeautifulSoup(html, "html.parser"))
    raw_html = html.lower()

    estimate_matches = find_matching_terms(
        visible_text,
        ESTIMATE_TERMS,
    )

    booking_matches = find_matching_terms(
        visible_text,
        BOOKING_TERMS,
    )

    emergency_matches = find_matching_terms(
        visible_text,
        EMERGENCY_TERMS,
    )

    chat_text_matches = find_matching_terms(
        visible_text,
        CHAT_TERMS,
    )

    chat_technology_matches = find_matching_terms(
        raw_html,
        CHAT_TECHNOLOGY_TERMS,
    )

    forms = soup.find_all("form")

    form_text = " ".join(
        " ".join(form.stripped_strings).lower()
        for form in forms
    )

    estimate_form_matches = find_matching_terms(
        form_text,
        ESTIMATE_TERMS,
    )

    booking_form_matches = find_matching_terms(
        form_text,
        BOOKING_TERMS,
    )

    estimate_found = bool(
        estimate_matches
        or estimate_form_matches
    )

    booking_found = bool(
        booking_matches
        or booking_form_matches
    )

    chat_found = bool(
        chat_text_matches
        or chat_technology_matches
    )

    emergency_found = bool(emergency_matches)

    return {
        "url": url,
        "estimate_found": estimate_found,
        "booking_found": booking_found,
        "chat_found": chat_found,
        "emergency_found": emergency_found,
        "estimate_evidence": sorted(
            set(estimate_matches + estimate_form_matches)
        ),
        "booking_evidence": sorted(
            set(booking_matches + booking_form_matches)
        ),
        "chat_evidence": sorted(
            set(chat_text_matches + chat_technology_matches)
        ),
        "emergency_evidence": emergency_matches,
        "forms_found": len(forms),
        "links": find_relevant_links(soup, url),
    }


# ---------------------------------------------------------
# AUDIT ONE BUSINESS
# ---------------------------------------------------------

def audit_business(business):
    business_id = business["id"]
    name = business["name"]
    website = normalize_url(business["website"])

    print()
    print("-" * 70)
    print(name)
    print(website)

    pages_checked = []
    page_results = []

    try:
        final_url, html = fetch_page(website)

        result = analyze_html(final_url, html)

        pages_checked.append(final_url)
        page_results.append(result)

        relevant_links = result["links"]

        for link in relevant_links:
            if link in pages_checked:
                continue

            try:
                time.sleep(0.5)

                page_url, page_html = fetch_page(link)

                if page_url in pages_checked:
                    continue

                page_result = analyze_html(
                    page_url,
                    page_html,
                )

                pages_checked.append(page_url)
                page_results.append(page_result)

            except Exception as page_error:
                print(
                    f"  Could not inspect extra page: {link}"
                )
                print(
                    f"  Reason: {page_error}"
                )

        estimate_found = any(
            page["estimate_found"]
            for page in page_results
        )

        booking_found = any(
            page["booking_found"]
            for page in page_results
        )

        chat_found = any(
            page["chat_found"]
            for page in page_results
        )

        emergency_found = any(
            page["emergency_found"]
            for page in page_results
        )

        evidence = {
            "website": website,
            "pages_checked": pages_checked,
            "results": page_results,
        }

        update_audit(
            business_id=business_id,
            status="completed",
            online_booking=booking_found,
            emergency_service=emergency_found,
            website_chat=chat_found,
            estimate_form=estimate_found,
            evidence=evidence,
            pages_checked=len(pages_checked),
        )

        print(f"  Pages checked: {len(pages_checked)}")
        print(
            f"  Estimate / quote: "
            f"{'FOUND' if estimate_found else 'NOT FOUND'}"
        )
        print(
            f"  Online booking:   "
            f"{'FOUND' if booking_found else 'NOT FOUND'}"
        )
        print(
            f"  Website chat:     "
            f"{'FOUND' if chat_found else 'NOT FOUND'}"
        )
        print(
            f"  Emergency service:"
            f" {'FOUND' if emergency_found else 'NOT FOUND'}"
        )

        return True

    except Exception as error:
        evidence = {
            "website": website,
            "error": str(error),
        }

        update_audit(
            business_id=business_id,
            status="failed",
            evidence=evidence,
            pages_checked=len(pages_checked),
        )

        print("  AUDIT FAILED")
        print(f"  Reason: {error}")

        return False


# ---------------------------------------------------------
# RUN AUDITOR
# ---------------------------------------------------------

def main():
    print()
    print("BUSINESS OS - REAL WEBSITE AUDITOR")
    print("=" * 70)

    prepare_database()

    businesses = get_businesses()

    if not businesses:
        print()
        print("No businesses with websites were found.")
        return

    print()
    print(
        f"Found {len(businesses)} businesses "
        f"with websites."
    )

    successful = 0
    failed = 0

    for business in businesses:
        result = audit_business(business)

        if result:
            successful += 1
        else:
            failed += 1

        time.sleep(0.75)

    print()
    print("=" * 70)
    print(f"Successful audits: {successful}")
    print(f"Failed audits:     {failed}")
    print()
    print("Website Auditor complete.")
    print()


if __name__ == "__main__":
    main()