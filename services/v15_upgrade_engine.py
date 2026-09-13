"""Business OS v15 Business Truth, capability gaps, and Upgrade Blueprint.

The engine is deliberately deterministic. Public website observations stay
separate from owner-confirmed truth, conflicts fail closed, and blueprint
generation never changes production configuration or invokes a provider.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

from services.v15_site_intelligence import CAPABILITIES, ensure_intelligence_schema


TRUTH_STATES = {
    "PUBLIC_OBSERVED", "INFERRED", "OWNER_CONFIRMED", "SYSTEM_VERIFIED",
    "UNKNOWN", "CONFLICT",
}
GAP_STATES = {"PRESENT", "MISSING", "RECOMMENDED", "NOT_RELEVANT", "VERIFY", "BLOCKED"}
BLUEPRINT_ACTIONS = ("KEEP", "IMPROVE", "ADD", "VERIFY", "IGNORE")
DECISIONS = {"CONFIRMED", "REJECTED"}
COMPLEXITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3, "owner_verified": 4, "system_verified": 4}


CAPABILITY_CATALOG = {
    "PHONE_CONTACT": {
        "label": "Direct phone contact", "complexity": "LOW", "risk": 1,
        "why": "Visitors should have an immediate path to the business when a call is appropriate.",
        "benefit": "Reduces the effort required to reach the business from a phone.",
        "dimensions": (4, 3, 1, 3, 3),
    },
    "GENERAL_CONTACT_FORM": {
        "label": "General contact form", "complexity": "LOW", "risk": 1,
        "why": "A form gives visitors a request path when they cannot or do not want to call.",
        "benefit": "Keeps basic inquiries from depending entirely on business hours.",
        "dimensions": (4, 3, 2, 2, 2),
    },
    "ESTIMATE_REQUEST": {
        "label": "Structured estimate request", "complexity": "MEDIUM", "risk": 1,
        "why": "Estimate-driven businesses need more context than a generic message box provides.",
        "benefit": "Gives the owner a more useful request before the first follow-up.",
        "dimensions": (5, 5, 4, 3, 4),
    },
    "PHOTO_UPLOAD": {
        "label": "Customer photo upload", "complexity": "MEDIUM", "risk": 2,
        "why": "Photos can clarify the scope of physical work before an onsite review.",
        "benefit": "Reduces avoidable back-and-forth while preserving owner judgment.",
        "dimensions": (5, 4, 5, 2, 3),
    },
    "SCHEDULING_REQUEST": {
        "label": "Scheduling request", "complexity": "MEDIUM", "risk": 2,
        "why": "A request can capture customer timing without promising an appointment.",
        "benefit": "Collects preferred timing while keeping confirmation under owner control.",
        "dimensions": (4, 3, 4, 2, 2),
    },
    "LIVE_BOOKING": {
        "label": "Live booking", "complexity": "HIGH", "risk": 5,
        "why": "Instant booking only helps when the business has reliable availability and service-duration rules.",
        "benefit": "Can reduce scheduling friction for businesses with standardized appointments.",
        "dimensions": (4, 4, 4, 2, 2),
    },
    "AFTER_HOURS_INTAKE": {
        "label": "After-hours intake", "complexity": "LOW", "risk": 1,
        "why": "Customers often research and submit requests outside normal office hours.",
        "benefit": "Captures structured requests without implying immediate service.",
        "dimensions": (5, 4, 4, 2, 4),
    },
    "URGENT_REQUEST_ROUTING": {
        "label": "Urgency classification", "complexity": "MEDIUM", "risk": 4,
        "why": "Urgent requests need clear classification without unsafe promises or automated dispatch.",
        "benefit": "Helps the owner recognize time-sensitive requests sooner.",
        "dimensions": (5, 3, 4, 3, 5),
    },
    "FAQ": {
        "label": "Useful customer FAQ", "complexity": "LOW", "risk": 1,
        "why": "Repeated customer questions should be answered clearly using verified business policy.",
        "benefit": "Reduces routine uncertainty before a visitor submits a request.",
        "dimensions": (3, 2, 3, 3, 1),
    },
    "REVIEW_DISPLAY": {
        "label": "Review and testimonial proof", "complexity": "LOW", "risk": 2,
        "why": "Credible proof can reduce uncertainty, but the source and wording must be verifiable.",
        "benefit": "Makes existing reputation easier for visitors to evaluate.",
        "dimensions": (4, 4, 1, 5, 2),
    },
    "SERVICE_AREA_QUALIFICATION": {
        "label": "Service-area qualification", "complexity": "MEDIUM", "risk": 2,
        "why": "Location eligibility should be checked before the owner spends time on a request.",
        "benefit": "Reduces requests from locations the business does not serve.",
        "dimensions": (4, 3, 5, 2, 3),
    },
    "FINANCING_CTA": {
        "label": "Financing information", "complexity": "LOW", "risk": 4,
        "why": "Financing should only be presented when the owner confirms the provider and terms.",
        "benefit": "Can clarify purchasing options for appropriate high-value work.",
        "dimensions": (3, 3, 1, 3, 1),
    },
    "LEAD_ACKNOWLEDGMENT": {
        "label": "Request acknowledgment", "complexity": "MEDIUM", "risk": 3,
        "why": "A visitor should know a request was received without being promised an outcome or response time.",
        "benefit": "Reduces uncertainty immediately after form submission.",
        "dimensions": (5, 3, 4, 4, 3),
    },
    "CUSTOMER_PORTAL": {
        "label": "Customer portal", "complexity": "HIGH", "risk": 4,
        "why": "A portal is only useful when customers need recurring access to meaningful account information.",
        "benefit": "Can centralize repeat-customer information when the operating model supports it.",
        "dimensions": (2, 1, 2, 2, 1),
    },
    "PAYMENT": {
        "label": "Online payment", "complexity": "HIGH", "risk": 5,
        "why": "Payment requires verified pricing, provider configuration, security, and reconciliation.",
        "benefit": "Can reduce payment friction after the business has a governed billing workflow.",
        "dimensions": (3, 2, 3, 3, 1),
    },
}


PROFILE_RELEVANCE = {
    "FIELD_ESTIMATE": {
        "PHONE_CONTACT": "CORE", "GENERAL_CONTACT_FORM": "USEFUL", "ESTIMATE_REQUEST": "CORE",
        "PHOTO_UPLOAD": "CORE", "SCHEDULING_REQUEST": "USEFUL", "LIVE_BOOKING": "NOT_RELEVANT",
        "AFTER_HOURS_INTAKE": "CORE", "URGENT_REQUEST_ROUTING": "USEFUL", "FAQ": "USEFUL",
        "REVIEW_DISPLAY": "USEFUL", "SERVICE_AREA_QUALIFICATION": "USEFUL",
        "FINANCING_CTA": "CONDITIONAL", "LEAD_ACKNOWLEDGMENT": "USEFUL",
        "CUSTOMER_PORTAL": "NOT_RELEVANT", "PAYMENT": "NOT_RELEVANT",
    },
    "APPOINTMENT_SERVICE": {
        "PHONE_CONTACT": "USEFUL", "GENERAL_CONTACT_FORM": "USEFUL", "ESTIMATE_REQUEST": "NOT_RELEVANT",
        "PHOTO_UPLOAD": "NOT_RELEVANT", "SCHEDULING_REQUEST": "CORE", "LIVE_BOOKING": "CORE",
        "AFTER_HOURS_INTAKE": "USEFUL", "URGENT_REQUEST_ROUTING": "NOT_RELEVANT", "FAQ": "USEFUL",
        "REVIEW_DISPLAY": "CORE", "SERVICE_AREA_QUALIFICATION": "CONDITIONAL",
        "FINANCING_CTA": "NOT_RELEVANT", "LEAD_ACKNOWLEDGMENT": "USEFUL",
        "CUSTOMER_PORTAL": "CONDITIONAL", "PAYMENT": "CONDITIONAL",
    },
    "CONSULTATION": {
        "PHONE_CONTACT": "USEFUL", "GENERAL_CONTACT_FORM": "CORE", "ESTIMATE_REQUEST": "NOT_RELEVANT",
        "PHOTO_UPLOAD": "NOT_RELEVANT", "SCHEDULING_REQUEST": "CORE", "LIVE_BOOKING": "CONDITIONAL",
        "AFTER_HOURS_INTAKE": "USEFUL", "URGENT_REQUEST_ROUTING": "NOT_RELEVANT", "FAQ": "USEFUL",
        "REVIEW_DISPLAY": "USEFUL", "SERVICE_AREA_QUALIFICATION": "NOT_RELEVANT",
        "FINANCING_CTA": "NOT_RELEVANT", "LEAD_ACKNOWLEDGMENT": "USEFUL",
        "CUSTOMER_PORTAL": "NOT_RELEVANT", "PAYMENT": "NOT_RELEVANT",
    },
    "GENERAL": {
        "PHONE_CONTACT": "CORE", "GENERAL_CONTACT_FORM": "CORE", "ESTIMATE_REQUEST": "CONDITIONAL",
        "PHOTO_UPLOAD": "CONDITIONAL", "SCHEDULING_REQUEST": "CONDITIONAL", "LIVE_BOOKING": "CONDITIONAL",
        "AFTER_HOURS_INTAKE": "USEFUL", "URGENT_REQUEST_ROUTING": "CONDITIONAL", "FAQ": "USEFUL",
        "REVIEW_DISPLAY": "USEFUL", "SERVICE_AREA_QUALIFICATION": "CONDITIONAL",
        "FINANCING_CTA": "CONDITIONAL", "LEAD_ACKNOWLEDGMENT": "USEFUL",
        "CUSTOMER_PORTAL": "NOT_RELEVANT", "PAYMENT": "CONDITIONAL",
    },
}


CLAIM_LABELS = {
    "BUSINESS_NAME": "Business name",
    "INDUSTRY": "Industry",
    "LOCATION": "Primary location",
    "WEBSITE_URL": "Current website",
    "CONTACT_PHONE": "Public phone",
    "CONTACT_EMAIL": "Public email",
    "SERVICE_CANDIDATES": "Services found on the site",
    "BUSINESS_HOURS": "Business hours",
    "SERVICE_AREA": "Service area",
    "MEDIA_RIGHTS": "Rights to existing website media",
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _clean(value, limit=800):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _json(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def ensure_upgrade_schema(conn):
    ensure_intelligence_schema(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS truth_resolution_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            intelligence_run_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'COMPLETED',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (intelligence_run_id) REFERENCES site_intelligence_runs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_truth_runs_business
            ON truth_resolution_runs(business_id, id DESC);

        CREATE TABLE IF NOT EXISTS business_truth_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resolution_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            claim_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            display_value TEXT NOT NULL DEFAULT '',
            normalized_value TEXT NOT NULL DEFAULT '',
            truth_state TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'low',
            requires_owner_verification INTEGER NOT NULL DEFAULT 1,
            rationale TEXT NOT NULL DEFAULT '',
            conflict_detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (resolution_id) REFERENCES truth_resolution_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE(resolution_id, claim_key)
        );
        CREATE INDEX IF NOT EXISTS idx_truth_claims_business
            ON business_truth_claims(business_id, resolution_id, claim_key);

        CREATE TABLE IF NOT EXISTS truth_claim_sources (
            claim_id INTEGER NOT NULL,
            evidence_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            PRIMARY KEY (claim_id, evidence_id),
            FOREIGN KEY (claim_id) REFERENCES business_truth_claims(id) ON DELETE CASCADE,
            FOREIGN KEY (evidence_id) REFERENCES site_intelligence_evidence(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS owner_truth_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            claim_key TEXT NOT NULL,
            decision TEXT NOT NULL,
            confirmed_value TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            recorded_by TEXT NOT NULL DEFAULT 'OPERATOR_RECORDED_OWNER',
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_owner_truth_latest
            ON owner_truth_verifications(business_id, claim_key, id DESC);

        CREATE TABLE IF NOT EXISTS upgrade_blueprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            intelligence_run_id INTEGER NOT NULL,
            resolution_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            industry_profile TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'READY',
            verification_revision INTEGER NOT NULL DEFAULT 0,
            generated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (intelligence_run_id) REFERENCES site_intelligence_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (resolution_id) REFERENCES truth_resolution_runs(id) ON DELETE CASCADE,
            UNIQUE(business_id, version_number)
        );
        CREATE INDEX IF NOT EXISTS idx_blueprints_business
            ON upgrade_blueprints(business_id, id DESC);

        CREATE TABLE IF NOT EXISTS capability_gap_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blueprint_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            capability_key TEXT NOT NULL,
            label TEXT NOT NULL,
            observed_state TEXT NOT NULL,
            observation_confidence TEXT NOT NULL,
            relevance TEXT NOT NULL,
            gap_state TEXT NOT NULL,
            recommended_action TEXT NOT NULL,
            rationale TEXT NOT NULL,
            expected_benefit TEXT NOT NULL,
            complexity TEXT NOT NULL,
            operational_risk INTEGER NOT NULL DEFAULT 1,
            priority_score INTEGER NOT NULL DEFAULT 0,
            priority_band TEXT NOT NULL DEFAULT 'LOW',
            evidence_summary TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            owner_verification_required INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (blueprint_id) REFERENCES upgrade_blueprints(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE(blueprint_id, capability_key)
        );
        CREATE INDEX IF NOT EXISTS idx_capability_gaps_blueprint
            ON capability_gap_assessments(blueprint_id, priority_score DESC);

        CREATE TABLE IF NOT EXISTS upgrade_blueprint_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blueprint_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            title TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            why_it_matters TEXT NOT NULL,
            expected_benefit TEXT NOT NULL,
            confidence TEXT NOT NULL,
            complexity TEXT NOT NULL,
            priority_score INTEGER NOT NULL DEFAULT 0,
            priority_band TEXT NOT NULL DEFAULT 'LOW',
            owner_verification_required INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (blueprint_id) REFERENCES upgrade_blueprints(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_blueprint_items
            ON upgrade_blueprint_items(blueprint_id, action, priority_score DESC, id);
        """
    )


