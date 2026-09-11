from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.v13_creative_director import generate_concept_blueprint
from services.v13_site_model import build_site_model


def assert_true(label, value):
    if not value:
        raise AssertionError(label)
    print(f"PASS: {label}")


def business(**overrides):
    row = {
        "id": 4,
        "name": "Example Auto Repair",
        "category": "Auto Repair",
        "city": "Marlboro",
        "phone": "(732) 555-0113",
        "rating": 4.7,
        "reviews": 210,
        "audit_status": "completed",
        "estimate_form": 0,
        "online_booking": 0,
        "website_chat": 0,
        "emergency_service": 0,
        "scheduling_mentioned": 0,
    }
    row.update(overrides)
    return row


director = generate_concept_blueprint(business(), "rugged practical established local shop", 8)
site = build_site_model(business(), director.blueprint)

assert_true("site model keeps canonical name", site["name"] == "Example Auto Repair")
assert_true("site model keeps public location", site["city"] == "Marlboro")
assert_true("site model keeps public reputation", site["rating"] == 4.7 and site["reviews"] == 210)
assert_true("reputation is expressed once as a composed heading", site["reputation_heading"] == "4.7 ★ from 210 public reviews")
assert_true("hero fact panel is based only on existing prospect facts", any(item["value"] == "Auto Repair" for item in site["hero_facts"]))
assert_true("phone action remains a safe tel link", site["phone_href"].startswith("tel:"))

no_rep = build_site_model(business(rating=None, reviews=0), director.blueprint)
assert_true("missing reputation remains omitted", no_rep["reputation_heading"] == "" and "reputation" not in no_rep["sections"])

preview = (ROOT / "templates" / "prospect_concept_preview.html").read_text(encoding="utf-8")
workspace = (ROOT / "templates" / "prospect_concept.html").read_text(encoding="utf-8")
css = (ROOT / "static" / "v13.css").read_text(encoding="utf-8")

for forbidden in (
    "Business OS for this prospect",
    "owner-confirmed",
    "Owner-verified",
    "v13 deliberately refuses",
    "This concept demonstrates",
    "v13-visual",
    "v13-rating-mark",
):
    assert_true(f"prospect-facing template omits prototype/internal artifact: {forbidden}", forbidden not in preview)

assert_true("meaningful public-facts hero panel replaces empty art", "v13-hero-proof" in preview)
assert_true("reputation uses one compact proof component", "v13-review-pill" in preview)
assert_true("operator create action appears before sales summary", workspace.find("v13-create-panel") < workspace.find("v13-sales-summary"))
assert_true("operator workspace no longer uses fragile two-column grid", "v13-operator-grid" not in workspace)
assert_true("operator panels are forced to full available width", "width:100%!important" in css)
assert_true("desktop-to-mobile breakpoint exists", "@media(max-width:900px)" in css)
assert_true("small-phone breakpoint exists", "@media(max-width:540px)" in css)
assert_true("CSS contains no external web asset dependency", "http://" not in css.lower() and "https://" not in css.lower())
assert_true("CSS contains no executable URL", "javascript:" not in css.lower())

print("ALL V13 VISUAL QUALITY TESTS PASSED")
