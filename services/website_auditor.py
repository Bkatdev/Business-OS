import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from services.db import connect


REQUEST_TIMEOUT = 18
MAX_EXTRA_PAGES = 4


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152 Safari/537.36 BusinessOSResearch/2.0"
    )
}


ESTIMATE_OFFER_TERMS = [
    "free estimate",
    "request an estimate",
    "request estimate",
    "get an estimate",
    "free quote",
    "request a quote",
    "request quote",
    "get a quote",
]


EMERGENCY_TERMS = [
    "24/7 emergency",
    "24 hour emergency",
    "24-hour emergency",
    "emergency tree service",
    "emergency service",
    "emergency services",
    "emergency tree removal",
    "storm damage",
    "storm cleanup",
    "storm clean up",
]


SCHEDULING_MENTION_TERMS = [
    "schedule an appointment",
    "schedule appointment",
    "book an appointment",
    "make an appointment",
    "appointment request",
]


CHAT_VISIBLE_TERMS = [
    "live chat",
    "chat with us",
    "chat now",
    "start chat",
]


CHAT_TECH_TERMS = [
    "intercom",
    "tawk.to",
    "tidio",
    "crisp.chat",
    "livechatinc",
    "drift.com",
    "olark",
    "chatra",
    "zopim",
    "freshchat",
    "hubspot-messages",
    "hubspot conversations",
]


BOOKING_TECH_TERMS = [
    "calendly.com",
    "acuityscheduling.com",
    "squareup.com/appointments",
    "square.site/appointments",
    "setmore.com",
    "booksy.com",
    "mindbodyonline.com",
    "vagaro.com",
    "appointy.com",
    "simplybook.me",
    "youcanbook.me",
]


MARKETPLACE_DOMAINS = {
    "thumbtack.com",
    "yelp.com",
    "angi.com",
    "homeadvisor.com",
    "facebook.com",
    "instagram.com",
    "nextdoor.com",
}


RELEVANT_LINK_TERMS = [
    "estimate",
    "quote",
    "contact",
    "schedule",
    "booking",
    "appointment",
    "emergency",
    "storm",
    "service",
]


def normalize_url(url):
    url = (url or "").strip()

    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def get_domain(url):
    return (
        urlparse(url)
        .netloc
        .lower()
        .replace("www.", "")
    )


def same_domain(url_a, url_b):
    return get_domain(url_a) == get_domain(url_b)


def classify_website(url):
    domain = get_domain(url)

    if domain == "sites.google.com":
        return "google_sites"

    for marketplace in MARKETPLACE_DOMAINS:
        if (
            domain == marketplace
            or domain.endswith("." + marketplace)
        ):
            return "marketplace"

    return "owned"


def fetch_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    content_type = (
        response.headers
        .get("Content-Type", "")
        .lower()
    )

    if "text/html" not in content_type:
        raise ValueError(
            "The URL did not return an HTML webpage."
        )

    return response.url, response.text


def visible_text_from_html(html):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()

    return " ".join(
        soup.stripped_strings
    ).lower()


def find_matches(text, terms):
    return sorted(
        {
            term
            for term in terms
            if term in text
        }
    )


def form_context(form):
    parts = [
        " ".join(form.stripped_strings),
        form.get("action", ""),
        form.get("id", ""),
        " ".join(
            form.get("class", [])
        ),
    ]

    for element in form.find_all(
        [
            "input",
            "textarea",
            "select",
            "button",
        ]
    ):
        for attribute in [
            "name",
            "id",
            "placeholder",
            "value",
            "type",
            "aria-label",
        ]:
            value = element.get(attribute)

            if value:
                parts.append(
                    str(value)
                )

    return " ".join(parts).lower()


def form_has_contact_fields(form):
    context = form_context(form)

    signals = [
        "name",
        "email",
        "phone",
        "message",
        "address",
    ]

    matches = sum(
        signal in context
        for signal in signals
    )

    return matches >= 2


def detect_estimate_form(soup):
    evidence = []

    for form in soup.find_all("form"):
        context = form_context(form)

        estimate_language = any(
            term in context
            for term in [
                "estimate",
                "quote",
                "pricing request",
            ]
        )

        if (
            estimate_language
            and form_has_contact_fields(form)
        ):
            evidence.append(
                "estimate/quote form with contact fields"
            )

    return (
        bool(evidence),
        sorted(set(evidence)),
    )


