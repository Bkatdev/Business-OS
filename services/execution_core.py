"""Governed, idempotent execution spine for Business OS v11."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from services.db import now_iso
from services.control_plane import ensure_control_plane_schema
from services.execution_schema import ensure_execution_schema
from services.providers.base import ProviderResult, ProviderUnavailable
from services.providers.registry import provider_for

LIVE_ENABLE_ENV = "BUSINESS_OS_LIVE_ACTIONS_ENABLED"


@dataclass(frozen=True)
class ActionIntent:
    action_type: str
    business_id: int
    lead_id: int | None = None
    source_entity_type: str = ""
    source_entity_id: int | None = None
    mode: str = "simulation"
    approval_required: bool = False
    approval_reference: str = ""
    data_classification: str = "UNVERIFIED"
    quarantine_status: str = "Not Required"
    max_retries: int = 3


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    status: str
    detail: str
    action_id: int | None = None
    provider: str = ""
    provider_external_id: str = ""
    deduplicated: bool = False


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def live_actions_enabled() -> bool:
    return _truthy(os.getenv(LIVE_ENABLE_ENV, "0"))


def _canonical_payload(payload) -> str:
    return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_fingerprint(payload) -> str:
    return hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()


def build_idempotency_key(intent: ActionIntent, payload) -> str:
    raw = "|".join(
        [
            str(intent.action_type or "").upper(),
            str(intent.business_id or ""),
            str(intent.lead_id or ""),
            str(intent.source_entity_type or "").lower(),
            str(intent.source_entity_id or ""),
            str(intent.mode or "simulation").lower(),
            payload_fingerprint(payload),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _row_dict(row):
    return dict(row) if row is not None else None


def _write_ledger(conn, *, event_type, title, detail, severity="Info", source="Execution Engine",
                  business_id=None, lead_id=None, outcome=""):
    # Do not open a second SQLite connection while an action transaction is live.
    conn.execute(
        """
        INSERT INTO system_ledger
            (event_type, severity, source, business_id, lead_id, title, detail, outcome, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_type, severity, source, business_id, lead_id, title, detail, outcome, now_iso()),
    )


