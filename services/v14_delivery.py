"""Business OS v14 customer-delivery loop.

This module creates an immutable *local delivery release* from an explicitly
reviewed Website Studio preview and accepts safe public-form test submissions
into the canonical lead model. It deliberately does not publish to an external
host, send messages, schedule appointments, or enable automation.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta

from services.db import now_iso
from services.platform_foundation import ensure_platform_schema, record_evidence
from services.v14_sales_workspace import ensure_sales_schema
from services.website_renderer import build_preview_render_model
from services.v14_production_site import production_model, selected_design
from services.website_studio import website_readiness

LOCAL_PROVIDER = "business_os_local_delivery"
MAX_ARTIFACT_BYTES = 250_000
MAX_TEXT = 4000
MAX_NAME = 160
MAX_PHONE = 80
MAX_EMAIL = 254
MAX_ADDRESS = 500
MAX_SERVICE = 200
NONCE_TTL_MINUTES = 90


def ensure_delivery_schema(conn):
    ensure_platform_schema(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS site_release_artifacts (
            deployment_id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            public_slug TEXT NOT NULL UNIQUE,
            artifact_json TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
            created_at TEXT NOT NULL,
            activated_at TEXT NOT NULL DEFAULT '',
            retired_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (deployment_id) REFERENCES site_deployments(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_site_release_artifacts_business
            ON site_release_artifacts(business_id, is_active, deployment_id DESC);

        CREATE TABLE IF NOT EXISTS public_form_nonces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deployment_id INTEGER NOT NULL,
            nonce_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (deployment_id) REFERENCES site_deployments(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_public_form_nonces_deployment
            ON public_form_nonces(deployment_id, expires_at);

        CREATE TABLE IF NOT EXISTS public_intake_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deployment_id INTEGER NOT NULL,
            business_id INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            lead_id INTEGER,
            reason TEXT NOT NULL DEFAULT '',
            submitted_name TEXT NOT NULL DEFAULT '',
            submitted_phone TEXT NOT NULL DEFAULT '',
            submitted_email TEXT NOT NULL DEFAULT '',
            submitted_service TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (deployment_id) REFERENCES site_deployments(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            UNIQUE(deployment_id, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_public_intake_business_created
            ON public_intake_submissions(business_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_public_intake_fingerprint
            ON public_intake_submissions(business_id, fingerprint, created_at DESC);
        """
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(value, limit):
    return str(value or "").replace("\x00", "").strip()[:limit]


def _valid_email(value: str) -> bool:
    if not value:
        return True
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)) and len(value) <= MAX_EMAIL