def _business(conn, business_id):
    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if row is None:
        raise LookupError("Business not found.")
    return dict(row)


def _latest_completed_run(conn, business_id):
    return conn.execute(
        "SELECT * FROM site_intelligence_runs WHERE business_id=? AND status='COMPLETED' "
        "ORDER BY id DESC LIMIT 1", (business_id,),
    ).fetchone()


def _latest_verifications(conn, business_id):
    rows = conn.execute(
        """
        SELECT v.* FROM owner_truth_verifications v
        JOIN (
            SELECT claim_key, MAX(id) AS max_id
            FROM owner_truth_verifications WHERE business_id=? GROUP BY claim_key
        ) latest ON latest.max_id=v.id
        WHERE v.business_id=?
        """, (business_id, business_id),
    ).fetchall()
    return {row["claim_key"]: dict(row) for row in rows}


def _profile_for(category):
    value = _clean(category, 160).lower()
    if any(token in value for token in (
        "tree", "roof", "hvac", "heating", "cooling", "plumb", "electric",
        "landscap", "lawn", "pest", "remodel", "contract", "cleaning",
        "moving", "garage", "masonry", "painting", "flooring", "restoration",
    )):
        return "FIELD_ESTIMATE"
    if any(token in value for token in (
        "salon", "spa", "barber", "beauty", "massage", "fitness", "trainer",
        "therapy", "chiropr", "dental", "dentist", "photograph",
    )):
        return "APPOINTMENT_SERVICE"
    if any(token in value for token in ("law", "legal", "account", "consult", "insurance", "financial")):
        return "CONSULTATION"
    return "GENERAL"