def _write_policy(conn, *, intent, decision, reason, context=None):
    conn.execute(
        """
        INSERT INTO policy_decisions
            (action_type, business_id, lead_id, decision, reason, context_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            intent.action_type,
            intent.business_id,
            intent.lead_id,
            decision,
            reason,
            json.dumps(context or {}, sort_keys=True),
            now_iso(),
        ),
    )


def _base_safety_check(conn, intent: ActionIntent):
    business = conn.execute(
        "SELECT id, lifecycle_stage, automation_enabled FROM businesses WHERE id = ?",
        (intent.business_id,),
    ).fetchone()
    if business is None:
        return False, "Owning business does not exist."

    if intent.lead_id is not None:
        lead = conn.execute(
            "SELECT id, business_id, data_classification, quarantine_status FROM leads WHERE id = ?",
            (intent.lead_id,),
        ).fetchone()
        if lead is None:
            return False, "Linked lead does not exist."
        if lead["business_id"] != intent.business_id:
            return False, "Tenant safety check failed: action and lead belong to different businesses."
        if (lead["quarantine_status"] or "") == "Open":
            return False, "Linked lead is quarantined."
        lead_class = (lead["data_classification"] or "UNVERIFIED").upper()
        if lead_class != (intent.data_classification or "UNVERIFIED").upper():
            return False, "Action classification does not match the linked lead."

    if (intent.quarantine_status or "") == "Open":
        return False, "Source record is quarantined."

    if intent.approval_required and not str(intent.approval_reference or "").strip():
        return False, "Action requires approval but no approval reference was supplied."

    mode = str(intent.mode or "simulation").lower()
    stage = (business["lifecycle_stage"] or "").upper()
    if stage in {"PAUSED", "CANCELLED"}:
        return False, f"Owning business is {stage}; execution is locked."
    if mode == "live":
        if not live_actions_enabled():
            return False, f"Global live-action gate {LIVE_ENABLE_ENV} is off."
        if (business["lifecycle_stage"] or "").upper() != "ACTIVE":
            return False, "Owning business is not ACTIVE."
        if not int(business["automation_enabled"] or 0):
            return False, "Client automation is disabled."
        if (intent.data_classification or "").upper() != "PRODUCTION":
            return False, "Live execution requires PRODUCTION data."
    else:
        if (intent.data_classification or "").upper() not in {"TEST", "DEMO", "PRODUCTION"}:
            return False, "Simulation requires TEST, DEMO, or PRODUCTION data."

    return True, "Base execution safety checks passed."


def _existing_action(conn, idempotency_key):
    return conn.execute(
        "SELECT * FROM actions WHERE idempotency_key = ? LIMIT 1", (idempotency_key,)
    ).fetchone()


def _result_from_existing(row):
    status = row["status"]
    ok = status == "SUCCEEDED"
    detail = row["outcome_detail"] or row["policy_reason"] or row["last_error"] or "Existing action reused."
    return ActionResult(
        ok=ok,
        status=status,
        detail=detail,
        action_id=row["id"],
        provider=row["provider"] or "",
        provider_external_id=row["provider_external_id"] or "",
        deduplicated=True,
    )


def _insert_action(conn, intent: ActionIntent, idempotency_key: str, request_fingerprint: str):
    timestamp = now_iso()
    action_key = f"act_{uuid.uuid4().hex}"
    before = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO actions (
            action_key, action_type, business_id, lead_id, source_entity_type,
            source_entity_id, mode, status, approval_required, approval_reference,
            idempotency_key, request_fingerprint, requested_at, max_retries,
            data_classification, quarantine_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'REQUESTED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_key,
            str(intent.action_type).upper(),
            intent.business_id,
            intent.lead_id,
            intent.source_entity_type,
            intent.source_entity_id,
            str(intent.mode or "simulation").lower(),
            1 if intent.approval_required else 0,
            intent.approval_reference,
            idempotency_key,
            request_fingerprint,
            timestamp,
            max(0, min(int(intent.max_retries or 0), 10)),
            (intent.data_classification or "UNVERIFIED").upper(),
            intent.quarantine_status or "Not Required",
            timestamp,
            timestamp,
        ),
    )
    created = conn.total_changes > before
    row = conn.execute("SELECT * FROM actions WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    return row, created


def _retry_time(attempt_number: int):
    # Persist the future retry point; no worker is enabled in v11.
    seconds = min(3600, 30 * (2 ** max(0, attempt_number - 1)))
    return (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _apply_provider_result(conn, action, attempt_number: int, provider_name: str, result: ProviderResult):
    timestamp = now_iso()
    outcome = str(result.outcome or "UNKNOWN").upper()

    if outcome == "CONFIRMED":
        status = "SUCCEEDED"
        accepted_at = timestamp
        completed_at = timestamp
        next_retry_at = ""
    elif outcome == "ACCEPTED":
        status = "ACCEPTED_PENDING_OUTCOME"
        accepted_at = timestamp
        completed_at = ""
        next_retry_at = ""
    elif outcome == "FAILED":
        accepted_at = ""
        completed_at = timestamp if not result.retryable else ""
        if result.retryable and int(action["retry_count"] or 0) < int(action["max_retries"] or 0):
            status = "RETRY_SCHEDULED"
            next_retry_at = _retry_time(attempt_number)
        else:
            status = "FAILED_PERMANENT"
            next_retry_at = ""
    else:
        # Unknown outcomes must be reconciled before retrying; blind retry can duplicate side effects.
        status = "UNKNOWN"
        accepted_at = ""
        completed_at = ""
        next_retry_at = ""

    conn.execute(
        """
        UPDATE action_attempts
        SET status = ?, provider_external_id = ?, error_class = ?, error_detail = ?, finished_at = ?
        WHERE action_id = ? AND attempt_number = ?
        """,
        (
            outcome,
            result.external_id,
            result.error_class,
            result.detail if outcome in {"FAILED", "UNKNOWN"} else "",
            timestamp,
            action["id"],
            attempt_number,
        ),
    )
    conn.execute(
        """
        UPDATE actions
        SET status = ?, provider = ?, provider_external_id = ?, accepted_at = ?,
            completed_at = ?, next_retry_at = ?, retry_count = ?, last_error_class = ?,
            last_error = ?, outcome_detail = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            provider_name,
            result.external_id,
            accepted_at,
            completed_at,
            next_retry_at,
            attempt_number,
            result.error_class if outcome in {"FAILED", "UNKNOWN"} else "",
            result.detail if outcome in {"FAILED", "UNKNOWN"} else "",
            result.detail,
            timestamp,
            action["id"],
        ),
    )
    severity = "High" if status in {"UNKNOWN", "FAILED_PERMANENT"} else "Info"
    _write_ledger(
        conn,
        event_type="Action",
        title=f"{action['action_type']} · {status}",
        detail=result.detail,
        severity=severity,
        business_id=action["business_id"],
        lead_id=action["lead_id"],
        outcome=status,
    )
    return status