def detect_booking(soup, html):
    evidence = []

    raw_html = html.lower()

    evidence.extend(
        find_matches(
            raw_html,
            BOOKING_TECH_TERMS,
        )
    )

    for element in soup.find_all(
        ["a", "iframe"]
    ):
        href = (
            element.get("href")
            or element.get("src")
            or ""
        ).lower()

        evidence.extend(
            find_matches(
                href,
                BOOKING_TECH_TERMS,
            )
        )

    for form in soup.find_all("form"):
        context = form_context(form)

        has_booking_words = any(
            word in context
            for word in [
                "book",
                "schedule",
                "appointment",
            ]
        )

        has_date_or_time = bool(
            form.find(
                "input",
                {
                    "type": re.compile(
                        r"^(date|datetime-local|time)$"
                    )
                },
            )
        )

        if (
            has_booking_words
            and has_date_or_time
        ):
            evidence.append(
                "booking form with date/time field"
            )

    evidence = sorted(set(evidence))

    return (
        bool(evidence),
        evidence,
    )


def detect_chat(html, visible_text):
    technology_evidence = find_matches(
        html.lower(),
        CHAT_TECH_TERMS,
    )

    visible_evidence = find_matches(
        visible_text,
        CHAT_VISIBLE_TERMS,
    )

    evidence = sorted(
        set(
            technology_evidence
            + visible_evidence
        )
    )

    # We only mark actual chat as detected
    # when a known chat technology appears.
    found = bool(
        technology_evidence
    )

    return found, evidence


def find_relevant_links(
    soup,
    base_url,
):
    links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = (
            anchor
            .get("href", "")
            .strip()
        )

        text = " ".join(
            anchor.stripped_strings
        ).lower()

        absolute_url = urljoin(
            base_url,
            href,
        ).split("#")[0]

        if not absolute_url.startswith(
            ("http://", "https://")
        ):
            continue

        if not same_domain(
            base_url,
            absolute_url,
        ):
            continue

        combined = (
            f"{text} {absolute_url}"
        ).lower()

        if any(
            term in combined
            for term in RELEVANT_LINK_TERMS
        ):
            if absolute_url not in links:
                links.append(
                    absolute_url
                )

    return links[:MAX_EXTRA_PAGES]


