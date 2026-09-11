"""Business OS v13 - validated website design blueprint contract.

Creative systems may propose only allowlisted design decisions. The renderer owns
HTML/CSS. No model or procedural designer may persist executable website code.
"""

from __future__ import annotations

import json

SCHEMA_VERSION = 2
MAX_BRIEF = 700

PERSONALITIES = (
    "premium",
    "rugged",
    "editorial",
    "minimal",
    "friendly_local",
    "service_first",
)
LAYOUT_FAMILIES = (
    "cinematic",
    "editorial",
    "utility",
    "poster",
    "minimal",
    "local_trust",
)
HERO_LAYOUTS = (
    "split_art",
    "full_statement",
    "offset_editorial",
    "utility_band",
    "poster_grid",
    "quiet_center",
)
NAV_STYLES = ("quiet", "solid", "floating", "utility")
TYPE_SYSTEMS = ("modern", "editorial", "humanist", "industrial", "geometric")
PALETTES = ("forest", "slate", "sand", "navy", "earth", "mono", "copper", "workwear")
SPACING = ("compact", "comfortable", "spacious")
RADII = ("square", "soft", "rounded")
SURFACES = ("clean", "layered", "contrast", "warm")
CTA_STYLES = ("solid", "outline", "high_contrast")
VISUAL_MOTIFS = ("canopy", "contour", "grid", "blueprint", "rings", "beams", "blocks", "none")
COPY_TONES = ("direct", "premium", "editorial", "neighborly", "practical")
DENSITIES = ("lean", "balanced", "detailed")

ALLOWED_SECTIONS = (
    "credibility",
    "category_focus",
    "local_presence",
    "reputation",
    "contact",
)
SECTION_VARIANTS = {
    "credibility": ("strip", "cards", "editorial"),
    "category_focus": ("statement", "split", "feature_band"),
    "local_presence": ("minimal", "panel", "editorial"),
    "reputation": ("score", "band", "editorial"),
    "contact": ("panel", "split", "minimal", "utility"),
}


class BlueprintValidationError(ValueError):
    pass


def clean_brief(value: str) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:MAX_BRIEF]


def validate_blueprint(blueprint):
    if not isinstance(blueprint, dict):
        raise BlueprintValidationError("Blueprint must be an object.")
    if blueprint.get("schema_version") != SCHEMA_VERSION:
        raise BlueprintValidationError("Unsupported blueprint schema version.")

    checks = {
        "personality": PERSONALITIES,
        "layout_family": LAYOUT_FAMILIES,
        "hero_layout": HERO_LAYOUTS,
        "nav_style": NAV_STYLES,
        "type_system": TYPE_SYSTEMS,
        "palette": PALETTES,
        "spacing": SPACING,
        "radius": RADII,
        "surface": SURFACES,
        "cta_style": CTA_STYLES,
        "visual_motif": VISUAL_MOTIFS,
        "copy_tone": COPY_TONES,
        "density": DENSITIES,
    }
    for key, allowed in checks.items():
        if blueprint.get(key) not in allowed:
            raise BlueprintValidationError(f"Unsupported {key}.")

    order = blueprint.get("section_order")
    if not isinstance(order, list) or len(order) < 2:
        raise BlueprintValidationError("section_order must contain at least two sections.")
    if len(order) != len(set(order)):
        raise BlueprintValidationError("section_order cannot contain duplicates.")
    if any(section not in ALLOWED_SECTIONS for section in order):
        raise BlueprintValidationError("Unsupported section in section_order.")
    if "contact" not in order:
        raise BlueprintValidationError("Every concept requires a contact section.")

    variants = blueprint.get("section_variants")
    if not isinstance(variants, dict):
        raise BlueprintValidationError("section_variants must be an object.")
    for section in order:
        allowed = SECTION_VARIANTS[section]
        if variants.get(section) not in allowed:
            raise BlueprintValidationError(f"Unsupported variant for {section}.")

    brief = clean_brief(blueprint.get("creative_brief", ""))
    lowered = brief.lower()
    dangerous = (
        "<script",
        "javascript:",
        "data:text/html",
        "onerror=",
        "onclick=",
        "onload=",
        "<iframe",
    )
    if any(token in lowered for token in dangerous):
        raise BlueprintValidationError("Creative brief contains executable markup patterns.")

    rationale = blueprint.get("design_rationale", [])
    if not isinstance(rationale, list) or len(rationale) > 6:
        raise BlueprintValidationError("design_rationale must be a short list.")
    for item in rationale:
        if not isinstance(item, str) or len(item) > 220:
            raise BlueprintValidationError("Invalid design rationale item.")

    return True




