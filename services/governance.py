"""Data governance and tenant-boundary policy for Business OS.

The goal is simple: production automation must be provably owned by one active
client. Anything ambiguous is quarantined instead of guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from services.db import now_iso

LIFECYCLE_STAGES = {
    "PROSPECT", "QUALIFIED", "DEMO", "ONBOARDING", "ACTIVE", "PAUSED", "CANCELLED"
}
DATA_CLASSES = {"LEGACY", "TEST", "DEMO", "PRODUCTION", "UNVERIFIED"}
QUARANTINE_OPEN = "Open"
QUARANTINE_RELEASED = "Released"


@dataclass
class GovernanceDecision:
    allowed: bool
    reason: str
    classification: str = "UNVERIFIED"
    business_id: int | None = None


def lifecycle_for_legacy_status(status: str) -> str:
    status = (status or "").strip()
    mapping = {
        "Qualified": "QUALIFIED",
        "Demo": "DEMO",
        "Client": "ONBOARDING",
        "Lost": "CANCELLED",
    }
    return mapping.get(status, "PROSPECT")


def classify_inbound(conn, business_id: int | None) -> GovernanceDecision:
    """Classify a new inbound call without ever guessing ownership."""
    if not business_id:
        return GovernanceDecision(False, "No exact receptionist-to-client mapping exists.", "UNVERIFIED")

    business = conn.execute(
        "SELECT id, lifecycle_stage, status FROM businesses WHERE id = ?", (business_id,)
    ).fetchone()
    if business is None:
        return GovernanceDecision(False, "Mapped business no longer exists.", "UNVERIFIED")

    stage = (business["lifecycle_stage"] or lifecycle_for_legacy_status(business["status"])).upper()
    if stage == "ACTIVE":
        return GovernanceDecision(True, "Exact mapping resolved to an active client.", "PRODUCTION", business_id)
    if stage in {"DEMO", "ONBOARDING"}:
        return GovernanceDecision(False, f"Client is {stage.lower()}, so inbound data is demo-only.", "DEMO", business_id)
    return GovernanceDecision(False, f"Business lifecycle is {stage}; customer automation is locked.", "UNVERIFIED", business_id)


def quarantine(conn, entity_type: str, entity_id: int, reason_code: str, reason_detail: str,
               business_id: int | None = None, classification: str = "UNVERIFIED") -> None:
    """Create one open quarantine record for a specific reason, idempotently."""
    existing = conn.execute(
        """
        SELECT id FROM quarantine_items
        WHERE entity_type = ? AND entity_id = ? AND reason_code = ? AND status = 'Open'
        LIMIT 1
        """,
        (entity_type, entity_id, reason_code),
    ).fetchone()
    if existing:
        return
    conn.execute(
        """
        INSERT INTO quarantine_items
            (entity_type, entity_id, business_id, classification, reason_code,
             reason_detail, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Open', ?)
        """,
        (entity_type, entity_id, business_id, classification, reason_code, reason_detail, now_iso()),
    )


def production_automation_policy(conn, message) -> GovernanceDecision:
    """Hard gate for any future live action. Simulation may use a separate gate."""
    if message is None:
        return GovernanceDecision(False, "Message does not exist.")
    if not message["business_id"]:
        return GovernanceDecision(False, "Client ownership is missing.")

    business = conn.execute(
        "SELECT id, lifecycle_stage, automation_enabled FROM businesses WHERE id = ?",
        (message["business_id"],),
    ).fetchone()
    if business is None:
        return GovernanceDecision(False, "Owning business does not exist.")
    if (business["lifecycle_stage"] or "").upper() != "ACTIVE":
        return GovernanceDecision(False, "Owning business is not ACTIVE.", business_id=message["business_id"])
    if not int(business["automation_enabled"] or 0):
        return GovernanceDecision(False, "Client automation is disabled.", business_id=message["business_id"])

    lead = conn.execute(
        "SELECT id, business_id, data_classification, quarantine_status FROM leads WHERE id = ?",
        (message["lead_id"],),
    ).fetchone()
    if lead is None:
        return GovernanceDecision(False, "Linked lead does not exist.")
    if lead["business_id"] != message["business_id"]:
        return GovernanceDecision(False, "Lead and message cross a client boundary.")
    if (lead["data_classification"] or "").upper() != "PRODUCTION":
        return GovernanceDecision(False, "Lead is not classified as PRODUCTION.")
    if (lead["quarantine_status"] or "") == QUARANTINE_OPEN:
        return GovernanceDecision(False, "Lead is quarantined.")
    if (message["data_classification"] or "").upper() != "PRODUCTION":
        return GovernanceDecision(False, "Message is not classified as PRODUCTION.")
    if (message["quarantine_status"] or "") == QUARANTINE_OPEN:
        return GovernanceDecision(False, "Message is quarantined.")

    return GovernanceDecision(True, "Production ownership and lifecycle checks passed.", "PRODUCTION", message["business_id"])


def simulation_policy(conn, message) -> GovernanceDecision:
    """Allow safe simulations for owned demo/test/production data, never unowned data."""
    if message is None or not message["business_id"]:
        return GovernanceDecision(False, "Simulation requires explicit client ownership.")
    lead = conn.execute(
        "SELECT business_id, data_classification, quarantine_status FROM leads WHERE id = ?",
        (message["lead_id"],),
    ).fetchone()
    if lead is None or lead["business_id"] != message["business_id"]:
        return GovernanceDecision(False, "Simulation tenant boundary check failed.")
    if (lead["quarantine_status"] or "") == QUARANTINE_OPEN:
        return GovernanceDecision(False, "Simulation is blocked while the lead is quarantined.")
    cls = (lead["data_classification"] or "LEGACY").upper()
    if cls not in {"TEST", "DEMO", "PRODUCTION"}:
        return GovernanceDecision(False, f"Simulation is blocked for {cls} data.")
    return GovernanceDecision(True, "Simulation ownership checks passed.", cls, message["business_id"])
