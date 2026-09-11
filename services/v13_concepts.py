"""Business OS v13 - immutable prospect website concepts."""

from __future__ import annotations

import json

from services.db import now_iso
from services.v13_blueprints import blueprint_json, normalize_stored_blueprint, validate_blueprint

CONCEPT_STATUSES = ("DRAFT", "REVIEWED", "SUPERSEDED")
TRUTH_STATES = ("PUBLIC_UNVERIFIED", "OWNER_VERIFIED")


class ConceptError(ValueError):
    pass


class ConceptNotFound(ConceptError):
    pass


def ensure_v13_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS website_concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            concept_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK(status IN ('DRAFT','REVIEWED','SUPERSEDED')),
            truth_state TEXT NOT NULL DEFAULT 'PUBLIC_UNVERIFIED'
                CHECK(truth_state IN ('PUBLIC_UNVERIFIED','OWNER_VERIFIED')),
            generation_mode TEXT NOT NULL DEFAULT 'LOCAL_DESIGNER',
            creative_brief TEXT NOT NULL DEFAULT '',
            blueprint_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE(business_id, concept_number)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_concepts_business
        ON website_concepts(business_id, concept_number DESC)
        """
    )
    conn.commit()


def _business_exists(conn, business_id):
    return conn.execute("SELECT 1 FROM businesses WHERE id=?", (business_id,)).fetchone() is not None


def next_concept_number(conn, business_id):
    ensure_v13_schema(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(concept_number),0) FROM website_concepts WHERE business_id=?",
        (business_id,),
    ).fetchone()
    return int(row[0] or 0) + 1


def create_concept(conn, business_id, creative_brief, blueprint, generation_mode="LOCAL_DESIGNER"):
    ensure_v13_schema(conn)
    if not _business_exists(conn, business_id):
        raise ConceptNotFound("Business does not exist.")
    validate_blueprint(blueprint)
    number = next_concept_number(conn, business_id)
    cur = conn.execute(
        """
        INSERT INTO website_concepts (
            business_id, concept_number, status, truth_state,
            generation_mode, creative_brief, blueprint_json, created_at
        ) VALUES (?, ?, 'DRAFT', 'PUBLIC_UNVERIFIED', ?, ?, ?, ?)
        """,
        (
            business_id,
            number,
            str(generation_mode or "LOCAL_DESIGNER")[:80],
            str(creative_brief or "")[:700],
            blueprint_json(blueprint),
            now_iso(),
        ),
    )
    conn.commit()
    return get_concept_for_business(conn, business_id, cur.lastrowid)


def _decode(row):
    if not row:
        return None
    result = dict(row)
    try:
        stored_blueprint = json.loads(result.get("blueprint_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ConceptError("Stored concept blueprint is invalid JSON.")
    try:
        runtime_blueprint, source_version, legacy_compat = normalize_stored_blueprint(stored_blueprint)
    except ValueError as exc:
        raise ConceptError(f"Stored concept blueprint is unsupported: {exc}") from exc
    result["blueprint"] = runtime_blueprint
    result["source_schema_version"] = source_version
    result["runtime_schema_version"] = runtime_blueprint.get("schema_version")
    result["legacy_compat"] = legacy_compat
    return result


def list_concepts(conn, business_id, limit=30):
    ensure_v13_schema(conn)
    limit = max(1, min(int(limit or 30), 100))
    rows = conn.execute(
        """
        SELECT * FROM website_concepts
        WHERE business_id=?
        ORDER BY concept_number DESC, id DESC
        LIMIT ?
        """,
        (business_id, limit),
    ).fetchall()
    return [_decode(row) for row in rows]


def get_concept_for_business(conn, business_id, concept_id):
    ensure_v13_schema(conn)
    row = conn.execute(
        """
        SELECT * FROM website_concepts
        WHERE id=? AND business_id=?
        """,
        (concept_id, business_id),
    ).fetchone()
    if not row:
        raise ConceptNotFound("Concept does not belong to this business or does not exist.")
    return _decode(row)
