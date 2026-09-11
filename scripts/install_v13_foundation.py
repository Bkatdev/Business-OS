from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def die(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        die(f"Missing required file: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"Expected exactly one anchor for {label}; found {count}. No changes were applied to that file.")
    return text.replace(old, new, 1)


def git_output(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception:
        return "(git unavailable)"


def backup_files(files: list[str]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = ROOT / ".v13_backups" / stamp
    for rel in files:
        src = ROOT / rel
        if src.exists():
            dst = backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return backup_root


print("Business OS v13 - Prospect-to-Demo Foundation Installer")
print(f"Repository: {ROOT}")
print()

if ROOT.name != "Business-OS":
    die("Run this only from the authoritative Business-OS repository.")

required = [
    "app.py",
    "services/db.py",
    "services/scoring.py",
    "services/website_auditor.py",
    "templates/base.html",
    "templates/business_detail.html",
]
for rel in required:
    read(rel)

# Abort if this installer was already applied. This keeps reruns deterministic.
if (ROOT / "services/v13_blueprints.py").exists():
    die("v13 foundation files already exist. Do not re-run this installer blindly.")

print("Current branch:")
print(git_output("branch", "--show-current"))
print("Current working-tree changes (informational; installer will not commit):")
status = git_output("status", "--short")
print(status or "(clean)")
print()

backup_root = backup_files(required)
print(f"Backup created: {backup_root}")

# -----------------------------------------------------------------------------
# v13 blueprint engine
# -----------------------------------------------------------------------------
write(
    "services/v13_blueprints.py",
    r'''"""Business OS v13 - safe Site Blueprint foundation.

AI/procedural design output is a proposal. Only validated allowlisted design
choices may be persisted or rendered. No arbitrary HTML/CSS/JS belongs here.
"""

from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION = 1

PERSONALITIES = (
    "premium",
    "rugged",
    "editorial",
    "minimal",
    "friendly_local",
    "service_first",
)
HERO_LAYOUTS = (
    "split",
    "centered",
    "editorial",
    "service_first",
    "panel",
)
NAV_STYLES = ("quiet", "solid", "floating")
TYPE_SYSTEMS = ("modern", "editorial", "humanist", "strong")
PALETTES = ("forest", "slate", "sand", "navy", "earth", "mono")
SPACING = ("compact", "comfortable", "spacious")
RADII = ("square", "soft", "rounded")
SURFACES = ("clean", "layered", "contrast", "warm")
CTA_STYLES = ("solid", "outline", "high_contrast")
SECTION_VARIANTS = {
    "business_snapshot": ("band", "cards", "editorial"),
    "category": ("statement", "cards", "split"),
    "contact": ("panel", "split", "minimal"),
}
ALLOWED_SECTIONS = ("business_snapshot", "category", "contact")

MAX_BRIEF = 700


class BlueprintValidationError(ValueError):
    pass


def clean_brief(value: str) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:MAX_BRIEF]


def _choose(options, seed: int, offset: int):
    return options[(seed + offset) % len(options)]


def _seed_for(business, brief: str, concept_number: int) -> int:
    raw = "|".join(
        [
            str(business.get("id", "")),
            str(business.get("name", "")),
            str(business.get("category", "")),
            str(brief or ""),
            str(concept_number),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def generate_blueprint(business, creative_brief="", concept_number=1):
    """Generate a varied safe blueprint without inventing business facts.

    This is the local development designer. A future LLM provider must return
    the same schema and pass validate_blueprint() before persistence.
    """
    brief = clean_brief(creative_brief)
    seed = _seed_for(dict(business), brief, int(concept_number or 1))

    personality = _choose(PERSONALITIES, seed, 1)
    hero_layout = _choose(HERO_LAYOUTS, seed, 3)
    nav_style = _choose(NAV_STYLES, seed, 5)
    type_system = _choose(TYPE_SYSTEMS, seed, 7)
    palette = _choose(PALETTES, seed, 11)
    spacing = _choose(SPACING, seed, 13)
    radius = _choose(RADII, seed, 17)
    surface = _choose(SURFACES, seed, 19)
    cta_style = _choose(CTA_STYLES, seed, 23)

    sections = list(ALLOWED_SECTIONS)
    if seed % 2:
        sections = ["category", "business_snapshot", "contact"]
    if seed % 5 == 0:
        sections = ["business_snapshot", "contact", "category"]

    blueprint = {
        "schema_version": SCHEMA_VERSION,
        "personality": personality,
        "hero_layout": hero_layout,
        "nav_style": nav_style,
        "type_system": type_system,
        "palette": palette,
        "spacing": spacing,
        "radius": radius,
        "surface": surface,
        "cta_style": cta_style,
        "section_order": sections,
        "section_variants": {
            name: _choose(variants, seed, 29 + index * 3)
            for index, (name, variants) in enumerate(SECTION_VARIANTS.items())
        },
        "creative_brief": brief,
    }

    validate_blueprint(blueprint)
    return blueprint


def validate_blueprint(blueprint):
    if not isinstance(blueprint, dict):
        raise BlueprintValidationError("Blueprint must be an object.")

    if blueprint.get("schema_version") != SCHEMA_VERSION:
        raise BlueprintValidationError("Unsupported blueprint schema version.")

    checks = {
        "personality": PERSONALITIES,
        "hero_layout": HERO_LAYOUTS,
        "nav_style": NAV_STYLES,
        "type_system": TYPE_SYSTEMS,
        "palette": PALETTES,
        "spacing": SPACING,
        "radius": RADII,
        "surface": SURFACES,
        "cta_style": CTA_STYLES,
    }
    for key, allowed in checks.items():
        if blueprint.get(key) not in allowed:
            raise BlueprintValidationError(f"Unsupported {key}.")

    order = blueprint.get("section_order")
    if not isinstance(order, list) or not order:
        raise BlueprintValidationError("section_order must be a non-empty list.")
    if len(order) != len(set(order)):
        raise BlueprintValidationError("section_order cannot contain duplicates.")
    if any(section not in ALLOWED_SECTIONS for section in order):
        raise BlueprintValidationError("Unsupported section in section_order.")

    variants = blueprint.get("section_variants")
    if not isinstance(variants, dict):
        raise BlueprintValidationError("section_variants must be an object.")
    for section, allowed in SECTION_VARIANTS.items():
        if variants.get(section) not in allowed:
            raise BlueprintValidationError(f"Unsupported variant for {section}.")

    brief = clean_brief(blueprint.get("creative_brief", ""))
    lowered = brief.lower()
    dangerous = ("<script", "javascript:", "data:text/html", "onerror=", "onclick=")
    if any(token in lowered for token in dangerous):
        raise BlueprintValidationError("Creative brief contains executable markup patterns.")

    return True


def blueprint_json(blueprint):
    validate_blueprint(blueprint)
    return json.dumps(blueprint, sort_keys=True, separators=(",", ":"))
''',
)

# -----------------------------------------------------------------------------
# Sales intelligence
# -----------------------------------------------------------------------------
write(
    "services/v13_sales.py",
    r'''"""Business OS v13 - evidence-backed prospect sales intelligence."""

from __future__ import annotations

from services.scoring import opportunity_analysis


def _bool(business, key):
    try:
        return bool(business[key])
    except (KeyError, IndexError, TypeError):
        return False


def _value(business, key, default=""):
    try:
        value = business[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def build_sales_brief(business):
    """Return sales guidance that never upgrades unknown evidence into fact."""
    analysis = opportunity_analysis(business)
    audit_status = str(_value(business, "audit_status", "not_audited") or "not_audited")
    completed = audit_status == "completed"

    pitch_points = []
    cautions = []
    discovery_questions = []

    reviews = int(_value(business, "reviews", 0) or 0)
    if reviews >= 100:
        pitch_points.append(
            "The business has substantial public review volume, so the conversation can focus on whether its website experience matches the strength of its reputation."
        )

    if not completed:
        cautions.append(
            "Website weaknesses are not scored until the public-site audit completes. Do not pitch missing features as facts yet."
        )
        return {
            "analysis": analysis,
            "recommended_plan": "Audit first",
            "plan_reason": "Business OS does not yet have enough website evidence to recommend a starting package responsibly.",
            "pitch_points": pitch_points,
            "cautions": cautions,
            "discovery_questions": [
                "What is the biggest problem with the current website today?",
                "How do new customers usually contact the business?",
            ],
            "next_action": "Complete the website audit before building the sales angle.",
            "complete_plan_note": "Complete automation requires owner discovery and is never prescribed from public web evidence alone.",
        }

    if not _bool(business, "estimate_form"):
        pitch_points.append(
            "No online estimate/quote form was detected in the pages Business OS inspected. Show the owner a clearer request path, while describing this only as 'not detected.'"
        )
    if not _bool(business, "online_booking"):
        pitch_points.append(
            "No actual online booking integration was detected. Ask whether scheduling is intentionally phone-based before proposing scheduling automation."
        )
    if not _bool(business, "website_chat"):
        pitch_points.append(
            "No website chat widget was detected. Treat this as a possible response-speed opportunity, not proof that the company misses leads."
        )
    if _bool(business, "emergency_service"):
        pitch_points.append(
            "Emergency/high-intent service language was detected. Fast intake and clear escalation may be valuable topics to discuss with the owner."
        )
    if _bool(business, "scheduling_mentioned"):
        pitch_points.append(
            "Appointment/scheduling language was detected. Ask how those requests are handled after a visitor expresses intent."
        )

    front_office_signal = (
        _bool(business, "emergency_service")
        or _bool(business, "scheduling_mentioned")
    ) and (
        not _bool(business, "estimate_form")
        or not _bool(business, "online_booking")
    )

    if front_office_signal:
        recommended_plan = "Front Office"
        plan_reason = (
            "The public site shows higher-intent service or scheduling signals plus an intake/booking gap. Lead with the website concept, then validate front-office workflow needs with the owner."
        )
    else:
        recommended_plan = "Website"
        plan_reason = (
            "The strongest evidence currently concerns the web experience. Start with the managed website offer and earn the right to discover deeper operational needs."
        )

    discovery_questions.extend(
        [
            "When someone submits a request or calls while you are busy, what happens next?",
            "How quickly do new inquiries usually receive a response?",
            "Who owns follow-up when an estimate has not been scheduled yet?",
            "Would you rather start with the website only or have inquiries organized in one place too?",
        ]
    )

    cautions.extend(
        [
            "Do not claim the company is losing revenue or missing calls without owner-confirmed or measured evidence.",
            "Do not present 'not detected' as proof a capability does not exist outside the inspected pages.",
        ]
    )

    return {
        "analysis": analysis,
        "recommended_plan": recommended_plan,
        "plan_reason": plan_reason,
        "pitch_points": pitch_points,
        "cautions": cautions,
        "discovery_questions": discovery_questions,
        "next_action": "Generate a private website concept and use it as the opening sales asset.",
        "complete_plan_note": "Business OS Complete remains a discovery-led upgrade; public website evidence alone is insufficient to recommend production receptionist, messaging or scheduling automation.",
    }
''',
)

# -----------------------------------------------------------------------------
# Concept persistence
# -----------------------------------------------------------------------------
write(
    "services/v13_concepts.py",
    r'''"""Business OS v13 - immutable prospect website concepts."""

from __future__ import annotations

import json

from services.db import now_iso
from services.v13_blueprints import blueprint_json, validate_blueprint

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
        result["blueprint"] = json.loads(result.get("blueprint_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ConceptError("Stored concept blueprint is invalid JSON.")
    validate_blueprint(result["blueprint"])
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
''',
)

# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
write(
    "templates/prospect_concept.html",
    r'''{% extends "base.html" %}
{% block title %}Website Concepts · {{ business.name }} · Business OS{% endblock %}
{% block heading %}Prospect-to-Demo Studio{% endblock %}

{% block actions %}
<a class="btn secondary" href="{{ url_for('business_detail', bid=business.id) }}">← Prospect Intelligence</a>
{% endblock %}

{% block content %}
<div class="v13-workspace-hero">
  <div>
    <span class="section-kicker">PRIVATE SALES ASSET</span>
    <h2>Turn evidence into something {{ business.name }} can see.</h2>
    <p>Build private website directions around public prospect information. Nothing here is published, owner-approved, or production truth.</p>
  </div>
  <div class="v13-truth-badge"><strong>PUBLIC / UNVERIFIED</strong><span>Confirm with owner before launch</span></div>
</div>

<div class="v13-sales-grid">
  <section class="panel v9-panel">
    <div class="v9-section-head"><div><span class="section-kicker">SALES BRIEF</span><h3>{{ sales.recommended_plan }} is the starting conversation</h3><p>{{ sales.plan_reason }}</p></div></div>
    {% if sales.pitch_points %}
    <div class="v13-stack">
      {% for item in sales.pitch_points %}<div class="v13-insight"><span>Pitch angle</span><p>{{ item }}</p></div>{% endfor %}
    </div>
    {% else %}
    <div class="v9-empty"><strong>No evidence-backed pitch angle yet.</strong><span>Run the website audit before treating weaknesses as facts.</span></div>
    {% endif %}
  </section>

  <section class="panel v9-panel">
    <span class="section-kicker">DO NOT OVERCLAIM</span><h3>Keep the sale truthful.</h3>
    <div class="v13-stack compact">
      {% for item in sales.cautions %}<div class="v13-caution">{{ item }}</div>{% endfor %}
      <div class="v13-caution">{{ sales.complete_plan_note }}</div>
    </div>
  </section>
</div>

<div class="v13-main-grid">
  <section class="panel v9-panel">
    <div class="v9-section-head"><div><span class="section-kicker">CREATE CONCEPT</span><h3>Give the design engine direction</h3><p>Describe the feeling you want. Business OS changes design decisions, not business facts.</p></div></div>
    <form method="POST" action="{{ url_for('generate_prospect_concept', bid=business.id) }}" class="v13-concept-form">
      <label><span>Creative direction</span><textarea name="creative_brief" maxlength="700" rows="5" placeholder="Example: Established local contractor, premium but not flashy. Strong mobile-first hero, confident typography, warm natural feel, make contacting them effortless."></textarea></label>
      <div class="v13-form-footer"><small>v13 foundation currently uses the safe local designer. The external AI provider plugs into this same validated blueprint contract next.</small><button class="btn" type="submit">Generate New Concept</button></div>
    </form>
  </section>

  <section class="panel v9-panel">
    <span class="section-kicker">DISCOVERY</span><h3>Questions for the owner</h3>
    <div class="v13-question-list">{% for item in sales.discovery_questions %}<div><span>{{ loop.index }}</span><p>{{ item }}</p></div>{% endfor %}</div>
  </section>
</div>

<section class="panel v9-panel v13-history-panel">
  <div class="v9-section-head"><div><span class="section-kicker">CONCEPT HISTORY</span><h3>Private directions</h3><p>Each generation is immutable and tenant-bound.</p></div><span class="count-bubble">{{ concepts|length }}</span></div>
  {% if concepts %}
  <div class="v13-concept-list">
    {% for concept in concepts %}
    <article>
      <div><span class="v13-concept-number">Concept {{ concept.concept_number }}</span><strong>{{ concept.blueprint.personality|replace('_',' ')|title }} · {{ concept.blueprint.hero_layout|replace('_',' ')|title }}</strong><small>{{ concept.blueprint.palette|title }} · {{ concept.blueprint.type_system|title }} · {{ concept.created_at }}</small></div>
      <div class="v13-concept-actions"><span class="v12-chip">{{ concept.truth_state|replace('_',' ')|title }}</span><a class="btn secondary" href="{{ url_for('prospect_concept_preview', bid=business.id, concept_id=concept.id) }}" target="_blank" rel="noopener">Open Preview ↗</a></div>
    </article>
    {% endfor %}
  </div>
  {% else %}
  <div class="v9-empty large"><strong>No concept yet.</strong><span>Generate the first private direction above.</span></div>
  {% endif %}
</section>
{% endblock %}
''',
)

write(
    "templates/prospect_concept_preview.html",
    r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{{ business.name }} · Private Website Concept</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='v13.css') }}?v=1">
</head>
<body class="v13-site palette-{{ bp.palette }} type-{{ bp.type_system }} spacing-{{ bp.spacing }} radius-{{ bp.radius }} surface-{{ bp.surface }} personality-{{ bp.personality }}">
  <div class="v13-demo-banner"><strong>PRIVATE CONCEPT</strong><span>Public business details shown here are not owner-verified. Nothing is published.</span></div>
  <header class="v13-site-nav nav-{{ bp.nav_style }}">
    <a class="v13-site-brand" href="#top">{{ business.name }}</a>
    <nav><a href="#about">About</a><a href="#contact">Contact</a><a class="v13-nav-cta cta-{{ bp.cta_style }}" href="#contact">Request Details</a></nav>
  </header>

  <main id="top">
    <section class="v13-public-hero hero-{{ bp.hero_layout }}">
      <div class="v13-hero-copy">
        <span class="v13-eyebrow">{{ business.category or 'Local Service Business' }}{% if business.city %} · {{ business.city }}{% endif %}</span>
        <h1>{{ business.name }}</h1>
        <p>A private design concept built around the public business information currently available to Business OS. Final services, claims, service area and company details require owner confirmation before launch.</p>
        <div class="v13-hero-actions"><a class="v13-primary cta-{{ bp.cta_style }}" href="#contact">Start a Conversation</a><a class="v13-secondary" href="#about">See the concept</a></div>
      </div>
      <div class="v13-hero-art" aria-hidden="true"><div></div><span>{{ business.category or 'LOCAL SERVICE' }}</span></div>
    </section>

    {% for section in bp.section_order %}
      {% if section == 'business_snapshot' %}
      <section id="about" class="v13-public-section snapshot-{{ bp.section_variants.business_snapshot }}">
        <div class="v13-section-heading"><span>BUSINESS SNAPSHOT</span><h2>Clear information. Clear next step.</h2></div>
        <div class="v13-snapshot-grid">
          <div><span>Business</span><strong>{{ business.name }}</strong></div>
          <div><span>Category</span><strong>{{ business.category or 'Local Service Business' }}</strong></div>
          <div><span>Location</span><strong>{{ business.city or 'Confirm with owner' }}</strong></div>
          <div><span>Contact</span><strong>{{ business.phone or 'Confirm with owner' }}</strong></div>
        </div>
      </section>
      {% elif section == 'category' %}
      <section class="v13-public-section category-{{ bp.section_variants.category }}">
        <div class="v13-section-heading"><span>WHAT THEY DO</span><h2>{{ business.category or 'Local service work' }}</h2><p>v13 deliberately refuses to fabricate a service catalog from a category label. Verified services can replace this section after owner review.</p></div>
        <div class="v13-category-card"><strong>{{ business.category or 'Service information pending confirmation' }}</strong><span>Owner-verified services will become the canonical source of truth before production.</span></div>
      </section>
      {% elif section == 'contact' %}
      <section id="contact" class="v13-public-section contact-{{ bp.section_variants.contact }}">
        <div><span class="v13-eyebrow">NEXT STEP</span><h2>Make it easy to start the conversation.</h2><p>This concept demonstrates layout and conversion flow without pretending an unverified prospect form is already production-ready.</p></div>
        <div class="v13-contact-card"><strong>{{ business.name }}</strong>{% if business.phone %}<span>{{ business.phone }}</span>{% endif %}{% if business.city %}<span>{{ business.city }}</span>{% endif %}<a href="#top">Back to top ↑</a></div>
      </section>
      {% endif %}
    {% endfor %}
  </main>
  <footer class="v13-site-footer"><strong>{{ business.name }}</strong><span>Private Business OS concept · not published</span></footer>
</body>
</html>
''',
)

# -----------------------------------------------------------------------------
# v13 CSS. The public concept surface intentionally has its own design tokens.
# -----------------------------------------------------------------------------
write(
    "static/v13.css",
    r'''/* Business OS v13 — Prospect-to-Demo foundation */
.v13-workspace-hero{display:flex;align-items:center;justify-content:space-between;gap:28px;padding:30px 32px;border-radius:24px;background:linear-gradient(135deg,#123c31,#1e5546);color:#fff;margin-bottom:18px}.v13-workspace-hero h2{font-size:31px;margin:7px 0}.v13-workspace-hero p{max-width:760px;color:rgba(255,255,255,.76);margin:0}.v13-truth-badge{min-width:190px;padding:16px 18px;border:1px solid rgba(255,255,255,.18);border-radius:16px;background:rgba(255,255,255,.08)}.v13-truth-badge strong,.v13-truth-badge span{display:block}.v13-truth-badge strong{font-size:11px;letter-spacing:.1em}.v13-truth-badge span{font-size:11px;opacity:.7;margin-top:5px}.v13-sales-grid,.v13-main-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(300px,.7fr);gap:18px;margin-bottom:18px}.v13-stack{display:grid;gap:10px}.v13-stack.compact{gap:8px}.v13-insight,.v13-caution{border:1px solid #e3ebe7;border-radius:14px;padding:14px 15px;background:#fbfdfc}.v13-insight span{display:block;font-size:9px;font-weight:850;letter-spacing:.11em;color:#5c756b}.v13-insight p{margin:5px 0 0!important}.v13-caution{font-size:12px;line-height:1.55;background:#fffaf1;border-color:#eee2c8}.v13-concept-form label{display:grid;gap:8px}.v13-concept-form label>span{font-size:12px;font-weight:800}.v13-concept-form textarea{width:100%;box-sizing:border-box;padding:13px 14px;border:1px solid #d9e2de;border-radius:13px;background:#fbfcfb;font:inherit;resize:vertical}.v13-form-footer{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-top:14px}.v13-form-footer small{max-width:560px;color:#6b7b75}.v13-question-list{display:grid}.v13-question-list>div{display:grid;grid-template-columns:28px 1fr;gap:10px;padding:12px 0;border-top:1px solid #e7ecea}.v13-question-list>div:first-child{border-top:0}.v13-question-list span{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:#edf4f1;font-size:10px;font-weight:850}.v13-question-list p{margin:2px 0!important;font-size:12px}.v13-history-panel{margin-top:18px}.v13-concept-list{display:grid}.v13-concept-list article{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:15px 2px;border-top:1px solid #e7ecea}.v13-concept-list article:first-child{border-top:0}.v13-concept-list strong,.v13-concept-list small{display:block}.v13-concept-list small{color:#6b7b75;margin-top:3px}.v13-concept-number{display:block;font-size:9px;font-weight:850;letter-spacing:.11em;color:#678078;margin-bottom:4px}.v13-concept-actions{display:flex;gap:9px;align-items:center}
@media(max-width:1000px){.v13-sales-grid,.v13-main-grid{grid-template-columns:1fr}.v13-workspace-hero{align-items:flex-start;flex-direction:column}.v13-truth-badge{min-width:0}.v13-form-footer{align-items:flex-start;flex-direction:column}.v13-concept-list article{align-items:flex-start;flex-direction:column}}

/* Isolated private website concept surface */
.v13-site{--ink:#17221e;--muted:#627069;--paper:#fff;--soft:#f3f5f3;--accent:#1d5b45;--accent2:#dce9e2;--line:rgba(23,34,30,.13);margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif}.v13-site.palette-navy{--ink:#111b2c;--accent:#183a68;--accent2:#dfe8f4;--soft:#f2f5f9}.v13-site.palette-slate{--ink:#20272b;--accent:#42545e;--accent2:#e4eaed;--soft:#f4f6f7}.v13-site.palette-sand{--ink:#2e281f;--accent:#8a6233;--accent2:#efe3cf;--soft:#faf6ef}.v13-site.palette-earth{--ink:#2b241e;--accent:#6a4c36;--accent2:#eadfd4;--soft:#f8f4ef}.v13-site.palette-mono{--ink:#151515;--accent:#151515;--accent2:#e9e9e9;--soft:#f5f5f5}.v13-site.type-editorial{font-family:Georgia,'Times New Roman',serif}.v13-site.type-humanist{font-family:'Trebuchet MS',Arial,sans-serif}.v13-site.type-strong{font-family:Arial,Helvetica,sans-serif;font-weight:500}.v13-demo-banner{display:flex;justify-content:center;gap:12px;align-items:center;padding:8px 16px;background:#111;color:#fff;font:11px Arial,sans-serif;letter-spacing:.02em}.v13-demo-banner strong{font-size:9px;letter-spacing:.13em}.v13-demo-banner span{opacity:.72}.v13-site-nav{max-width:1280px;margin:0 auto;padding:22px 34px;display:flex;align-items:center;justify-content:space-between;gap:24px}.v13-site-nav.nav-floating{margin-top:18px;border:1px solid var(--line);border-radius:999px;padding:13px 18px;background:rgba(255,255,255,.9)}.v13-site-nav.nav-solid{max-width:none;padding-left:max(34px,calc((100vw - 1212px)/2));padding-right:max(34px,calc((100vw - 1212px)/2));background:var(--ink);color:#fff}.v13-site-nav.nav-solid a{color:inherit}.v13-site-brand{font-weight:850;text-decoration:none;color:inherit;letter-spacing:-.02em}.v13-site-nav nav{display:flex;align-items:center;gap:22px}.v13-site-nav nav a{text-decoration:none;color:inherit;font-size:13px}.v13-nav-cta,.v13-primary{padding:11px 16px;border-radius:999px;background:var(--accent);color:#fff!important}.v13-nav-cta.cta-outline,.v13-primary.cta-outline{background:transparent;color:var(--accent)!important;border:1px solid var(--accent)}.v13-nav-cta.cta-high_contrast,.v13-primary.cta-high_contrast{background:var(--ink);color:#fff!important}.v13-public-hero{max-width:1280px;margin:18px auto 0;padding:74px 34px 86px;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(340px,.9fr);gap:58px;align-items:center}.v13-public-hero.hero-centered{display:block;text-align:center;max-width:950px}.v13-public-hero.hero-centered .v13-hero-copy p{margin-left:auto;margin-right:auto}.v13-public-hero.hero-centered .v13-hero-actions{justify-content:center}.v13-public-hero.hero-centered .v13-hero-art{display:none}.v13-public-hero.hero-editorial{grid-template-columns:minmax(0,.8fr) minmax(420px,1.2fr);padding-top:95px;padding-bottom:100px}.v13-public-hero.hero-service_first{background:var(--soft);border-radius:30px;margin-top:28px;padding-left:48px;padding-right:48px}.v13-public-hero.hero-panel .v13-hero-copy{padding:44px;background:var(--ink);color:#fff;border-radius:26px}.v13-public-hero.hero-panel .v13-hero-copy p{color:rgba(255,255,255,.72)}.v13-eyebrow{display:block;font:800 10px Arial,sans-serif;letter-spacing:.14em;color:var(--accent);text-transform:uppercase}.v13-hero-copy h1{font-size:clamp(48px,6vw,84px);line-height:.98;letter-spacing:-.055em;margin:16px 0 20px}.v13-hero-copy p{max-width:680px;font-size:17px;line-height:1.7;color:var(--muted)}.v13-hero-actions{display:flex;gap:11px;align-items:center;margin-top:28px}.v13-hero-actions a{text-decoration:none;font:800 12px Arial,sans-serif}.v13-secondary{padding:11px 15px;color:var(--ink);border-bottom:1px solid var(--line)}.v13-hero-art{min-height:430px;border-radius:28px;background:linear-gradient(145deg,var(--accent2),var(--soft));position:relative;overflow:hidden}.v13-hero-art div{position:absolute;width:270px;height:270px;border-radius:50%;background:var(--accent);opacity:.83;right:-35px;top:-40px}.v13-hero-art:after{content:'';position:absolute;width:190px;height:190px;border:1px solid var(--accent);left:42px;bottom:50px;transform:rotate(18deg)}.v13-hero-art span{position:absolute;left:32px;bottom:28px;font:850 11px Arial,sans-serif;letter-spacing:.16em}.v13-public-section{max-width:1212px;margin:0 auto;padding:82px 34px;border-top:1px solid var(--line)}.v13-section-heading{max-width:720px}.v13-section-heading>span{font:850 9px Arial,sans-serif;letter-spacing:.15em;color:var(--accent)}.v13-section-heading h2{font-size:clamp(34px,4vw,54px);line-height:1.05;letter-spacing:-.04em;margin:10px 0}.v13-section-heading p{color:var(--muted);line-height:1.7}.v13-snapshot-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:34px}.v13-snapshot-grid>div{padding:24px;border:1px solid var(--line);border-radius:18px;background:var(--paper)}.v13-snapshot-grid span,.v13-snapshot-grid strong{display:block}.v13-snapshot-grid span{font:800 9px Arial,sans-serif;letter-spacing:.12em;color:var(--muted);margin-bottom:8px}.snapshot-band .v13-snapshot-grid{background:var(--ink);padding:12px;border-radius:22px}.snapshot-band .v13-snapshot-grid>div{background:transparent;color:#fff;border-color:rgba(255,255,255,.12)}.snapshot-editorial .v13-snapshot-grid>div{border-width:0 0 1px;border-radius:0;padding-left:0}.v13-category-card{margin-top:30px;padding:34px;border-radius:22px;background:var(--soft);display:flex;justify-content:space-between;gap:24px}.v13-category-card strong{font-size:22px}.v13-category-card span{max-width:540px;color:var(--muted);line-height:1.6}.category-split{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:60px}.category-split .v13-category-card{margin-top:0}.category-statement .v13-category-card{background:var(--accent);color:#fff}.category-statement .v13-category-card span{color:rgba(255,255,255,.72)}.contact-panel{background:var(--ink);color:#fff;max-width:1144px;border:0;border-radius:28px;margin-bottom:60px}.contact-panel p{color:rgba(255,255,255,.7)}.contact-split{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr);gap:50px}.v13-contact-card{padding:26px;border:1px solid var(--line);border-radius:20px;background:var(--paper);color:var(--ink);display:grid;gap:8px}.v13-contact-card span{color:var(--muted)}.v13-contact-card a{margin-top:10px;color:var(--accent);font-weight:800}.v13-site-footer{display:flex;justify-content:space-between;gap:20px;padding:28px max(34px,calc((100vw - 1212px)/2));background:var(--soft);font-size:12px;color:var(--muted)}.v13-site.radius-square *{border-radius:0!important}.v13-site.radius-rounded .v13-hero-art,.v13-site.radius-rounded .v13-public-hero.hero-service_first,.v13-site.radius-rounded .contact-panel{border-radius:42px}.v13-site.spacing-compact .v13-public-section{padding-top:58px;padding-bottom:58px}.v13-site.spacing-spacious .v13-public-section{padding-top:108px;padding-bottom:108px}
@media(max-width:850px){.v13-demo-banner{align-items:flex-start;flex-direction:column;gap:2px}.v13-site-nav nav a:not(.v13-nav-cta){display:none}.v13-site-nav{padding:18px 20px}.v13-site-nav.nav-floating{margin:12px 12px 0}.v13-public-hero,.v13-public-hero.hero-editorial,.category-split,.contact-split{grid-template-columns:1fr}.v13-public-hero{padding:48px 20px 62px;gap:30px}.v13-public-hero.hero-service_first{margin:14px 12px 0;padding:38px 24px}.v13-public-hero.hero-panel .v13-hero-copy{padding:28px}.v13-hero-art{min-height:280px}.v13-public-section{padding:60px 20px}.v13-snapshot-grid{grid-template-columns:1fr 1fr}.v13-category-card{align-items:flex-start;flex-direction:column}.v13-site-footer{padding:24px 20px;flex-direction:column}.v13-hero-copy h1{font-size:48px}}@media(max-width:520px){.v13-snapshot-grid{grid-template-columns:1fr}.v13-hero-actions{align-items:flex-start;flex-direction:column}}
''',
)

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
write(
    "scripts/test_v13_foundation.py",
    r'''from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.v13_blueprints import BlueprintValidationError, generate_blueprint, validate_blueprint
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
    assert json.loads(raw)["schema_version"] == 1
    print("PASS: immutable concept stores validated blueprint JSON")
    conn.close()

    print("ALL V13 FOUNDATION TESTS PASSED")


if __name__ == "__main__":
    main()
''',
)

# -----------------------------------------------------------------------------
# Patch db.py so schema is created during normal initialization.
# -----------------------------------------------------------------------------
db = read("services/db.py")
db_anchor = '''    # ---- v12: Website Studio ------------------------------------------\n    # Website Studio owns presentation/draft state while continuing to\n    # reference canonical Business OS configuration and tenant identity.\n    from services.website_studio import ensure_website_studio_schema\n    ensure_website_studio_schema(con)\n\n    con.commit()\n'''
db_replacement = '''    # ---- v12: Website Studio ------------------------------------------\n    # Website Studio owns presentation/draft state while continuing to\n    # reference canonical Business OS configuration and tenant identity.\n    from services.website_studio import ensure_website_studio_schema\n    ensure_website_studio_schema(con)\n\n    # ---- v13: Prospect-to-Demo foundation -----------------------------\n    # Immutable private website concepts are separate from production\n    # publishing and remain bound to canonical business ownership.\n    from services.v13_concepts import ensure_v13_schema\n    ensure_v13_schema(con)\n\n    con.commit()\n'''
db = replace_once(db, db_anchor, db_replacement, "db v13 schema hook")
write("services/db.py", db)

# -----------------------------------------------------------------------------
# Patch app imports + routes + startup schema.
# -----------------------------------------------------------------------------
app = read("app.py")
import_anchor = '''from services.website_renderer import (\n    WebsiteRenderNotFound,\n    build_current_draft_render_model,\n    build_preview_render_model,\n)\n'''
import_replacement = import_anchor + '''from services.v13_blueprints import generate_blueprint\nfrom services.v13_concepts import (\n    ConceptNotFound,\n    create_concept,\n    ensure_v13_schema,\n    get_concept_for_business,\n    list_concepts,\n    next_concept_number,\n)\nfrom services.v13_sales import build_sales_brief\n'''
app = replace_once(app, import_anchor, import_replacement, "app v13 imports")

routes_anchor = '''@app.route("/audits")\ndef audits():\n'''
routes = r'''@app.route("/business/<int:bid>/concept")
def prospect_concept_workspace(bid):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    sales = build_sales_brief(business)
    concepts = list_concepts(conn, bid)
    conn.close()
    return render_template(
        "prospect_concept.html",
        business=dict(business),
        sales=sales,
        concepts=concepts,
    )


@app.route("/business/<int:bid>/concept/generate", methods=["POST"])
def generate_prospect_concept(bid):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404

    creative_brief = request.form.get("creative_brief", "").strip()
    concept_number = next_concept_number(conn, bid)
    try:
        blueprint = generate_blueprint(dict(business), creative_brief, concept_number)
        concept = create_concept(conn, bid, creative_brief, blueprint, "LOCAL_DESIGNER")
        flash(
            f"Private concept {concept['concept_number']} generated. Nothing was published.",
            "success",
        )
    except Exception as exc:
        flash(f"Concept generation failed safely: {exc}", "error")
    finally:
        conn.close()

    return redirect(url_for("prospect_concept_workspace", bid=bid))


@app.route("/business/<int:bid>/concept/<int:concept_id>/preview")
def prospect_concept_preview(bid, concept_id):
    conn = connect()
    ensure_v13_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    try:
        concept = get_concept_for_business(conn, bid, concept_id)
    except ConceptNotFound:
        conn.close()
        return render_template("404.html"), 404
    conn.close()

    response = render_template(
        "prospect_concept_preview.html",
        business=dict(business),
        concept=concept,
        bp=concept["blueprint"],
    )
    return Response(
        response,
        headers={
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.route("/audits")
def audits():
'''
app = replace_once(app, routes_anchor, routes, "v13 concept routes")

startup_anchor = '''    ensure_execution_schema(conn)\n    conn.close()\n'''
startup_replacement = '''    ensure_execution_schema(conn)\n    ensure_v13_schema(conn)\n    conn.close()\n'''
app = replace_once(app, startup_anchor, startup_replacement, "v13 startup schema")
write("app.py", app)

# -----------------------------------------------------------------------------
# Patch base stylesheet + active Growth navigation.
# -----------------------------------------------------------------------------
base = read("templates/base.html")
css_anchor = '''    <link rel="stylesheet" href="{{ url_for('static', filename='v12.css') }}?v=1">\n'''
css_replacement = css_anchor + '''    <link rel="stylesheet" href="{{ url_for('static', filename='v13.css') }}?v=1">\n'''
base = replace_once(base, css_anchor, css_replacement, "v13 stylesheet")
nav_anchor = '''            <a class="{% if request.endpoint in ['prospects', 'business_detail'] %}active{% endif %}" href="{{ url_for('prospects') }}" title="Prospects">\n'''
nav_replacement = '''            <a class="{% if request.endpoint in ['prospects', 'business_detail', 'prospect_concept_workspace', 'generate_prospect_concept', 'prospect_concept_preview'] %}active{% endif %}" href="{{ url_for('prospects') }}" title="Prospects">\n'''
base = replace_once(base, nav_anchor, nav_replacement, "prospect nav endpoints")
write("templates/base.html", base)

# -----------------------------------------------------------------------------
# Add Concept CTA on Prospect Intelligence.
# -----------------------------------------------------------------------------
detail = read("templates/business_detail.html")
detail_anchor = '''<a\n  class="btn secondary"\n  href="{{ url_for('prospects') }}"\n>\n  ← Prospects\n</a>\n\n<form\n'''
detail_replacement = '''<a\n  class="btn secondary"\n  href="{{ url_for('prospects') }}"\n>\n  ← Prospects\n</a>\n\n<a\n  class="btn secondary"\n  href="{{ url_for('prospect_concept_workspace', bid=business.id) }}"\n>\n  Website Concepts\n</a>\n\n<form\n'''
detail = replace_once(detail, detail_anchor, detail_replacement, "prospect concept CTA")
write("templates/business_detail.html", detail)

print()
print("PASS: v13 Site Blueprint foundation installed")
print("PASS: evidence-backed Sales Brief installed")
print("PASS: immutable tenant-bound private concepts installed")
print("PASS: Prospect-to-Demo workspace + private preview installed")
print("PASS: live publishing remains absent")
print("PASS: live provider/SMS/scheduling gates were not modified")
print()
print("Next verification commands:")
print("  python -m compileall app.py services scripts")
print("  python scripts/test_v12_schema.py")
print("  python scripts/test_v12_renderer.py")
print("  python scripts/test_v13_foundation.py")
print("  git diff --check")
print()
print("Do not commit/tag yet. Visual acceptance and the real AI provider workstream come next.")
