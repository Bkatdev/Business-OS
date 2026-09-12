"""v14 governed prospect discovery wrapper.

This wraps the existing Google Places implementation instead of forking it.
It meters provider usage and records reference-only provenance. No raw provider
payload is persisted here, and provider pricing is deliberately not guessed.
"""
from __future__ import annotations

from services.db import connect
from services.platform_foundation import record_evidence, record_usage
from services.prospect_finder import discover as _google_discover


def discover(query, page_size=10, fallback_category="Local Service Business", *, discover_fn=None):
    runner = discover_fn or _google_discover
    requested = max(1, min(int(page_size), 20))
    try:
        result = runner(query, requested, fallback_category)
    except Exception:
        con = connect()
        try:
            record_usage(
                con,
                provider="google_places",
                capability="prospect_discovery",
                units=1,
                unit_name="request",
                status="FAILED",
                detail={"requested_results": requested},
            )
            con.commit()
        finally:
            con.close()
        raise

    con = connect()
    try:
        record_usage(
            con,
            provider="google_places",
            capability="prospect_discovery",
            units=1,
            unit_name="request",
            status="SUCCEEDED",
            detail={
                "requested_results": requested,
                "returned": int(result.get("returned", 0)),
            },
        )
        for business_id, _name in result.get("added", []):
            row = con.execute(
                "SELECT google_place_id FROM businesses WHERE id=?",
                (business_id,),
            ).fetchone()
            place_id = (row["google_place_id"] if row else "") or ""
            record_evidence(
                con,
                business_id=int(business_id),
                entity_type="business",
                entity_id=int(business_id),
                fact_type="discovery_reference",
                evidence_kind="PUBLIC_THIRD_PARTY",
                source_provider="google_places",
                source_reference=place_id,
                summary="Prospect discovered through configured Places provider.",
                confidence="provider_reference",
                storage_policy="REFERENCE_ONLY",
            )
        con.commit()
    finally:
        con.close()
    return result
