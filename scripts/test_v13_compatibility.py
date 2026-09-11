from pathlib import Path
import json
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.v13_blueprints import validate_blueprint
from services.v13_concepts import create_concept, ensure_v13_schema, list_concepts
from services.v13_creative_director import generate_concept_blueprint


def assert_true(label, value):
    if not value:
        raise AssertionError(label)
    print(f"PASS: {label}")


db_path = Path(tempfile.gettempdir()) / "business_os_v13_compatibility_test.db"
if db_path.exists():
    db_path.unlink()
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")
conn.execute(
    """
    CREATE TABLE businesses (
        id INTEGER PRIMARY KEY,
        name TEXT, category TEXT, city TEXT, phone TEXT,
        rating REAL, reviews INTEGER, audit_status TEXT,
        estimate_form INTEGER, online_booking INTEGER, website_chat INTEGER,
        emergency_service INTEGER, scheduling_mentioned INTEGER
    )
    """
)
conn.execute(
    "INSERT INTO businesses VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?)",
    ("Legacy Tree Co", "Tree Care", "East Brunswick", "(732) 555-0101", 4.7, 21, "completed", 0, 0, 0, 0, 0),
)
ensure_v13_schema(conn)

legacy_v1 = {
    "schema_version": 1,
    "personality": "rugged",
    "hero_layout": "split",
    "nav_style": "quiet",
    "type_system": "strong",
    "palette": "forest",
    "spacing": "comfortable",
    "radius": "soft",
    "surface": "layered",
    "cta_style": "solid",
    "section_order": ["category", "business_snapshot", "contact"],
    "section_variants": {"business_snapshot": "cards", "category": "split", "contact": "panel"},
    "creative_brief": "rugged local",
}
legacy_json = json.dumps(legacy_v1, sort_keys=True, separators=(",", ":"))
conn.execute(
    """
    INSERT INTO website_concepts (
        business_id, concept_number, status, truth_state,
        generation_mode, creative_brief, blueprint_json, created_at
    ) VALUES (1,1,'DRAFT','PUBLIC_UNVERIFIED','LOCAL_DESIGNER','rugged local',?,'2026-01-01T00:00:00')
    """,
    (legacy_json,),
)
conn.commit()

legacy = list_concepts(conn, 1)[0]
assert_true("stored v1 concept remains readable", legacy["source_schema_version"] == 1)
assert_true("v1 concept receives validated v2 runtime view", legacy["runtime_schema_version"] == 2 and legacy["legacy_compat"] is True)
validate_blueprint(legacy["blueprint"])
assert_true("legacy category section maps safely", "category_focus" in legacy["blueprint"]["section_order"])

stored_after = conn.execute(
    "SELECT blueprint_json FROM website_concepts WHERE business_id=1 AND concept_number=1"
).fetchone()[0]
assert_true("legacy immutable blueprint bytes are not mutated", stored_after == legacy_json)

business = dict(conn.execute("SELECT * FROM businesses WHERE id=1").fetchone())
director = generate_concept_blueprint(business, "premium high-end editorial", 2)
new_concept = create_concept(conn, 1, "premium high-end editorial", director.blueprint, director.generation_mode)
assert_true("new concepts remain native schema v2", new_concept["source_schema_version"] == 2 and new_concept["legacy_compat"] is False)
assert_true("old and new concepts coexist in history", len(list_concepts(conn, 1)) == 2)

bad = dict(legacy_v1)
bad["hero_layout"] = "<script>alert(1)</script>"
bad_json = json.dumps(bad, sort_keys=True, separators=(",", ":"))
conn.execute(
    """
    INSERT INTO website_concepts (
        business_id, concept_number, status, truth_state,
        generation_mode, creative_brief, blueprint_json, created_at
    ) VALUES (1,3,'DRAFT','PUBLIC_UNVERIFIED','LOCAL_DESIGNER','bad',?,'2026-01-01T00:00:01')
    """,
    (bad_json,),
)
conn.commit()
try:
    list_concepts(conn, 1)
except ValueError:
    print("PASS: malformed legacy blueprint still fails closed")
else:
    raise AssertionError("malformed legacy blueprint unexpectedly passed")

print("ALL V13 COMPATIBILITY TESTS PASSED")