# v1 is a read-compatibility contract only. New concepts must always use v2.
LEGACY_V1_PERSONALITIES = PERSONALITIES
LEGACY_V1_HERO_LAYOUTS = ("split", "centered", "editorial", "service_first", "panel")
LEGACY_V1_NAV_STYLES = ("quiet", "solid", "floating")
LEGACY_V1_TYPE_SYSTEMS = ("modern", "editorial", "humanist", "strong")
LEGACY_V1_PALETTES = ("forest", "slate", "sand", "navy", "earth", "mono")
LEGACY_V1_SECTIONS = ("business_snapshot", "category", "contact")
LEGACY_V1_SECTION_VARIANTS = {
    "business_snapshot": ("band", "cards", "editorial"),
    "category": ("statement", "cards", "split"),
    "contact": ("panel", "split", "minimal"),
}


def _validate_legacy_v1(blueprint):
    """Strictly validate the historical v1 shape before adapting it in memory."""
    if not isinstance(blueprint, dict) or blueprint.get("schema_version") != 1:
        raise BlueprintValidationError("Unsupported legacy blueprint schema version.")

    checks = {
        "personality": LEGACY_V1_PERSONALITIES,
        "hero_layout": LEGACY_V1_HERO_LAYOUTS,
        "nav_style": LEGACY_V1_NAV_STYLES,
        "type_system": LEGACY_V1_TYPE_SYSTEMS,
        "palette": LEGACY_V1_PALETTES,
        "spacing": SPACING,
        "radius": RADII,
        "surface": SURFACES,
        "cta_style": CTA_STYLES,
    }
    for key, allowed in checks.items():
        if blueprint.get(key) not in allowed:
            raise BlueprintValidationError(f"Unsupported legacy {key}.")

    order = blueprint.get("section_order")
    if not isinstance(order, list) or not order:
        raise BlueprintValidationError("Legacy section_order must be a non-empty list.")
    if len(order) != len(set(order)):
        raise BlueprintValidationError("Legacy section_order cannot contain duplicates.")
    if any(section not in LEGACY_V1_SECTIONS for section in order):
        raise BlueprintValidationError("Unsupported legacy section.")

    variants = blueprint.get("section_variants")
    if not isinstance(variants, dict):
        raise BlueprintValidationError("Legacy section_variants must be an object.")
    for section, allowed in LEGACY_V1_SECTION_VARIANTS.items():
        if variants.get(section) not in allowed:
            raise BlueprintValidationError(f"Unsupported legacy variant for {section}.")

    brief = clean_brief(blueprint.get("creative_brief", ""))
    lowered = brief.lower()
    dangerous = ("<script", "javascript:", "data:text/html", "onerror=", "onclick=", "onload=", "<iframe")
    if any(token in lowered for token in dangerous):
        raise BlueprintValidationError("Legacy creative brief contains executable markup patterns.")
    return True


def _legacy_family(blueprint):
    personality = blueprint["personality"]
    hero = blueprint["hero_layout"]
    if personality == "rugged":
        return "poster"
    if personality == "service_first" or hero == "service_first":
        return "utility"
    if personality == "editorial" or hero == "editorial":
        return "editorial"
    if personality == "minimal" or hero == "centered":
        return "minimal"
    if personality == "friendly_local":
        return "local_trust"
    return "cinematic"


