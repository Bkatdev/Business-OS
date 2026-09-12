"""Business OS v14 - founder sales workspace and safe prospect conversion.

This module keeps sales execution deterministic and auditable. Public prospect
facts remain public/unverified until the founder explicitly records owner-
verified values during conversion. Conversion enters ONBOARDING only; it never
activates automation or live provider actions.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from services.db import now_iso
from services.platform_foundation import record_evidence
from services.product_foundation import ensure_product_schema
from services.business_config import ensure_business_config_schema, get_or_create_default_schema
from services.v13_sales import build_sales_brief

INTERACTION_TYPES = {
    "OUTREACH": "Outreach sent",
    "REPLY": "Owner replied",
    "DEMO": "Demo / concept reviewed",
    "PROPOSAL": "Proposal discussed",
    "NOTE": "Sales note",
    "AGREEMENT": "Owner agreed to start onboarding",
    "LOST": "Opportunity closed lost",
}
CHANNELS = {
    "EMAIL": "Email",
    "SMS": "Text",
    "PHONE": "Phone",
    "IN_PERSON": "In person",
    "OTHER": "Other",
}
FOLLOW_UP_STATES = {"OPEN", "DONE", "CANCELLED"}


def ensure_sales_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sales_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'OTHER',
            summary TEXT NOT NULL DEFAULT '',
            pipeline_status TEXT NOT NULL DEFAULT '',
            occurred_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sales_interactions_business
            ON sales_interactions(business_id, occurred_at DESC, id DESC);

        CREATE TABLE IF NOT EXISTS sales_followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            due_at TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sales_followups_due
            ON sales_followups(status, due_at, business_id);

        CREATE TABLE IF NOT EXISTS prospect_conversion_records (
            business_id INTEGER PRIMARY KEY,
            owner_name TEXT NOT NULL DEFAULT '',
            verified_business_name TEXT NOT NULL DEFAULT '',
            verified_industry TEXT NOT NULL DEFAULT '',
            verified_phone TEXT NOT NULL DEFAULT '',
            verified_email TEXT NOT NULL DEFAULT '',
            services TEXT NOT NULL DEFAULT '',
            business_hours TEXT NOT NULL DEFAULT '',
            service_area TEXT NOT NULL DEFAULT '',
            emergency_rules TEXT NOT NULL DEFAULT '',
            escalation_instructions TEXT NOT NULL DEFAULT '',
            scheduling_policy TEXT NOT NULL DEFAULT '',
            messaging_tone TEXT NOT NULL DEFAULT 'Professional, warm, concise',
            onboarding_notes TEXT NOT NULL DEFAULT '',
            verification_status TEXT NOT NULL DEFAULT 'DRAFT',
            verified_at TEXT NOT NULL DEFAULT '',
            converted_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        """
    )


def _business(conn, business_id: int):
    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if row is None:
        raise LookupError("Business not found")
    return row


def _concepts(conn, business_id: int):
    return conn.execute(
        "SELECT * FROM website_concepts WHERE business_id=? ORDER BY concept_number DESC, id DESC",
        (business_id,),
    ).fetchall()


def _active_followup(conn, business_id: int):
    return conn.execute(
        """
        SELECT * FROM sales_followups
        WHERE business_id=? AND status='OPEN'
        ORDER BY due_at ASC, id ASC LIMIT 1
        """,
        (business_id,),
    ).fetchone()


def _safe_city_phrase(business: dict) -> str:
    city = (business.get("city") or "").strip()
    return f" in {city}" if city else ""


def _safe_http_url(value: str) -> str:
    value = (value or "").strip()[:2048]
    if not value:
        return ""
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    if (parsed.scheme or "").lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return value