def _serialize_artifact(model: dict) -> tuple[str, str]:
    """Freeze only customer-facing, JSON-safe production state.

    The local release must render the same approved production design the operator
    reviewed. Internal design-row metadata is intentionally reduced to the safe
    blueprint + critic summary; no executable content is accepted.
    """
    design = model.get("design") or {}
    artifact = {
        "schema_version": 2,
        "artifact_kind": "PRODUCTION_SITE",
        "business_id": model["business_id"],
        "version": model["version"],
        "business": model["business"],
        "profile": model["profile"],
        "presentation": model["presentation"],
        "hero": model["hero"],
        "services": model["services"],
        "service_areas": model.get("service_areas") or [],
        "hours_lines": model.get("hours_lines") or [],
        "public_email": model.get("public_email") or "",
        "intake": model["intake"],
        "contact": model["contact"],
        "seo": model["seo"],
        "sections": model["sections"],
        "warnings": model["warnings"],
        "customer_ready": bool(model["customer_ready"]),
        "blueprint": model.get("blueprint") or {},
        "design": {
            "critic_score": design.get("critic_score"),
            "critic": design.get("critic") or [],
            "generation_mode": design.get("generation_mode") or "",
        },
    }
    raw = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    if len(raw.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise ValueError("Website artifact is unexpectedly large and was blocked.")
    return raw, _sha(raw)


def delivery_readiness(conn, business_id: int) -> dict:
    ensure_delivery_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if business is None:
        raise LookupError("Business not found")
    conversion = conn.execute(
        "SELECT * FROM prospect_conversion_records WHERE business_id=?", (business_id,)
    ).fetchone()
    website = website_readiness(conn, business_id)
    project = conn.execute(
        "SELECT * FROM website_projects WHERE business_id=?", (business_id,)
    ).fetchone()
    preview_id = project["preview_version_id"] if project else None
    design = selected_design(conn, business_id)
    design_matches = bool(design and preview_id and int(design["website_version_id"]) == int(preview_id))
    checks = [
        {"key": "onboarding", "label": "Client is in onboarding or active", "ok": (business["lifecycle_stage"] or "") in {"ONBOARDING", "ACTIVE"}},
        {"key": "owner_verified", "label": "Owner verification completed", "ok": bool(conversion and conversion["verification_status"] == "CONVERTED")},
        {"key": "website_truth", "label": "Website truth is customer-ready", "ok": bool(website["ready"])},
        {"key": "reviewed_preview", "label": "A reviewed preview version is selected", "ok": bool(preview_id)},
        {"key": "production_design", "label": "Production design matches the reviewed preview", "ok": design_matches},
    ]
    return {
        "ready": all(x["ok"] for x in checks),
        "checks": checks,
        "website": website,
        "preview_version_id": preview_id,
        "business": dict(business),
    }


def create_local_release(conn, business_id: int) -> dict:
    """Freeze the selected preview into an immutable local delivery artifact."""
    ensure_delivery_schema(conn)
    readiness = delivery_readiness(conn, business_id)
    if not readiness["ready"]:
        missing = [x["label"] for x in readiness["checks"] if not x["ok"]]
        raise ValueError("Delivery release blocked. Missing: " + ", ".join(missing))

    model = production_model(conn, business_id)
    if not model.get("customer_ready"):
        raise ValueError("Delivery release blocked by Website Studio safety warnings.")
    raw, checksum = _serialize_artifact(model)
    version_id = int(model["version"]["id"])

    existing = conn.execute(
        """
        SELECT d.*, a.public_slug, a.artifact_sha256, a.is_active
        FROM site_deployments d JOIN site_release_artifacts a ON a.deployment_id=d.id
        WHERE d.business_id=? AND d.website_version_id=? AND a.artifact_sha256=?
        ORDER BY d.id DESC LIMIT 1
        """,
        (business_id, version_id, checksum),
    ).fetchone()
    if existing:
        return dict(existing)

    ts = now_iso()
    slug = "site-" + secrets.token_urlsafe(12).replace("_", "-").replace("~", "-").lower()
    deployment_key = f"local:{business_id}:{version_id}:{checksum[:16]}"
    cur = conn.execute(
        """
        INSERT INTO site_deployments(
            business_id, website_version_id, provider, deployment_key, status,
            preview_reference, production_reference, requested_at, completed_at,
            created_at, updated_at
        ) VALUES (?,?,?,?,'ACTIVE',?,?,?, ?,?,?)
        """,
        (business_id, version_id, LOCAL_PROVIDER, deployment_key,
         f"/client/{business_id}/design/preview", f"/site/{slug}", ts, ts, ts, ts),
    )
    deployment_id = cur.lastrowid
    conn.execute(
        "UPDATE site_release_artifacts SET is_active=0, retired_at=? WHERE business_id=? AND is_active=1",
        (ts, business_id),
    )
    conn.execute(
        """
        INSERT INTO site_release_artifacts(
            deployment_id,business_id,public_slug,artifact_json,artifact_sha256,
            is_active,created_at,activated_at
        ) VALUES (?,?,?,?,?,1,?,?)
        """,
        (deployment_id, business_id, slug, raw, checksum, ts, ts),
    )
    # Keep deployment history coherent with the platform foundation.
    conn.execute(
        "UPDATE site_deployments SET status='ROLLED_BACK', updated_at=? WHERE business_id=? AND id<>? AND status='ACTIVE'",
        (ts, business_id, deployment_id),
    )
    record_evidence(
        conn,
        business_id=business_id,
        fact_type="website_release",
        evidence_kind="SYSTEM_MEASURED",
        source_provider=LOCAL_PROVIDER,
        source_reference=deployment_key,
        summary=f"Reviewed production design for Website Studio version {model['version']['number']} frozen as local delivery artifact {checksum[:12]}.",
        confidence="deterministic",
        storage_policy="SYSTEM_LEDGER",
        entity_type="site_deployment",
        entity_id=deployment_id,
    )
    conn.commit()
    return dict(conn.execute(
        "SELECT d.*, a.public_slug, a.artifact_sha256, a.is_active FROM site_deployments d JOIN site_release_artifacts a ON a.deployment_id=d.id WHERE d.id=?",
        (deployment_id,),
    ).fetchone())


def list_releases(conn, business_id: int):
    ensure_delivery_schema(conn)
    return [dict(r) for r in conn.execute(
        """
        SELECT d.*, a.public_slug, a.artifact_sha256, a.is_active, a.activated_at, a.retired_at
        FROM site_deployments d JOIN site_release_artifacts a ON a.deployment_id=d.id
        WHERE d.business_id=? ORDER BY d.id DESC
        """,
        (business_id,),
    ).fetchall()]


def active_release_for_business(conn, business_id: int):
    """Return the active local release for one tenant, including its frozen artifact."""
    ensure_delivery_schema(conn)
    row = conn.execute(
        """
        SELECT d.*, a.public_slug, a.artifact_json, a.artifact_sha256, a.is_active
        FROM site_release_artifacts a JOIN site_deployments d ON d.id=a.deployment_id
        WHERE d.business_id=? AND a.is_active=1 AND d.status='ACTIVE'
        ORDER BY d.id DESC LIMIT 1
        """,
        (business_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["artifact"] = json.loads(row["artifact_json"])
    return result


def active_release_by_slug(conn, slug: str):
    ensure_delivery_schema(conn)
    slug = _clean(slug, 120)
    row = conn.execute(
        """
        SELECT d.*, a.public_slug, a.artifact_json, a.artifact_sha256, a.is_active
        FROM site_release_artifacts a JOIN site_deployments d ON d.id=a.deployment_id
        WHERE a.public_slug=? AND a.is_active=1 AND d.status='ACTIVE'
        """,
        (slug,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["artifact"] = json.loads(row["artifact_json"])
    return result


def issue_form_nonce(conn, deployment_id: int) -> str:
    ensure_delivery_schema(conn)
    token = secrets.token_urlsafe(24)
    created = datetime.now()
    expires = created + timedelta(minutes=NONCE_TTL_MINUTES)
    conn.execute(
        "INSERT INTO public_form_nonces(deployment_id,nonce_hash,expires_at,created_at) VALUES (?,?,?,?)",
        (deployment_id, _sha(token), expires.isoformat(timespec="seconds"), created.isoformat(timespec="seconds")),
    )
    conn.commit()
    return token


def _consume_nonce(conn, deployment_id: int, token: str) -> bool:
    token = _clean(token, 200)
    if not token:
        return False
    row = conn.execute(
        "SELECT * FROM public_form_nonces WHERE deployment_id=? AND nonce_hash=?",
        (deployment_id, _sha(token)),
    ).fetchone()
    if row is None or row["used_at"]:
        return False
    try:
        if datetime.fromisoformat(row["expires_at"]) < datetime.now():
            return False
    except ValueError:
        return False
    conn.execute("UPDATE public_form_nonces SET used_at=? WHERE id=?", (now_iso(), row["id"]))
    return True


def _fingerprint(business_id: int, name: str, phone: str, email: str, service: str) -> str:
    basis = "|".join([
        str(business_id), name.lower(), re.sub(r"\D", "", phone), email.lower(), service.lower()
    ])
    return _sha(basis)


def _record_submission(conn, *, deployment_id, business_id, key, fingerprint, status,
                       lead_id=None, reason="", name="", phone="", email="", service=""):
    cur = conn.execute(
        """
        INSERT INTO public_intake_submissions(
            deployment_id,business_id,idempotency_key,fingerprint,status,lead_id,reason,
            submitted_name,submitted_phone,submitted_email,submitted_service,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (deployment_id,business_id,key,fingerprint,status,lead_id,reason,name,phone,email,service,now_iso()),
    )
    return cur.lastrowid


def submit_public_intake(conn, *, slug: str, nonce: str, idempotency_key: str, values: dict) -> dict:
    """Validate one public website request and create at most one canonical lead."""
    ensure_delivery_schema(conn)
    release = active_release_by_slug(conn, slug)
    if release is None:
        raise LookupError("This website release is not active.")
    business_id = int(release["business_id"])
    key = _clean(idempotency_key, 160)
    if not key:
        raise ValueError("Submission key is missing. Reload the form and try again.")

    prior = conn.execute(
        "SELECT * FROM public_intake_submissions WHERE deployment_id=? AND idempotency_key=?",
        (release["id"], key),
    ).fetchone()
    if prior:
        return {"status": "IDEMPOTENT_REPLAY", "lead_id": prior["lead_id"], "submission_id": prior["id"]}

    # Honeypot is intentionally silent from the user-facing form.
    if _clean(values.get("company_website"), 500):
        _record_submission(conn, deployment_id=release["id"], business_id=business_id,
                           key=key, fingerprint="", status="REJECTED", reason="honeypot")
        conn.commit()
        return {"status": "REJECTED", "lead_id": None}

    if not _consume_nonce(conn, release["id"], nonce):
        raise ValueError("This request form expired or was already submitted. Reload the page and try again.")

    name = _clean(values.get("name"), MAX_NAME)
    phone = _clean(values.get("phone"), MAX_PHONE)
    email = _clean(values.get("email"), MAX_EMAIL).lower()
    address = _clean(values.get("address"), MAX_ADDRESS)
    service = _clean(values.get("service"), MAX_SERVICE)
    message = _clean(values.get("message"), MAX_TEXT)
    preferred = _clean(values.get("preferred_time"), 200)

    errors = []
    if not name:
        errors.append("Name is required")
    if not phone and not email:
        errors.append("Phone or email is required")
    if email and not _valid_email(email):
        errors.append("Email address is invalid")

    allowed_services = {str(s.get("name") or "") for s in release["artifact"].get("services", [])}
    if service and service not in allowed_services:
        errors.append("Selected service is not offered on this website release")

    fingerprint = _fingerprint(business_id, name, phone, email, service)
    if errors:
        _record_submission(conn, deployment_id=release["id"], business_id=business_id,
                           key=key, fingerprint=fingerprint, status="REJECTED",
                           reason="; ".join(errors), name=name, phone=phone, email=email, service=service)
        conn.commit()
        return {"status": "REJECTED", "errors": errors, "lead_id": None}

    # Same person/service submitted recently: preserve the request record but do
    # not create a second lead. This catches double-clicks with different nonces.
    duplicate = conn.execute(
        """
        SELECT * FROM public_intake_submissions
        WHERE business_id=? AND fingerprint=? AND status IN ('ACCEPTED','DUPLICATE')
          AND created_at >= datetime('now','-15 minutes','localtime')
        ORDER BY id DESC LIMIT 1
        """,
        (business_id, fingerprint),
    ).fetchone()
    if duplicate and duplicate["lead_id"]:
        sid = _record_submission(conn, deployment_id=release["id"], business_id=business_id,
                                 key=key, fingerprint=fingerprint, status="DUPLICATE",
                                 lead_id=duplicate["lead_id"], reason="recent matching website request",
                                 name=name, phone=phone, email=email, service=service)
        conn.commit()
        return {"status": "DUPLICATE", "lead_id": duplicate["lead_id"], "submission_id": sid}

    ts = now_iso()
    cur = conn.execute(
        """
        INSERT INTO leads(
            business_id,caller_name,phone,address,service_type,issue_description,
            lead_type,priority,safety_flag,preferred_time,appointment_status,status,
            source,retell_call_id,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,'New Lead','Normal','',?,'Not Scheduled','New','Website','',?,?)
        """,
        (business_id,name,phone,address,service,message,preferred,ts,ts),
    )
    lead_id = cur.lastrowid
    # Email is not a canonical lead column in v13, so retain it as an intake note
    # rather than altering the lead schema ad hoc.
    if email:
        conn.execute(
            "INSERT INTO lead_notes(lead_id,note,created_at) VALUES (?,?,?)",
            (lead_id, f"Website contact email: {email}", ts),
        )
    sid = _record_submission(conn, deployment_id=release["id"], business_id=business_id,
                             key=key, fingerprint=fingerprint, status="ACCEPTED", lead_id=lead_id,
                             name=name, phone=phone, email=email, service=service)
    record_evidence(
        conn,
        business_id=business_id,
        fact_type="website_intake_submission",
        evidence_kind="SYSTEM_MEASURED",
        source_provider=LOCAL_PROVIDER,
        source_reference=f"submission:{sid}",
        summary=f"Website request accepted into canonical lead #{lead_id}.",
        confidence="deterministic",
        storage_policy="SYSTEM_LEDGER",
        entity_type="lead",
        entity_id=lead_id,
    )
    conn.commit()
    return {"status": "ACCEPTED", "lead_id": lead_id, "submission_id": sid}


def delivery_dashboard(conn, business_id: int) -> dict:
    readiness = delivery_readiness(conn, business_id)
    releases = list_releases(conn, business_id)
    submissions = [dict(r) for r in conn.execute(
        "SELECT * FROM public_intake_submissions WHERE business_id=? ORDER BY id DESC LIMIT 25",
        (business_id,),
    ).fetchall()]
    return {"readiness": readiness, "releases": releases, "submissions": submissions,
            "active_release": next((r for r in releases if r["is_active"]), None)}