def _normalize_phone(value):
    raw = _clean(value, 80)
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or raw.lower()


def _unique_evidence(rows, kind, normalizer=None):
    matches = [dict(row) for row in rows if row["evidence_type"] == kind and _clean(row["normalized_value"])]
    grouped = defaultdict(list)
    for row in matches:
        key = (normalizer or (lambda v: _clean(v).lower()))(row["normalized_value"])
        if key:
            grouped[key].append(row)
    return grouped


def _service_candidates(evidence):
    stop = {
        "home", "about", "about us", "contact", "contact us", "services", "our services",
        "reviews", "testimonials", "gallery", "frequently asked questions", "faq",
        "request an estimate", "get a quote", "why choose us", "areas we serve",
    }
    values = []
    for row in evidence:
        if row["evidence_type"] != "HEADING":
            continue
        value = _clean(row["normalized_value"], 120)
        key = value.lower().strip(" .:-")
        if not value or key in stop or len(value.split()) > 9 or len(value) < 3:
            continue
        if value not in values:
            values.append(value)
        if len(values) >= 12:
            break
    return values


def _public_claims(business, run, evidence, assets):
    claims = []

    def add(key, value, state, confidence, rationale, verify=True, sources=None, conflict=""):
        claims.append({
            "key": key, "label": CLAIM_LABELS[key], "value": _clean(value),
            "normalized": _clean(value).lower(), "state": state, "confidence": confidence,
            "verify": bool(verify), "rationale": rationale, "sources": sources or [],
            "conflict": conflict,
        })

    add("BUSINESS_NAME", business.get("name"), "INFERRED", "medium",
        "Name comes from the prospect record and has not been confirmed by the owner.")
    add("INDUSTRY", business.get("category"), "INFERRED", "medium",
        "Industry comes from prospect research and controls capability relevance.")
    location = business.get("address") or business.get("city") or ""
    add("LOCATION", location, "INFERRED" if location else "UNKNOWN", "medium" if location else "low",
        "Location is a prospect-research input, not production truth." if location else "No primary location was observed.")
    add("WEBSITE_URL", run["canonical_url"], "PUBLIC_OBSERVED", "high",
        "Canonical public URL reached by the bounded crawler.", verify=False)

    for key, kind, fallback, normalizer in (
        ("CONTACT_PHONE", "CONTACT_PHONE", business.get("phone"), _normalize_phone),
        ("CONTACT_EMAIL", "CONTACT_EMAIL", business.get("email"), lambda v: _clean(v).lower()),
    ):
        groups = _unique_evidence(evidence, kind, normalizer)
        if len(groups) == 1:
            matched = next(iter(groups.values()))
            value = matched[0]["normalized_value"]
            add(key, value, "PUBLIC_OBSERVED", "high" if len(matched) > 1 else "medium",
                f"One public value was observed across {len(matched)} website signal(s).",
                sources=[row["id"] for row in matched])
        elif len(groups) > 1:
            matched = [row for group in groups.values() for row in group]
            values = [group[0]["normalized_value"] for group in groups.values()]
            add(key, " · ".join(values), "CONFLICT", "low",
                "Multiple public values were observed. Business OS will not choose one automatically.",
                sources=[row["id"] for row in matched],
                conflict="Conflicting public values: " + " | ".join(values))
        elif _clean(fallback):
            add(key, fallback, "INFERRED", "low",
                "Value exists in the prospect record but was not confirmed by the latest website analysis.")
        else:
            add(key, "", "UNKNOWN", "low", "No value was observed in the latest website analysis.")

    services = _service_candidates(evidence)
    add("SERVICE_CANDIDATES", ", ".join(services), "INFERRED" if services else "UNKNOWN",
        "low", "Headings can suggest services but cannot prove the owner currently offers them.")
    add("BUSINESS_HOURS", "", "UNKNOWN", "low",
        "Static page analysis did not produce a reliable, structured hours claim.")
    add("SERVICE_AREA", "", "UNKNOWN", "low",
        "Static page analysis did not produce a reliable, structured service-area claim.")
    media_count = len(assets)
    add("MEDIA_RIGHTS", f"{media_count} discovered reference asset(s)" if media_count else "",
        "UNKNOWN", "low", "Public visibility does not prove permission to reuse images, logos, or other media.")
    return claims