def build_outreach_drafts(business: dict, *, concept_count: int) -> dict:
    """Create deterministic drafts from known prospect identity only.

    Drafts intentionally avoid claiming ROI, missed revenue, or unsupported
    website defects. When a concept exists, the draft accurately says one was
    built. Nothing is sent by this function.
    """
    name = (business.get("name") or "this business").strip()
    category = (business.get("category") or "local service").strip().lower()
    city_phrase = _safe_city_phrase(business)

    if concept_count > 0:
        email_subject = f"Private website concept for {name}"
        email_body = (
            f"Hi — I came across {name} while researching {category} businesses{city_phrase}. "
            "I took a look at the public website and built a private website concept so you can react to something concrete. "
            "Nothing on your current website has been changed. Would you be open to seeing it?\n\n"
            "— Ben, Business OS"
        )
        text_body = (
            f"Hi — this is Ben from Business OS. I came across {name} and built a private website concept for the business. "
            "I haven't changed anything on your current site. Would you be open to seeing it?"
        )
        call_opener = (
            f"Hi, this is Ben from Business OS. I came across {name} and built a private website concept for the business. "
            "Nothing has been changed on your current website — I wanted to see if you'd be open to taking a quick look at what I made."
        )
    else:
        email_subject = f"Website idea for {name}"
        email_body = (
            f"Hi — I came across {name} while researching {category} businesses{city_phrase}. "
            "I took a look at the public website and have a few ideas for making the customer inquiry path clearer. "
            "I haven't changed anything on your site. Would you be open to seeing a private concept?\n\n"
            "— Ben, Business OS"
        )
        text_body = (
            f"Hi — this is Ben from Business OS. I came across {name} and have a few website ideas I'd like to show you privately. "
            "Would you be open to seeing a concept?"
        )
        call_opener = (
            f"Hi, this is Ben from Business OS. I came across {name} and had a few ideas for the website and inquiry experience. "
            "Would you be open to seeing a private concept before talking about anything further?"
        )

    return {
        "email_subject": email_subject,
        "email_body": email_body,
        "text_body": text_body,
        "call_opener": call_opener,
    }


def build_sales_workspace(conn, business_id: int) -> dict:
    ensure_sales_schema(conn)
    ensure_product_schema(conn)
    business_row = _business(conn, business_id)
    business = dict(business_row)
    concepts = _concepts(conn, business_id)
    interactions = conn.execute(
        """
        SELECT * FROM sales_interactions
        WHERE business_id=? ORDER BY occurred_at DESC, id DESC LIMIT 50
        """,
        (business_id,),
    ).fetchall()
    followups = conn.execute(
        """
        SELECT * FROM sales_followups
        WHERE business_id=? ORDER BY CASE status WHEN 'OPEN' THEN 0 ELSE 1 END, due_at ASC, id DESC
        LIMIT 50
        """,
        (business_id,),
    ).fetchall()
    conversion = conn.execute(
        "SELECT * FROM prospect_conversion_records WHERE business_id=?",
        (business_id,),
    ).fetchone()
    sales = build_sales_brief(business_row)
    drafts = build_outreach_drafts(business, concept_count=len(concepts))
    active_followup_row = _active_followup(conn, business_id)
    business["safe_website_url"] = _safe_http_url(business.get("website") or "")
    return {
        "business": business,
        "sales": sales,
        "concepts": [dict(c) for c in concepts],
        "concept_count": len(concepts),
        "drafts": drafts,
        "interactions": [dict(x) for x in interactions],
        "followups": [dict(x) for x in followups],
        "active_followup": dict(active_followup_row) if active_followup_row else None,
        "conversion": dict(conversion) if conversion else None,
        "interaction_types": INTERACTION_TYPES,
        "channels": CHANNELS,
    }