def adapt_legacy_v1_blueprint(blueprint):
    """Return a validated v2 runtime view of a valid stored v1 blueprint.

    This function never mutates the input or the database. It exists only so
    immutable v1 concepts remain readable after the v2 Creative Director ships.
    """
    _validate_legacy_v1(blueprint)
    family = _legacy_family(blueprint)

    hero_map = {
        "split": "split_art",
        "centered": "quiet_center",
        "editorial": "offset_editorial",
        "service_first": "utility_band",
        "panel": "full_statement",
    }
    type_map = {"strong": "industrial"}
    section_map = {
        "business_snapshot": "credibility",
        "category": "category_focus",
        "contact": "contact",
    }
    variant_map = {
        "business_snapshot": {"band": "strip", "cards": "cards", "editorial": "editorial"},
        "category": {"statement": "statement", "cards": "feature_band", "split": "split"},
        "contact": {"panel": "panel", "split": "split", "minimal": "minimal"},
    }

    order = [section_map[name] for name in blueprint["section_order"]]
    if "contact" not in order:
        order.append("contact")

    variants = {}
    for old_name in blueprint["section_order"]:
        new_name = section_map[old_name]
        old_variant = blueprint["section_variants"][old_name]
        variants[new_name] = variant_map[old_name][old_variant]
    variants.setdefault("contact", "panel")

    motif_by_palette = {
        "forest": "canopy",
        "slate": "contour",
        "sand": "rings",
        "navy": "blueprint",
        "earth": "blocks",
        "mono": "none",
    }
    tone_by_personality = {
        "premium": "premium",
        "rugged": "direct",
        "editorial": "editorial",
        "minimal": "direct",
        "friendly_local": "neighborly",
        "service_first": "practical",
    }

    adapted = {
        "schema_version": SCHEMA_VERSION,
        "personality": blueprint["personality"],
        "layout_family": family,
        "hero_layout": hero_map[blueprint["hero_layout"]],
        "nav_style": blueprint["nav_style"],
        "type_system": type_map.get(blueprint["type_system"], blueprint["type_system"]),
        "palette": blueprint["palette"],
        "spacing": blueprint["spacing"],
        "radius": blueprint["radius"],
        "surface": blueprint["surface"],
        "cta_style": blueprint["cta_style"],
        "visual_motif": motif_by_palette[blueprint["palette"]],
        "copy_tone": tone_by_personality[blueprint["personality"]],
        "density": "lean" if family == "minimal" else ("detailed" if family == "utility" else "balanced"),
        "section_order": order,
        "section_variants": variants,
        "creative_brief": clean_brief(blueprint.get("creative_brief", "")),
        "design_rationale": ["Legacy v1 concept rendered through the read-only v2 compatibility adapter."],
    }
    validate_blueprint(adapted)
    return adapted


def normalize_stored_blueprint(blueprint):
    """Validate current blueprints or adapt supported legacy blueprints in memory."""
    if not isinstance(blueprint, dict):
        raise BlueprintValidationError("Stored blueprint must be an object.")
    version = blueprint.get("schema_version")
    if version == SCHEMA_VERSION:
        validate_blueprint(blueprint)
        return dict(blueprint), SCHEMA_VERSION, False
    if version == 1:
        return adapt_legacy_v1_blueprint(blueprint), 1, True
    raise BlueprintValidationError("Unsupported stored blueprint schema version.")


def blueprint_json(blueprint):
    validate_blueprint(blueprint)
    return json.dumps(blueprint, sort_keys=True, separators=(",", ":"))


def generate_blueprint(business, creative_brief="", concept_number=1):
    """Backward-compatible entry point retained for v13 foundation tests.

    The Creative Director now owns generation. Import lazily to avoid a module
    cycle while keeping older verification scripts valid.
    """
    from services.v13_creative_director import generate_concept_blueprint

    return generate_concept_blueprint(business, creative_brief, concept_number).blueprint
