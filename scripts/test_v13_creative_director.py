from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.v13_blueprints import BlueprintValidationError, validate_blueprint
from services.v13_creative_director import generate_concept_blueprint
from services.v13_site_model import build_site_model


def assert_true(label, value):
    if not value:
        raise AssertionError(label)
    print(f"PASS: {label}")


def business(**overrides):
    row = {
        "id": 1,
        "name": "Herb Clark Tree Services",
        "category": "Tree Care",
        "city": "East Brunswick",
        "phone": "(732) 238-7976",
        "rating": 4.8,
        "reviews": 143,
        "audit_status": "completed",
        "estimate_form": 0,
        "online_booking": 0,
        "website_chat": 0,
        "emergency_service": 1,
        "scheduling_mentioned": 0,
    }
    row.update(overrides)
    return row


premium = generate_concept_blueprint(business(), "premium high-end editorial", 1)
rugged = generate_concept_blueprint(business(), "rugged blue-collar practical", 2)
minimal = generate_concept_blueprint(business(), "minimal and quiet", 3)
auto = generate_concept_blueprint(
    business(id=2, name="Example Auto Repair", category="Auto Repair", city="Marlboro"),
    "rugged and direct",
    1,
)

for result in (premium, rugged, minimal, auto):
    validate_blueprint(result.blueprint)

assert_true("creative directions change layout family", len({premium.blueprint["layout_family"], rugged.blueprint["layout_family"], minimal.blueprint["layout_family"]}) >= 3)
assert_true("tree and auto contexts can choose different visual systems", rugged.blueprint["visual_motif"] != auto.blueprint["visual_motif"] or rugged.blueprint["palette"] != auto.blueprint["palette"])
assert_true("provider boundary records context director mode", premium.generation_mode == "CONTEXT_DIRECTOR_V1")

site = build_site_model(business(), premium.blueprint)
assert_true("render model preserves canonical business name", site["name"] == "Herb Clark Tree Services")
assert_true("render model preserves public rating", site["rating"] == 4.8 and site["reviews"] == 143)
assert_true("render model creates safe tel href", site["phone_href"].startswith("tel:"))
assert_true("reputation section uses measured public data", "reputation" in site["sections"])

no_rep = build_site_model(business(rating=None, reviews=0), minimal.blueprint)
assert_true("missing reputation disappears instead of fabricating proof", "reputation" not in no_rep["sections"])

preview = (ROOT / "templates" / "prospect_concept_preview.html").read_text(encoding="utf-8")
for forbidden in (
    "v13 deliberately refuses",
    "Owner-verified services will become",
    "This concept demonstrates layout",
    "Final services, claims, service area",
):
    assert_true(f"prospect preview omits internal engineering phrase: {forbidden}", forbidden not in preview)

bad = dict(premium.blueprint)
bad["layout_family"] = "<script>alert(1)</script>"
try:
    validate_blueprint(bad)
except BlueprintValidationError:
    print("PASS: invalid executable-like design value fails closed")
else:
    raise AssertionError("invalid blueprint unexpectedly passed")

assert_true("live publishing remains absent from creative director", "publish" not in (ROOT / "services" / "v13_creative_director.py").read_text(encoding="utf-8").lower())
print("ALL V13 CREATIVE DIRECTOR TESTS PASSED")