def _apply_verifications(claims, decisions):
    for claim in claims:
        decision = decisions.get(claim["key"])
        if not decision:
            continue
        if decision["decision"] == "CONFIRMED":
            public_value = claim["value"]
            confirmed = _clean(decision["confirmed_value"])
            differs = bool(public_value and confirmed.lower() != public_value.lower())
            claim.update({
                "value": confirmed,
                "normalized": confirmed.lower(),
                "state": "OWNER_CONFIRMED",
                "confidence": "owner_verified",
                "verify": False,
                "rationale": "Owner confirmation was recorded by the operator.",
                "conflict": ("Owner-confirmed value differs from public observation: " + public_value) if differs else "",
            })
        elif decision["decision"] == "REJECTED":
            claim.update({
                "value": "",
                "normalized": "",
                "state": "UNKNOWN",
                "confidence": "low",
                "verify": True,
                "rationale": "The owner rejected the observed value; a replacement has not been confirmed.",
                "conflict": "Rejected public observation: " + claim["value"] if claim["value"] else "",
            })
    return claims


def _insert_claims(conn, resolution_id, business_id, claims):
    ts = _now()
    stored = []
    for claim in claims:
        if claim["state"] not in TRUTH_STATES:
            raise ValueError("Unsupported truth state.")
        cur = conn.execute(
            """
            INSERT INTO business_truth_claims(
                resolution_id,business_id,claim_key,display_name,display_value,normalized_value,
                truth_state,confidence,requires_owner_verification,rationale,conflict_detail,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (resolution_id, business_id, claim["key"], claim["label"], claim["value"],
             claim["normalized"], claim["state"], claim["confidence"], int(claim["verify"]),
             claim["rationale"], claim["conflict"], ts),
        )
        claim["id"] = cur.lastrowid
        for evidence_id in claim["sources"]:
            conn.execute(
                "INSERT INTO truth_claim_sources(claim_id,evidence_id,business_id) VALUES (?,?,?)",
                (cur.lastrowid, evidence_id, business_id),
            )
        stored.append(claim)
    return stored


def _priority(catalog, relevance, confidence):
    customer, conversion, operations, trust, urgency = catalog["dimensions"]
    confidence_points = CONFIDENCE_RANK.get(confidence, 1) * 2
    relevance_points = {"CORE": 8, "USEFUL": 4, "CONDITIONAL": 0, "NOT_RELEVANT": -15}[relevance]
    raw = (
        customer * 3 + conversion * 3 + operations * 2 + trust * 2 + urgency
        + confidence_points + relevance_points
        - COMPLEXITY_RANK[catalog["complexity"]] * 2 - catalog["risk"] * 2
    )
    score = max(0, min(100, int(raw * 1.45)))
    band = "HIGH" if score >= 58 else "MEDIUM" if score >= 38 else "LOW"
    return score, band


def _gap_assessments(conn, run, business, profile):
    rows = conn.execute(
        "SELECT * FROM site_capability_observations WHERE run_id=? ORDER BY capability_key",
        (run["id"],),
    ).fetchall()
    observed = {row["capability_key"]: dict(row) for row in rows}
    output = []
    for key in CAPABILITIES:
        catalog = CAPABILITY_CATALOG[key]
        observation = observed.get(key, {
            "observed_state": "UNKNOWN", "confidence": "low", "evidence_count": 0,
            "rationale": "No capability observation is available.",
        })
        relevance = PROFILE_RELEVANCE[profile].get(key, "CONDITIONAL")
        observed_state = observation["observed_state"]
        owner_verify = False

        if observed_state == "PRESENT":
            gap_state, action = "PRESENT", "KEEP"
        elif relevance == "NOT_RELEVANT":
            gap_state, action = "NOT_RELEVANT", "IGNORE"
        elif key in {"LIVE_BOOKING", "PAYMENT", "CUSTOMER_PORTAL"} and observed_state != "PRESENT":
            gap_state, action = "BLOCKED", "IGNORE"
        elif observed_state == "UNKNOWN" or relevance == "CONDITIONAL":
            gap_state, action, owner_verify = "VERIFY", "VERIFY", True
        else:
            gap_state, action = "RECOMMENDED", "ADD"

        score, band = _priority(catalog, relevance, observation["confidence"])
        evidence_summary = _clean(observation["rationale"], 500)
        output.append({
            "key": key, "label": catalog["label"], "observed_state": observed_state,
            "confidence": observation["confidence"], "relevance": relevance,
            "gap_state": gap_state, "action": action, "rationale": catalog["why"],
            "benefit": catalog["benefit"], "complexity": catalog["complexity"],
            "risk": catalog["risk"], "score": score, "band": band,
            "evidence_summary": evidence_summary,
            "source_url": run["canonical_url"], "verify": owner_verify,
        })
    return output


def _improvement_items(gaps, run):
    by_key = {gap["key"]: gap for gap in gaps}
    output = []

    def improve(subject, title, evidence, why, benefit, complexity="MEDIUM", score=55, band="MEDIUM"):
        output.append({
            "action": "IMPROVE", "subject": subject, "title": title,
            "evidence": evidence, "source_url": run["canonical_url"], "why": why,
            "benefit": benefit, "confidence": "medium", "complexity": complexity,
            "score": score, "band": band, "verify": False,
        })

    generic = by_key["GENERAL_CONTACT_FORM"]
    estimate = by_key["ESTIMATE_REQUEST"]
    if generic["observed_state"] == "PRESENT" and estimate["observed_state"] != "PRESENT" and estimate["relevance"] == "CORE":
        improve(
            "CONTACT_TO_ESTIMATE", "Turn the generic form into a useful estimate path",
            f"A general form is present, but a structured estimate request was {estimate['observed_state'].lower().replace('_', ' ')}.",
            "A name-and-message form does not collect the scope details an estimate-driven business needs.",
            "Collects service, location, urgency, timing, and job context before owner review.",
            score=72, band="HIGH",
        )
    scheduling = by_key["SCHEDULING_REQUEST"]
    live = by_key["LIVE_BOOKING"]
    if live["observed_state"] == "PRESENT" and scheduling["relevance"] != "NOT_RELEVANT":
        improve(
            "BOOKING_GOVERNANCE", "Verify the live booking promise and fallback path",
            "A live booking capability was detected on the public site.",
            "Instant availability can create operational problems if duration, service area, or calendar rules are stale.",
            "Preserves convenient booking while making exceptions and ownership clear.",
            score=58, band="HIGH",
        )
    reviews = by_key["REVIEW_DISPLAY"]
    if reviews["observed_state"] == "PRESENT":
        improve(
            "REVIEW_PROVENANCE", "Keep the proof, verify the source",
            reviews["evidence_summary"],
            "Review language is useful only when the source, wording, and permission are defensible.",
            "Retains existing trust without turning public evidence into an unsupported production claim.",
            complexity="LOW", score=48, band="MEDIUM",
        )
    return output


def _select_blueprint_items(gaps, claims, run):
    items = []
    action_limits = {"KEEP": 6, "ADD": 3, "VERIFY": 5, "IGNORE": 4}
    for action in ("KEEP", "ADD", "VERIFY", "IGNORE"):
        candidates = [gap for gap in gaps if gap["action"] == action]
        candidates.sort(key=lambda row: (-row["score"], row["label"]))
        for gap in candidates[:action_limits[action]]:
            title_prefix = {"KEEP": "Keep", "ADD": "Add", "VERIFY": "Verify", "IGNORE": "Do not prioritize"}[action]
            items.append({
                "action": action, "subject": gap["key"],
                "title": f"{title_prefix} {gap['label'].lower()}",
                "evidence": gap["evidence_summary"], "source_url": gap["source_url"],
                "why": gap["rationale"], "benefit": gap["benefit"],
                "confidence": gap["confidence"], "complexity": gap["complexity"],
                "score": gap["score"], "band": gap["band"], "verify": gap["verify"],
            })

    items.extend(_improvement_items(gaps, run))
    capability_verify_keys = {item["subject"] for item in items if item["action"] == "VERIFY"}
    truth_candidates = [
        claim for claim in claims
        if claim["verify"] and claim["key"] not in capability_verify_keys
        and claim["key"] != "MEDIA_RIGHTS"
    ]
    truth_candidates.sort(key=lambda row: (row["state"] != "CONFLICT", row["label"]))
    existing_verify_count = sum(item["action"] == "VERIFY" for item in items)
    for claim in truth_candidates[:max(0, 7 - existing_verify_count)]:
        items.append({
            "action": "VERIFY", "subject": "TRUTH:" + claim["key"],
            "title": "Confirm " + claim["label"].lower(),
            "evidence": claim["conflict"] or claim["rationale"],
            "source_url": run["canonical_url"],
            "why": "Production copy and customer handling must use owner-confirmed business facts.",
            "benefit": "Prevents public research or inference from silently becoming a business promise.",
            "confidence": claim["confidence"], "complexity": "LOW",
            "score": 66 if claim["state"] == "CONFLICT" else 42,
            "band": "HIGH" if claim["state"] == "CONFLICT" else "MEDIUM", "verify": True,
        })
    return items


def build_upgrade_blueprint(conn, business_id):
    """Create immutable resolution and blueprint records from the latest completed crawl."""
    ensure_upgrade_schema(conn)
    business = _business(conn, business_id)
    run = _latest_completed_run(conn, business_id)
    if run is None:
        raise ValueError("Analyze the current website before building an Upgrade Blueprint.")
    evidence = conn.execute(
        "SELECT * FROM site_intelligence_evidence WHERE run_id=? AND business_id=? ORDER BY id",
        (run["id"], business_id),
    ).fetchall()
    assets = conn.execute(
        "SELECT * FROM site_asset_observations WHERE run_id=? AND business_id=? ORDER BY id",
        (run["id"], business_id),
    ).fetchall()
    decisions = _latest_verifications(conn, business_id)
    claims = _apply_verifications(_public_claims(business, run, evidence, assets), decisions)
    profile = _profile_for(business.get("category"))
    gaps = _gap_assessments(conn, run, business, profile)
    items = _select_blueprint_items(gaps, claims, run)
    ts = _now()
    version = conn.execute(
        "SELECT COALESCE(MAX(version_number),0)+1 FROM upgrade_blueprints WHERE business_id=?",
        (business_id,),
    ).fetchone()[0]
    revision = max((row["id"] for row in decisions.values()), default=0)

    with conn:
        resolution_id = conn.execute(
            "INSERT INTO truth_resolution_runs(business_id,intelligence_run_id,created_at) VALUES (?,?,?)",
            (business_id, run["id"], ts),
        ).lastrowid
        claims = _insert_claims(conn, resolution_id, business_id, claims)
        blueprint_id = conn.execute(
            """
            INSERT INTO upgrade_blueprints(
                business_id,intelligence_run_id,resolution_id,version_number,
                industry_profile,verification_revision,generated_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (business_id, run["id"], resolution_id, version, profile, revision, ts),
        ).lastrowid
        for gap in gaps:
            if gap["gap_state"] not in GAP_STATES or gap["action"] not in BLUEPRINT_ACTIONS:
                raise ValueError("Invalid capability assessment state.")
            conn.execute(
                """
                INSERT INTO capability_gap_assessments(
                    blueprint_id,business_id,capability_key,label,observed_state,
                    observation_confidence,relevance,gap_state,recommended_action,rationale,
                    expected_benefit,complexity,operational_risk,priority_score,priority_band,
                    evidence_summary,source_url,owner_verification_required,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (blueprint_id,business_id,gap["key"],gap["label"],gap["observed_state"],
                 gap["confidence"],gap["relevance"],gap["gap_state"],gap["action"],gap["rationale"],
                 gap["benefit"],gap["complexity"],gap["risk"],gap["score"],gap["band"],
                 gap["evidence_summary"],gap["source_url"],int(gap["verify"]),ts),
            )
        for item in items:
            conn.execute(
                """
                INSERT INTO upgrade_blueprint_items(
                    blueprint_id,business_id,action,subject_key,title,evidence_summary,source_url,
                    why_it_matters,expected_benefit,confidence,complexity,priority_score,
                    priority_band,owner_verification_required,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (blueprint_id,business_id,item["action"],item["subject"],item["title"],
                 item["evidence"],item["source_url"],item["why"],item["benefit"],
                 item["confidence"],item["complexity"],item["score"],item["band"],
                 int(item["verify"]),ts),
            )
    return upgrade_workspace_view(conn, business_id, blueprint_id=blueprint_id)


def record_owner_verification(conn, business_id, *, claim_key, decision, confirmed_value="", note=""):
    ensure_upgrade_schema(conn)
    _business(conn, business_id)
    claim_key = _clean(claim_key, 80).upper()
    decision = _clean(decision, 20).upper()
    confirmed_value = _clean(confirmed_value, 800)
    note = _clean(note, 500)
    if claim_key not in CLAIM_LABELS:
        raise ValueError("Unsupported Business Truth claim.")
    if decision not in DECISIONS:
        raise ValueError("Verification decision must be Confirmed or Rejected.")
    if decision == "CONFIRMED" and not confirmed_value:
        raise ValueError("Enter the value the owner confirmed.")
    if _latest_completed_run(conn, business_id) is None:
        raise ValueError("Website analysis is required before owner verification.")
    conn.execute(
        """
        INSERT INTO owner_truth_verifications(
            business_id,claim_key,decision,confirmed_value,note,created_at
        ) VALUES (?,?,?,?,?,?)
        """, (business_id, claim_key, decision, confirmed_value, note, _now()),
    )
    conn.commit()
    return build_upgrade_blueprint(conn, business_id)


def _source_urls_for_claims(conn, claim_ids):
    if not claim_ids:
        return {}
    placeholders = ",".join("?" for _ in claim_ids)
    rows = conn.execute(
        f"""
        SELECT s.claim_id,e.page_url FROM truth_claim_sources s
        JOIN site_intelligence_evidence e ON e.id=s.evidence_id AND e.business_id=s.business_id
        WHERE s.claim_id IN ({placeholders}) ORDER BY e.id
        """, tuple(claim_ids),
    ).fetchall()
    output = defaultdict(list)
    for row in rows:
        if row["page_url"] not in output[row["claim_id"]]:
            output[row["claim_id"]].append(row["page_url"])
    return output


def upgrade_workspace_view(conn, business_id, blueprint_id=None):
    ensure_upgrade_schema(conn)
    business = _business(conn, business_id)
    business["safe_website_url"] = safe_external_url(business.get("website"))
    run = _latest_completed_run(conn, business_id)
    if blueprint_id is None:
        blueprint = conn.execute(
            "SELECT * FROM upgrade_blueprints WHERE business_id=? ORDER BY id DESC LIMIT 1",
            (business_id,),
        ).fetchone()
    else:
        blueprint = conn.execute(
            "SELECT * FROM upgrade_blueprints WHERE id=? AND business_id=?",
            (blueprint_id, business_id),
        ).fetchone()
    latest_revision = conn.execute(
        "SELECT COALESCE(MAX(id),0) FROM owner_truth_verifications WHERE business_id=?",
        (business_id,),
    ).fetchone()[0]
    if not blueprint:
        return {
            "business": business, "run": dict(run) if run else None, "blueprint": None,
            "claims": [], "gaps": [], "items": {action: [] for action in BLUEPRINT_ACTIONS},
            "counts": {action: 0 for action in BLUEPRINT_ACTIONS}, "top_recommendation": None,
            "verification_queue": [], "stale": False, "history_count": 0,
        }
    bp = dict(blueprint)
    claims = [dict(row) for row in conn.execute(
        "SELECT * FROM business_truth_claims WHERE resolution_id=? AND business_id=? ORDER BY id",
        (bp["resolution_id"], business_id),
    ).fetchall()]
    urls = _source_urls_for_claims(conn, [row["id"] for row in claims])
    for claim in claims:
        claim["source_urls"] = urls.get(claim["id"], [])
    gaps = [dict(row) for row in conn.execute(
        "SELECT * FROM capability_gap_assessments WHERE blueprint_id=? AND business_id=? "
        "ORDER BY priority_score DESC,label", (bp["id"], business_id),
    ).fetchall()]
    item_rows = [dict(row) for row in conn.execute(
        "SELECT * FROM upgrade_blueprint_items WHERE blueprint_id=? AND business_id=? "
        "ORDER BY priority_score DESC,id", (bp["id"], business_id),
    ).fetchall()]
    items = {action: [] for action in BLUEPRINT_ACTIONS}
    for row in item_rows:
        items[row["action"]].append(row)
    counts = {action: len(items[action]) for action in BLUEPRINT_ACTIONS}
    actionable = [row for row in item_rows if row["action"] in {"ADD", "IMPROVE"}]
    top = max(actionable, key=lambda row: row["priority_score"], default=None)
    verification_queue = [claim for claim in claims if claim["requires_owner_verification"]]
    history_count = conn.execute(
        "SELECT COUNT(*) FROM upgrade_blueprints WHERE business_id=?", (business_id,),
    ).fetchone()[0]
    stale = bool(
        (run and bp["intelligence_run_id"] != run["id"])
        or bp["verification_revision"] != latest_revision
    )
    return {
        "business": business, "run": dict(run) if run else None, "blueprint": bp,
        "claims": claims, "gaps": gaps, "items": items, "counts": counts,
        "top_recommendation": top, "verification_queue": verification_queue,
        "stale": stale, "history_count": history_count,
    }


def safe_external_url(value):
    """Allow templates to link only to ordinary public HTTP(S) evidence URLs."""
    value = _clean(value, 2048)
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""