def execute_action(conn, intent: ActionIntent, payload, *, policy_allowed: bool, policy_reason: str,
                   policy_context=None) -> ActionResult:
    """Execute one governed action through a replaceable provider boundary.

    The function is intentionally synchronous for v11 local development, but all
    action state is persisted so a background worker can be added later without
    redefining business truth.
    """
    ensure_execution_schema(conn)
    ensure_control_plane_schema(conn)
    request_fingerprint = payload_fingerprint(payload)
    idempotency_key = build_idempotency_key(intent, payload)

    existing = _existing_action(conn, idempotency_key)
    if existing is not None:
        return _result_from_existing(existing)

    action, created = _insert_action(conn, intent, idempotency_key, request_fingerprint)
    if not created:
        return _result_from_existing(action)

    base_allowed, base_reason = _base_safety_check(conn, intent)
    allowed = bool(policy_allowed and base_allowed)
    reason = policy_reason if not policy_allowed else base_reason
    decision = "ALLOW" if allowed else "BLOCK"

    _write_policy(conn, intent=intent, decision=decision, reason=reason, context=policy_context)
    conn.execute(
        "UPDATE actions SET policy_decision = ?, policy_reason = ?, updated_at = ? WHERE id = ?",
        (decision, reason, now_iso(), action["id"]),
    )

    if not allowed:
        conn.execute(
            "UPDATE actions SET status = 'BLOCKED', completed_at = ?, outcome_detail = ?, updated_at = ? WHERE id = ?",
            (now_iso(), reason, now_iso(), action["id"]),
        )
        _write_ledger(
            conn,
            event_type="Action",
            title=f"{intent.action_type} · BLOCKED",
            detail=reason,
            severity="High",
            business_id=intent.business_id,
            lead_id=intent.lead_id,
            outcome="BLOCKED",
        )
        conn.commit()
        return ActionResult(False, "BLOCKED", reason, action["id"])

    try:
        provider = provider_for(action_type=intent.action_type, mode=intent.mode)
    except ProviderUnavailable as exc:
        detail = str(exc)
        conn.execute(
            "UPDATE actions SET status='BLOCKED', policy_decision='BLOCK', policy_reason=?, completed_at=?, outcome_detail=?, updated_at=? WHERE id=?",
            (detail, now_iso(), detail, now_iso(), action["id"]),
        )
        _write_ledger(
            conn,
            event_type="Action",
            title=f"{intent.action_type} · PROVIDER LOCKED",
            detail=detail,
            severity="High",
            business_id=intent.business_id,
            lead_id=intent.lead_id,
            outcome="BLOCKED",
        )
        conn.commit()
        return ActionResult(False, "BLOCKED", detail, action["id"])

    attempt_number = int(action["retry_count"] or 0) + 1
    timestamp = now_iso()
    conn.execute(
        "UPDATE actions SET status='ATTEMPTING', started_at=?, provider=?, updated_at=? WHERE id=?",
        (timestamp, provider.name, timestamp, action["id"]),
    )
    conn.execute(
        """
        INSERT INTO action_attempts
            (action_id, attempt_number, provider, status, request_fingerprint, started_at)
        VALUES (?, ?, ?, 'ATTEMPTING', ?, ?)
        """,
        (action["id"], attempt_number, provider.name, request_fingerprint, timestamp),
    )
    conn.commit()

    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action["id"],)).fetchone()
    try:
        provider_result = provider.execute(action=action, payload=payload)
    except Exception as exc:  # provider boundary: unexpected exception becomes UNKNOWN, never blind retry
        provider_result = ProviderResult(
            outcome="UNKNOWN",
            detail=f"Provider execution raised {type(exc).__name__}; outcome requires reconciliation.",
            retryable=False,
            error_class=type(exc).__name__,
        )

    status = _apply_provider_result(conn, action, attempt_number, provider.name, provider_result)
    conn.commit()
    return ActionResult(
        ok=status == "SUCCEEDED",
        status=status,
        detail=provider_result.detail,
        action_id=action["id"],
        provider=provider.name,
        provider_external_id=provider_result.external_id,
    )