def log_sales_interaction(
    conn,
    *,
    business_id: int,
    interaction_type: str,
    channel: str = "OTHER",
    summary: str = "",
    follow_up_at: str = "",
    follow_up_reason: str = "",
):
    ensure_sales_schema(conn)
    business = _business(conn, business_id)
    interaction_type = (interaction_type or "").upper().strip()
    channel = (channel or "OTHER").upper().strip()
    if interaction_type not in INTERACTION_TYPES:
        raise ValueError("Unsupported sales interaction type")
    if channel not in CHANNELS:
        raise ValueError("Unsupported sales channel")
    summary = (summary or "").strip()[:2000]
    old_status = str(business["status"] or "Not Contacted")
    new_status = old_status
    if interaction_type == "OUTREACH":
        new_status = "Contacted"
    elif interaction_type == "DEMO":
        new_status = "Demo"
    elif interaction_type in {"PROPOSAL", "AGREEMENT"}:
        new_status = "Proposal"
    elif interaction_type == "LOST":
        new_status = "Lost"

    ts = now_iso()
    conn.execute(
        """
        INSERT INTO sales_interactions(
            business_id, interaction_type, channel, summary,
            pipeline_status, occurred_at, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (business_id, interaction_type, channel, summary, new_status, ts, ts),
    )
    if new_status != old_status:
        conn.execute("UPDATE businesses SET status=? WHERE id=?", (new_status, business_id))

    follow_up_at = (follow_up_at or "").strip()
    if follow_up_at:
        reason = (follow_up_reason or "Follow up on the latest sales conversation").strip()[:500]
        conn.execute(
            """
            INSERT INTO sales_followups(business_id,due_at,reason,status,created_at)
            VALUES (?,?,?,'OPEN',?)
            """,
            (business_id, follow_up_at, reason, ts),
        )
    conn.commit()
    return new_status


def complete_followup(conn, *, business_id: int, followup_id: int):
    ensure_sales_schema(conn)
    row = conn.execute(
        "SELECT * FROM sales_followups WHERE id=? AND business_id=?",
        (followup_id, business_id),
    ).fetchone()
    if row is None:
        raise LookupError("Follow-up not found for this prospect")
    if row["status"] != "OPEN":
        return False
    conn.execute(
        "UPDATE sales_followups SET status='DONE', completed_at=? WHERE id=? AND business_id=?",
        (now_iso(), followup_id, business_id),
    )
    conn.commit()
    return True


def save_conversion_draft(conn, *, business_id: int, values: dict):
    ensure_sales_schema(conn)
    _business(conn, business_id)
    existing = conn.execute(
        "SELECT verification_status FROM prospect_conversion_records WHERE business_id=?",
        (business_id,),
    ).fetchone()
    if existing and existing["verification_status"] == "CONVERTED":
        raise ValueError(
            "This prospect is already converted. Update production truth in Business Configuration instead."
        )
    allowed = (
        "owner_name",
        "verified_business_name",
        "verified_industry",
        "verified_phone",
        "verified_email",
        "services",
        "business_hours",
        "service_area",
        "emergency_rules",
        "escalation_instructions",
        "scheduling_policy",
        "messaging_tone",
        "onboarding_notes",
    )
    cleaned = {key: (values.get(key) or "").strip() for key in allowed}
    cleaned["messaging_tone"] = cleaned["messaging_tone"] or "Professional, warm, concise"
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO prospect_conversion_records(
            business_id, owner_name, verified_business_name, verified_industry,
            verified_phone, verified_email, services, business_hours, service_area,
            emergency_rules, escalation_instructions, scheduling_policy,
            messaging_tone, onboarding_notes, verification_status, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?)
        ON CONFLICT(business_id) DO UPDATE SET
            owner_name=excluded.owner_name,
            verified_business_name=excluded.verified_business_name,
            verified_industry=excluded.verified_industry,
            verified_phone=excluded.verified_phone,
            verified_email=excluded.verified_email,
            services=excluded.services,
            business_hours=excluded.business_hours,
            service_area=excluded.service_area,
            emergency_rules=excluded.emergency_rules,
            escalation_instructions=excluded.escalation_instructions,
            scheduling_policy=excluded.scheduling_policy,
            messaging_tone=excluded.messaging_tone,
            onboarding_notes=excluded.onboarding_notes,
            updated_at=excluded.updated_at
        """,
        (
            business_id,
            cleaned["owner_name"],
            cleaned["verified_business_name"],
            cleaned["verified_industry"],
            cleaned["verified_phone"],
            cleaned["verified_email"],
            cleaned["services"],
            cleaned["business_hours"],
            cleaned["service_area"],
            cleaned["emergency_rules"],
            cleaned["escalation_instructions"],
            cleaned["scheduling_policy"],
            cleaned["messaging_tone"],
            cleaned["onboarding_notes"],
            ts,
            ts,
        ),
    )
    conn.commit()