def analyze_page(
    url,
    html,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    visible_text = visible_text_from_html(
        html
    )

    estimate_offer_evidence = find_matches(
        visible_text,
        ESTIMATE_OFFER_TERMS,
    )

    emergency_evidence = find_matches(
        visible_text,
        EMERGENCY_TERMS,
    )

    scheduling_evidence = find_matches(
        visible_text,
        SCHEDULING_MENTION_TERMS,
    )

    (
        estimate_form,
        estimate_form_evidence,
    ) = detect_estimate_form(
        soup
    )

    (
        online_booking,
        booking_evidence,
    ) = detect_booking(
        soup,
        html,
    )

    (
        website_chat,
        chat_evidence,
    ) = detect_chat(
        html,
        visible_text,
    )

    return {
        "url": url,

        "estimate_offered":
            bool(
                estimate_offer_evidence
            ),

        "estimate_form":
            estimate_form,

        "online_booking":
            online_booking,

        "website_chat":
            website_chat,

        "emergency_service":
            bool(
                emergency_evidence
            ),

        "scheduling_mentioned":
            bool(
                scheduling_evidence
            ),

        "evidence": {
            "estimate_offered":
                estimate_offer_evidence,

            "estimate_form":
                estimate_form_evidence,

            "online_booking":
                booking_evidence,

            "website_chat":
                chat_evidence,

            "emergency_service":
                emergency_evidence,

            "scheduling_mentioned":
                scheduling_evidence,
        },

        "relevant_links":
            find_relevant_links(
                soup,
                url,
            ),
    }


def merge_results(results):
    fields = [
        "estimate_offered",
        "estimate_form",
        "online_booking",
        "website_chat",
        "emergency_service",
        "scheduling_mentioned",
    ]

    merged = {}

    for field in fields:
        merged[field] = any(
            result[field]
            for result in results
        )

    return merged


def calculate_confidence(
    results,
    website_type,
):
    if not results:
        return "low"

    if website_type == "marketplace":
        return "medium"

    if len(results) >= 2:
        return "high"

    return "medium"


def save_audit(
    business_id,
    status,
    data,
    pages_checked,
    error="",
):
    conn = connect()

    audited_at = (
        datetime.now()
        .isoformat(
            timespec="seconds"
        )
    )

    if status == "completed":
        merged = data["merged"]

        conn.execute(
            """
            UPDATE businesses
            SET
                online_booking = ?,
                emergency_service = ?,
                website_chat = ?,
                estimate_form = ?,
                estimate_offered = ?,
                scheduling_mentioned = ?,
                website_type = ?,
                audit_confidence = ?,
                audit_status = 'completed',
                audited_at = ?,
                audit_evidence = ?,
                audit_pages_checked = ?
            WHERE id = ?
            """,
            (
                int(
                    merged[
                        "online_booking"
                    ]
                ),

                int(
                    merged[
                        "emergency_service"
                    ]
                ),

                int(
                    merged[
                        "website_chat"
                    ]
                ),

                int(
                    merged[
                        "estimate_form"
                    ]
                ),

                int(
                    merged[
                        "estimate_offered"
                    ]
                ),

                int(
                    merged[
                        "scheduling_mentioned"
                    ]
                ),

                data[
                    "website_type"
                ],

                data[
                    "confidence"
                ],

                audited_at,

                json.dumps(
                    data,
                    indent=2,
                ),

                pages_checked,

                business_id,
            ),
        )

    else:
        payload = {
            "error": error,
        }

        if data:
            payload.update(data)

        conn.execute(
            """
            UPDATE businesses
            SET
                audit_status = ?,
                audited_at = ?,
                audit_evidence = ?,
                audit_pages_checked = ?
            WHERE id = ?
            """,
            (
                status,

                audited_at,

                json.dumps(
                    payload,
                    indent=2,
                ),

                pages_checked,

                business_id,
            ),
        )

    conn.commit()
    conn.close()


def audit_business(business):
    website = normalize_url(
        business["website"]
    )

    if not website:
        save_audit(
            business["id"],
            "no_website",
            {
                "website": "",
            },
            0,
            "No website available.",
        )

        return {
            "ok": False,
            "status": "no_website",
            "message": "No website available.",
        }

    checked_pages = []
    results = []

    try:
        final_url, html = fetch_page(
            website
        )

        homepage_result = analyze_page(
            final_url,
            html,
        )

        checked_pages.append(
            final_url
        )

        results.append(
            homepage_result
        )

        links = homepage_result[
            "relevant_links"
        ]

        for link in links:
            if link in checked_pages:
                continue

            try:
                time.sleep(0.35)

                page_url, page_html = fetch_page(
                    link
                )

                if page_url in checked_pages:
                    continue

                checked_pages.append(
                    page_url
                )

                results.append(
                    analyze_page(
                        page_url,
                        page_html,
                    )
                )

            except Exception:
                # One secondary page failing
                # should not destroy the whole audit.
                continue

        website_type = classify_website(
            final_url
        )

        confidence = calculate_confidence(
            results,
            website_type,
        )

        payload = {
            "website": website,

            "final_url": final_url,

            "website_type":
                website_type,

            "confidence":
                confidence,

            "pages_checked":
                checked_pages,

            "merged":
                merge_results(
                    results
                ),

            "results":
                results,

            "limitations": (
                "Business OS analyzes public HTML. "
                "JavaScript-only widgets, blocked pages, "
                "or hidden workflows may not be visible."
            ),
        }

        save_audit(
            business["id"],
            "completed",
            payload,
            len(
                checked_pages
            ),
        )

        return {
            "ok": True,
            "status": "completed",
            "data": payload,
        }

    except Exception as exc:
        save_audit(
            business["id"],
            "failed",
            {
                "website":
                    website
            },
            len(
                checked_pages
            ),
            str(exc),
        )

        return {
            "ok": False,
            "status": "failed",
            "message": str(exc),
        }


def audit_business_by_id(
    business_id,
):
    conn = connect()

    business = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE id = ?
        """,
        (
            business_id,
        ),
    ).fetchone()

    conn.close()

    if business is None:
        raise LookupError(
            "Business not found."
        )

    return audit_business(
        business
    )


def audit_batch(
    mode="not_audited",
    limit=25,
):
    conn = connect()

    if mode == "all":
        businesses = conn.execute(
            """
            SELECT *
            FROM businesses
            WHERE website IS NOT NULL
              AND TRIM(website) != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            ),
        ).fetchall()

    else:
        businesses = conn.execute(
            """
            SELECT *
            FROM businesses
            WHERE website IS NOT NULL
              AND TRIM(website) != ''
              AND audit_status != 'completed'
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            ),
        ).fetchall()

    conn.close()

    results = []

    for business in businesses:
        result = audit_business(
            business
        )

        results.append(
            (
                business["id"],
                business["name"],
                result,
            )
        )

        time.sleep(0.4)

    return results