def reconcile_action_outcome(conn, action_id: int, *, status: str, detail: str,
                             provider_external_id: str = "") -> ActionResult:
    """Apply a trusted normalized provider outcome to an existing action.

    Signature verification and provider-specific event translation happen before
    this boundary. Final success is monotonic: a late/out-of-order callback may
    confirm uncertain work, but cannot downgrade an already confirmed action.
    """
    ensure_execution_schema(conn)
    ensure_control_plane_schema(conn)
    action = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if action is None:
        return ActionResult(False, "NOT_FOUND", "Action does not exist.", action_id=action_id)

    current = action["status"]
    target = str(status or "").strip().upper()
    allowed_targets = {"SUCCEEDED", "FAILED_PERMANENT", "UNKNOWN", "ACCEPTED_PENDING_OUTCOME"}
    if target not in allowed_targets:
        raise ValueError(f"Unsupported normalized outcome: {target}")
    if current in {"BLOCKED", "CANCELLED"}:
        return ActionResult(False, current, "Blocked or cancelled actions cannot receive provider outcomes.", action_id=action_id, deduplicated=True)
    if current == "SUCCEEDED":
        return ActionResult(True, current, action["outcome_detail"] or "Action already confirmed.", action_id=action_id, provider=action["provider"], provider_external_id=action["provider_external_id"], deduplicated=True)

    timestamp = now_iso()
    completed_at = timestamp if target in {"SUCCEEDED", "FAILED_PERMANENT"} else ""
    accepted_at = action["accepted_at"] or (timestamp if target in {"SUCCEEDED", "ACCEPTED_PENDING_OUTCOME"} else "")
    external_id = provider_external_id or action["provider_external_id"] or ""
    conn.execute(
        """
        UPDATE actions
        SET status=?, provider_external_id=?, accepted_at=?, completed_at=?,
            next_retry_at='', last_error_class=?, last_error=?, outcome_detail=?, updated_at=?
        WHERE id=?
        """,
        (
            target,
            external_id,
            accepted_at,
            completed_at,
            "PROVIDER_OUTCOME" if target in {"FAILED_PERMANENT", "UNKNOWN"} else "",
            detail if target in {"FAILED_PERMANENT", "UNKNOWN"} else "",
            detail,
            timestamp,
            action_id,
        ),
    )
    _write_ledger(
        conn,
        event_type="Outcome",
        title=f"{action['action_type']} · {target}",
        detail=detail,
        severity="High" if target in {"FAILED_PERMANENT", "UNKNOWN"} else "Info",
        business_id=action["business_id"],
        lead_id=action["lead_id"],
        outcome=target,
    )
    conn.commit()
    return ActionResult(target == "SUCCEEDED", target, detail, action_id, action["provider"], external_id)


def record_provider_event(conn, *, provider: str, event_id: str, event_type: str = "",
                          provider_external_id: str = "", payload=None):
    """Idempotently record an authenticated, normalized provider event.

    Provider-specific webhook verification must happen before this function is
    called. v11 exposes no generic public webhook route.
    """
    ensure_execution_schema(conn)
    provider = str(provider or "").strip()
    event_id = str(event_id or "").strip()
    if not provider or not event_id:
        raise ValueError("provider and event_id are required")

    existing = conn.execute(
        "SELECT * FROM provider_events WHERE provider = ? AND event_id = ?",
        (provider, event_id),
    ).fetchone()
    if existing is not None:
        return existing, True

    action = None
    if provider_external_id:
        action = conn.execute(
            "SELECT id FROM actions WHERE provider = ? AND provider_external_id = ? ORDER BY id DESC LIMIT 1",
            (provider, provider_external_id),
        ).fetchone()
    payload_hash = payload_fingerprint(payload)
    timestamp = now_iso()
    cur = conn.execute(
        """
        INSERT INTO provider_events
            (provider, event_id, event_type, provider_external_id, action_id,
             payload_hash, processing_status, received_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Received', ?)
        """,
        (
            provider,
            event_id,
            event_type,
            provider_external_id,
            action["id"] if action else None,
            payload_hash,
            timestamp,
        ),
    )
    conn.commit()
    return conn.execute("SELECT * FROM provider_events WHERE id = ?", (cur.lastrowid,)).fetchone(), False
