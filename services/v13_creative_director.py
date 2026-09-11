"""Business OS v13 - context-aware Creative Director.

This module is the provider boundary for website design decisions. The current
provider is deterministic and local so development is reproducible and safe.
A future external model must return this same blueprint schema and pass the same
validator before anything is stored or rendered.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from services.v13_blueprints import (
    COPY_TONES,
    CTA_STYLES,
    DENSITIES,
    HERO_LAYOUTS,
    LAYOUT_FAMILIES,
    NAV_STYLES,
    PALETTES,
    PERSONALITIES,
    RADII,
    SCHEMA_VERSION,
    SECTION_VARIANTS,
    SPACING,
    SURFACES,
    TYPE_SYSTEMS,
    VISUAL_MOTIFS,
    clean_brief,
    validate_blueprint,
)


@dataclass(frozen=True)
class DirectorResult:
    blueprint: dict
    generation_mode: str


def _value(business, key, default=""):
    try:
        value = business[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def build_fact_packet(business):
    """Return only public prospect facts already held by Business OS."""
    return {
        "id": _value(business, "id", ""),
        "name": str(_value(business, "name", "") or "").strip(),
        "category": str(_value(business, "category", "") or "").strip(),
        "city": str(_value(business, "city", "") or "").strip(),
        "phone": str(_value(business, "phone", "") or "").strip(),
        "rating": _value(business, "rating", None),
        "reviews": _value(business, "reviews", 0),
        "audit_status": str(_value(business, "audit_status", "") or ""),
        "estimate_form": bool(_value(business, "estimate_form", False)),
        "online_booking": bool(_value(business, "online_booking", False)),
        "website_chat": bool(_value(business, "website_chat", False)),
        "emergency_service": bool(_value(business, "emergency_service", False)),
        "scheduling_mentioned": bool(_value(business, "scheduling_mentioned", False)),
    }


def _seed(facts, brief, concept_number):
    raw = "|".join(
        [
            str(facts.get("id", "")),
            facts.get("name", ""),
            facts.get("category", ""),
            facts.get("city", ""),
            brief,
            str(int(concept_number or 1)),
        ]
    )
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)


def _pick(options, seed, offset):
    return options[(seed + offset) % len(options)]


def _contains(text, *terms):
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _category_profile(category):
    text = category.lower()
    if _contains(text, "tree", "landscap", "lawn", "outdoor", "masonry", "excavat"):
        return {
            "personality": "rugged",
            "family": "cinematic",
            "palette": "forest",
            "type": "humanist",
            "motif": "canopy",
            "tone": "practical",
        }
    if _contains(text, "auto", "mechanic", "tire", "collision", "body shop"):
        return {
            "personality": "rugged",
            "family": "poster",
            "palette": "workwear",
            "type": "industrial",
            "motif": "grid",
            "tone": "direct",
        }
    if _contains(text, "plumb", "hvac", "heating", "cooling", "electric", "roof", "contractor"):
        return {
            "personality": "service_first",
            "family": "utility",
            "palette": "navy",
            "type": "geometric",
            "motif": "blueprint",
            "tone": "direct",
        }
    if _contains(text, "law", "attorney", "financial", "account", "consult", "architect"):
        return {
            "personality": "editorial",
            "family": "editorial",
            "palette": "slate",
            "type": "editorial",
            "motif": "contour",
            "tone": "editorial",
        }
    if _contains(text, "salon", "spa", "beauty", "design", "interior", "photo", "studio"):
        return {
            "personality": "premium",
            "family": "minimal",
            "palette": "sand",
            "type": "editorial",
            "motif": "rings",
            "tone": "premium",
        }
    return {
        "personality": "friendly_local",
        "family": "local_trust",
        "palette": "earth",
        "type": "humanist",
        "motif": "blocks",
        "tone": "neighborly",
    }


def _apply_brief(profile, brief):
    result = dict(profile)
    b = brief.lower()
    if _contains(b, "premium", "luxury", "high-end", "high end", "upscale"):
        result.update(personality="premium", family="editorial", palette="sand", type="editorial", tone="premium", motif="contour")
    if _contains(b, "rugged", "blue-collar", "blue collar", "tough", "industrial"):
        result.update(personality="rugged", family="poster", palette="workwear", type="industrial", tone="direct", motif="grid")
    if _contains(b, "minimal", "clean", "simple", "quiet"):
        result.update(personality="minimal", family="minimal", palette="mono", type="modern", tone="direct", motif="none")
    if _contains(b, "editorial", "magazine", "story", "sophisticated"):
        result.update(personality="editorial", family="editorial", type="editorial", tone="editorial", motif="contour")
    if _contains(b, "friendly", "neighbor", "warm", "local"):
        result.update(personality="friendly_local", family="local_trust", palette="earth", type="humanist", tone="neighborly", motif="rings")
    if _contains(b, "service-first", "service first", "conversion", "direct", "urgent", "fast"):
        result.update(personality="service_first", family="utility", palette="navy", type="geometric", tone="direct", motif="blueprint")
    return result


def _hero_for_family(family):
    return {
        "cinematic": "split_art",
        "editorial": "offset_editorial",
        "utility": "utility_band",
        "poster": "poster_grid",
        "minimal": "quiet_center",
        "local_trust": "full_statement",
    }[family]


def _nav_for_family(family):
    return {
        "cinematic": "quiet",
        "editorial": "quiet",
        "utility": "utility",
        "poster": "solid",
        "minimal": "floating",
        "local_trust": "quiet",
    }[family]


def _sections_for(facts, family, seed):
    # Always provide a useful path to contact. Other sections must be backed by
    # available public facts or category-level presentation, never invented claims.
    sections = []
    if family in ("utility", "poster"):
        sections.extend(["credibility", "category_focus"])
    elif family == "editorial":
        sections.extend(["category_focus", "credibility"])
    elif family == "minimal":
        sections.append("category_focus")
    else:
        sections.extend(["credibility", "category_focus"])

    reviews = int(facts.get("reviews") or 0)
    rating = facts.get("rating")
    if reviews > 0 and rating not in (None, ""):
        insert_at = 1 if seed % 2 else len(sections)
        sections.insert(insert_at, "reputation")
    if facts.get("city"):
        insert_at = max(1, len(sections) - 1)
        sections.insert(insert_at, "local_presence")
    sections.append("contact")

    seen = []
    for item in sections:
        if item not in seen:
            seen.append(item)
    return seen[:5]


def _rationale(facts, profile, brief):
    items = [
        f"Uses a {profile['family'].replace('_', ' ')} composition for the {facts.get('category') or 'local service'} context.",
        f"Uses {profile['personality'].replace('_', ' ')} visual language rather than changing business facts.",
    ]
    if facts.get("reviews") and facts.get("rating") not in (None, ""):
        items.append("Public rating and review count are eligible for a reputation block because those values already exist in the prospect record.")
    if facts.get("city"):
        items.append("Location presentation is limited to the city already present in the prospect record.")
    if brief:
        items.append("Creative direction influenced presentation choices only; it did not add services, claims, credentials, or outcomes.")
    return items[:6]


def local_director(business, creative_brief="", concept_number=1):
    facts = build_fact_packet(business)
    brief = clean_brief(creative_brief)
    seed = _seed(facts, brief, concept_number)
    profile = _apply_brief(_category_profile(facts.get("category", "")), brief)

    family = profile["family"]
    # When the user asks for a genuinely different direction without a strong
    # stylistic keyword, rotate families rather than merely rotating colors.
    if _contains(brief, "different direction", "surprise me", "another direction", "completely different"):
        family = _pick(LAYOUT_FAMILIES, seed, 9)
        profile["family"] = family

    hero = _hero_for_family(family)
    nav = _nav_for_family(family)
    sections = _sections_for(facts, family, seed)

    variants = {}
    for index, section in enumerate(sections):
        options = SECTION_VARIANTS[section]
        variants[section] = _pick(options, seed, 17 + index * 5)

    blueprint = {
        "schema_version": SCHEMA_VERSION,
        "personality": profile["personality"] if profile["personality"] in PERSONALITIES else _pick(PERSONALITIES, seed, 1),
        "layout_family": family,
        "hero_layout": hero if hero in HERO_LAYOUTS else _pick(HERO_LAYOUTS, seed, 3),
        "nav_style": nav if nav in NAV_STYLES else _pick(NAV_STYLES, seed, 5),
        "type_system": profile["type"] if profile["type"] in TYPE_SYSTEMS else _pick(TYPE_SYSTEMS, seed, 7),
        "palette": profile["palette"] if profile["palette"] in PALETTES else _pick(PALETTES, seed, 11),
        "spacing": _pick(SPACING, seed, 13),
        "radius": "square" if family == "poster" else ("rounded" if family == "local_trust" else _pick(RADII, seed, 19)),
        "surface": "contrast" if family in ("poster", "utility") else _pick(SURFACES, seed, 23),
        "cta_style": "high_contrast" if family in ("poster", "utility") else _pick(CTA_STYLES, seed, 29),
        "visual_motif": profile["motif"] if profile["motif"] in VISUAL_MOTIFS else _pick(VISUAL_MOTIFS, seed, 31),
        "copy_tone": profile["tone"] if profile["tone"] in COPY_TONES else _pick(COPY_TONES, seed, 37),
        "density": "detailed" if family == "utility" else ("lean" if family == "minimal" else _pick(DENSITIES, seed, 41)),
        "section_order": sections,
        "section_variants": variants,
        "creative_brief": brief,
        "design_rationale": _rationale(facts, profile, brief),
    }
    validate_blueprint(blueprint)
    return DirectorResult(blueprint=blueprint, generation_mode="CONTEXT_DIRECTOR_V1")


def generate_concept_blueprint(business, creative_brief="", concept_number=1):
    """Provider-neutral entry point used by the Flask route."""
    return local_director(business, creative_brief, concept_number)
