"""Business OS v14 - production architecture foundation.

Business OS owns canonical truth. External vendors remain replaceable edges.
This module adds provider-independent records for provenance, usage/cost,
assets, and deployment history without unlocking any live provider.
"""
from __future__ import annotations

import json
from typing import Any

from services.db import now_iso

EVIDENCE_KINDS = {
    "PUBLIC_OBSERVED",
    "PUBLIC_THIRD_PARTY",
    "AI_ASSESSMENT",
    "OWNER_VERIFIED",
    "SYSTEM_MEASURED",
    "UNKNOWN",
}

DEPLOYMENT_STATES = {
    "DRAFT",
    "READY",
    "DEPLOYING",
    "ACTIVE",
    "FAILED",
    "ROLLED_BACK",
}


def ensure_platform_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS evidence_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            entity_type TEXT NOT NULL DEFAULT '',
            entity_id INTEGER,
            fact_type TEXT NOT NULL,
            evidence_kind TEXT NOT NULL,
            source_provider TEXT NOT NULL DEFAULT '',
            source_reference TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            confidence TEXT NOT NULL DEFAULT '',
            storage_policy TEXT NOT NULL DEFAULT 'REFERENCE_ONLY',
            observed_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_business_created
            ON evidence_records(business_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_evidence_entity
            ON evidence_records(entity_type, entity_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            provider TEXT NOT NULL,
            capability TEXT NOT NULL,
            execution_reference TEXT NOT NULL DEFAULT '',
            unit_name TEXT NOT NULL DEFAULT 'request',
            units REAL NOT NULL DEFAULT 0,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            status TEXT NOT NULL DEFAULT 'RECORDED',
            detail_json TEXT NOT NULL DEFAULT '{}',
            occurred_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );
        CREATE INDEX IF NOT EXISTS idx_usage_business_time
            ON usage_events(business_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_usage_provider_capability
            ON usage_events(provider, capability, occurred_at DESC);

        CREATE TABLE IF NOT EXISTS media_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_reference TEXT NOT NULL DEFAULT '',
            storage_key TEXT NOT NULL DEFAULT '',
            rights_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            business_verified INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );
        CREATE INDEX IF NOT EXISTS idx_media_assets_business
            ON media_assets(business_id, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS site_deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            website_version_id INTEGER,
            concept_id INTEGER,
            provider TEXT NOT NULL DEFAULT '',
            deployment_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            preview_reference TEXT NOT NULL DEFAULT '',
            production_reference TEXT NOT NULL DEFAULT '',
            previous_deployment_id INTEGER,
            requested_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT '',
            failure_detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (previous_deployment_id) REFERENCES site_deployments(id)
        );
        CREATE INDEX IF NOT EXISTS idx_site_deployments_business
            ON site_deployments(business_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_site_deployments_status
            ON site_deployments(status, created_at DESC);
        """
    )


def _business_exists(conn, business_id: int) -> bool:
    return conn.execute("SELECT 1 FROM businesses WHERE id=?", (business_id,)).fetchone() is not None


def require_business(conn, business_id: int):
    row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if row is None:
        raise LookupError(f"Business {business_id} does not exist")
    return row


def record_evidence(
    conn,
    *,
    business_id: int | None,
    fact_type: str,
    evidence_kind: str,
    source_provider: str = "",
    source_reference: str = "",
    summary: str = "",
    confidence: str = "",
    storage_policy: str = "REFERENCE_ONLY",
    entity_type: str = "business",
    entity_id: int | None = None,
    observed_at: str | None = None,
):
    if evidence_kind not in EVIDENCE_KINDS:
        raise ValueError(f"Unsupported evidence kind: {evidence_kind}")
    if business_id is not None and not _business_exists(conn, int(business_id)):
        raise LookupError(f"Business {business_id} does not exist")
    ts = observed_at or now_iso()
    cur = conn.execute(
        """
        INSERT INTO evidence_records (
            business_id, entity_type, entity_id, fact_type, evidence_kind,
            source_provider, source_reference, summary, confidence,
            storage_policy, observed_at, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            business_id, entity_type, entity_id, fact_type, evidence_kind,
            source_provider, source_reference, summary, confidence,
            storage_policy, ts, now_iso(),
        ),
    )
    return cur.lastrowid


def record_usage(
    conn,
    *,
    provider: str,
    capability: str,
    units: float = 1,
    unit_name: str = "request",
    business_id: int | None = None,
    estimated_cost_usd: float | None = None,
    actual_cost_usd: float | None = None,
    execution_reference: str = "",
    status: str = "RECORDED",
    detail: dict[str, Any] | None = None,
):
    if business_id is not None and not _business_exists(conn, int(business_id)):
        raise LookupError(f"Business {business_id} does not exist")
    ts = now_iso()
    cur = conn.execute(
        """
        INSERT INTO usage_events (
            business_id, provider, capability, execution_reference,
            unit_name, units, estimated_cost_usd, actual_cost_usd,
            status, detail_json, occurred_at, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            business_id, provider, capability, execution_reference,
            unit_name, float(units), estimated_cost_usd, actual_cost_usd,
            status, json.dumps(detail or {}, sort_keys=True), ts, ts,
        ),
    )
    return cur.lastrowid


def usage_summary(conn):
    row = conn.execute(
        """
        SELECT COUNT(*) AS event_count,
               COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd, 0)),0) AS tracked_cost
        FROM usage_events
        """
    ).fetchone()
    return {
        "event_count": int(row["event_count"] or 0),
        "tracked_cost": float(row["tracked_cost"] or 0),
    }


def create_deployment_record(
    conn,
    *,
    business_id: int,
    deployment_key: str,
    website_version_id: int | None = None,
    concept_id: int | None = None,
):
    require_business(conn, business_id)
    ts = now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO site_deployments (
            business_id, website_version_id, concept_id, deployment_key,
            status, requested_at, created_at, updated_at
        ) VALUES (?,?,?,?, 'DRAFT', ?,?,?)
        """,
        (business_id, website_version_id, concept_id, deployment_key, ts, ts, ts),
    )
    return conn.execute(
        "SELECT * FROM site_deployments WHERE deployment_key=?",
        (deployment_key,),
    ).fetchone()
