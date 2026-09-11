from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.v13_blueprints import BlueprintValidationError, SCHEMA_VERSION, generate_blueprint, validate_blueprint
from services.v13_concepts import create_concept, ensure_v13_schema, get_concept_for_business, ConceptNotFound
from services.v13_sales import build_sales_brief


def row(**values):
    return values


def main():
    business = row(id=7, name="Example Tree Care", category="Tree Service", city="Exampletown", reviews=180,
                   audit_status="completed", estimate_form=0, online_booking=0, website_chat=0,
                   emergency_service=1, scheduling_mentioned=0)

    one = generate_blueprint(business, "rugged established local", 1)
    two = generate_blueprint(business, "premium editorial", 2)
    assert one != two
    validate_blueprint(one)
    validate_blueprint(two)
    print("PASS: different creative directions produce different validated blueprints")

    bad = dict(one)
    bad["hero_layout"] = "<script>alert(1)</script>"
    try:
        validate_blueprint(bad)
        raise AssertionError("unsafe blueprint was accepted")
    except BlueprintValidationError:
        pass
    print("PASS: unsupported/executable blueprint values fail closed")

    sales = build_sales_brief(business)
    assert sales["recommended_plan"] == "Front Office"
    assert "lost revenue" not in " ".join(sales["pitch_points"]).lower()
    print("PASS: evidence-backed package recommendation avoids fake ROI")

    unknown = dict(business)
    unknown["audit_status"] = "not_audited"
    pending = build_sales_brief(unknown)
    assert pending["recommended_plan"] == "Audit first"
    print("PASS: unknown website state does not become a scored weakness")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE businesses (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.executemany("INSERT INTO businesses(id,name) VALUES (?,?)", [(7,"A"),(8,"B")])
    ensure_v13_schema(conn)
    concept = create_concept(conn, 7, "premium", one)
    assert concept["business_id"] == 7
    try:
        get_concept_for_business(conn, 8, concept["id"])
        raise AssertionError("cross-tenant concept fetch was accepted")
    except ConceptNotFound:
        pass
    print("PASS: concept lookup enforces business ownership")

    raw = conn.execute("SELECT blueprint_json FROM website_concepts WHERE id=?", (concept["id"],)).fetchone()[0]
    assert json.loads(raw)["schema_version"] == SCHEMA_VERSION
    print("PASS: immutable concept stores validated blueprint JSON")
    conn.close()

    print("ALL V13 FOUNDATION TESTS PASSED")


if __name__ == "__main__":
    main()