def conversion_readiness(record: dict | None) -> dict:
    record = record or {}
    checks = [
        ("business_name", bool((record.get("verified_business_name") or "").strip()), "Owner-confirmed business name"),
        ("industry", bool((record.get("verified_industry") or "").strip()), "Owner-confirmed industry"),
        ("contact", bool((record.get("verified_phone") or "").strip() or (record.get("verified_email") or "").strip()), "Owner-confirmed phone or email"),
        ("services", bool((record.get("services") or "").strip()), "Owner-confirmed services"),
        ("business_hours", bool((record.get("business_hours") or "").strip()), "Owner-confirmed business hours"),
        ("service_area", bool((record.get("service_area") or "").strip()), "Owner-confirmed service area"),
        ("emergency_rules", bool((record.get("emergency_rules") or "").strip()), "Emergency and safety rules"),
        ("escalation_instructions", bool((record.get("escalation_instructions") or "").strip()), "Escalation instructions"),
        ("scheduling_policy", bool((record.get("scheduling_policy") or "").strip()), "Scheduling policy"),
    ]
    missing = [label for _, ok, label in checks if not ok]
    return {"checks": checks, "missing": missing, "ready": not missing}


def _owner_verified_service_names(raw: str) -> list[str]:
    """Turn an owner-confirmed service list into bounded structured names.

    This is only used after the owner-verification gate. It does not parse
    public research or AI output into production truth.
    """
    import re
    names = []
    seen = set()
    for item in re.split(r"[\n,;]+", raw or ""):
        name = " ".join(item.strip().split())[:120]
        key = name.lower()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
        if len(names) >= 25:
            break
    return names


def convert_to_onboarding(conn, *, business_id: int):
    ensure_sales_schema(conn)
    ensure_product_schema(conn)
    business = _business(conn, business_id)
    row = conn.execute(
        "SELECT * FROM prospect_conversion_records WHERE business_id=?",
        (business_id,),
    ).fetchone()
    if row is None:
        return False, "Save owner-verified information before converting this prospect."
    record = dict(row)
    if record.get("verification_status") == "CONVERTED":
        return True, "This business is already in onboarding. Production truth should now be maintained in Business Configuration."
    if str(business["lifecycle_stage"] or "") == "ACTIVE":
        return False, "Active clients cannot be reconverted through the prospect workflow."
    readiness = conversion_readiness(record)
    if not readiness["ready"]:
        return False, "Conversion blocked. Missing: " + ", ".join(readiness["missing"])

    ts = now_iso()
    conn.execute(
        """
        INSERT INTO client_profiles(
            business_id, services, business_hours, service_area, emergency_rules,
            escalation_instructions, scheduling_policy, messaging_tone,
            onboarding_notes, updated_at, industry
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(business_id) DO UPDATE SET
            services=excluded.services,
            business_hours=excluded.business_hours,
            service_area=excluded.service_area,
            emergency_rules=excluded.emergency_rules,
            escalation_instructions=excluded.escalation_instructions,
            scheduling_policy=excluded.scheduling_policy,
            messaging_tone=excluded.messaging_tone,
            onboarding_notes=excluded.onboarding_notes,
            updated_at=excluded.updated_at,
            industry=excluded.industry
        """,
        (
            business_id, record["services"], record["business_hours"], record["service_area"],
            record["emergency_rules"], record["escalation_instructions"], record["scheduling_policy"],
            record["messaging_tone"], record["onboarding_notes"], ts, record["verified_industry"],
        ),
    )
    # Public values never silently become production truth; only the explicitly
    # owner-verified contact fields from the conversion record can replace them.
    conn.execute(
        """
        UPDATE businesses
        SET name=?, category=?, phone=?, email=?, status='Client', lifecycle_stage='ONBOARDING',
            automation_enabled=0, lifecycle_updated_at=?
        WHERE id=?
        """,
        (record["verified_business_name"], record["verified_industry"], record["verified_phone"], record["verified_email"], ts, business_id),
    )
    # The service list below is owner-verified at this point. Materialize it
    # into the structured catalog so Website Studio and public intake share the
    # same production truth rather than requiring a second copy/paste step.
    ensure_business_config_schema(conn)
    for order, service_name in enumerate(_owner_verified_service_names(record["services"]), start=1):
        conn.execute(
            """
            INSERT INTO business_services(
                business_id,name,description,active,public,bookable,requires_estimate,
                sort_order,created_at,updated_at
            ) VALUES (?,?,'',1,1,0,1,?,?,?)
            ON CONFLICT(business_id,name) DO UPDATE SET
                active=1, public=1, updated_at=excluded.updated_at
            """,
            (business_id, service_name, order * 10, ts, ts),
        )
    intake_schema = get_or_create_default_schema(conn, business_id)
    conn.execute(
        "UPDATE intake_schemas SET status='Active', updated_at=? WHERE id=?",
        (ts, intake_schema["id"]),
    )

    conn.execute(
        """
        UPDATE prospect_conversion_records
        SET verification_status='CONVERTED', verified_at=?, converted_at=?, updated_at=?
        WHERE business_id=?
        """,
        (ts, ts, ts, business_id),
    )

    for fact_type, summary in (
        ("business_name", record["verified_business_name"]),
        ("industry", record["verified_industry"]),
        ("phone", record["verified_phone"]),
        ("email", record["verified_email"]),
        ("services", record["services"]),
        ("business_hours", record["business_hours"]),
        ("service_area", record["service_area"]),
        ("emergency_rules", record["emergency_rules"]),
        ("escalation_instructions", record["escalation_instructions"]),
        ("scheduling_policy", record["scheduling_policy"]),
    ):
        if summary:
            record_evidence(
                conn,
                business_id=business_id,
                fact_type=fact_type,
                evidence_kind="OWNER_VERIFIED",
                source_provider="owner_confirmation",
                source_reference="v14_conversion",
                summary=summary,
                confidence="owner_verified",
                storage_policy="CANONICAL_PRODUCTION",
            )
    conn.commit()
    return True, "Prospect converted to ONBOARDING. Automation remains disabled until the existing readiness and activation gates pass."


def sales_pipeline_metrics(conn):
    ensure_sales_schema(conn)
    now_key = datetime.now().strftime("%Y-%m-%dT%H:%M")
    due = conn.execute(
        "SELECT COUNT(*) FROM sales_followups WHERE status='OPEN' AND due_at<=?",
        (now_key,),
    ).fetchone()[0]
    ready = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses b
        WHERE COALESCE(b.audit_status,'')='completed'
          AND COALESCE(b.status,'Not Contacted') IN ('Not Contacted','Researching','Qualified')
          AND EXISTS (SELECT 1 FROM website_concepts wc WHERE wc.business_id=b.id)
        """
    ).fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE status IN ('Contacted','Demo','Proposal')"
    ).fetchone()[0]
    onboarding = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE status='Client' AND COALESCE(lifecycle_stage,'ONBOARDING')='ONBOARDING'"
    ).fetchone()[0]
    return {
        "followups_due": int(due or 0),
        "ready_to_contact": int(ready or 0),
        "active_conversations": int(active or 0),
        "onboarding": int(onboarding or 0),
    }
