"""Business OS v13 - safe prospect concept render model.

This module converts public prospect facts plus a validated design blueprint into
presentation text. It never infers services, warranties, credentials, years in
business, pricing, service areas, availability, outcomes, or ROI.
"""

from __future__ import annotations

import re

from services.v13_blueprints import validate_blueprint
from services.v13_creative_director import build_fact_packet


def _safe_phone_href(phone):
    digits = re.sub(r"[^0-9+]", "", str(phone or ""))
    if not digits or len(re.sub(r"\D", "", digits)) < 7:
        return ""
    return "tel:" + digits


def _category_label(category):
    return str(category or "Local Service").strip() or "Local Service"


def _hero_body(facts, tone):
    name = facts["name"] or "This business"
    category = _category_label(facts["category"])
    city = facts["city"]

    if tone == "premium":
        return (
            f"A more considered way to present {name}"
            + (f" in {city}" if city else "")
            + " and make the next step easy to find."
        )
    if tone == "neighborly":
        return (
            f"A straightforward way for people"
            + (f" in {city}" if city else "")
            + f" to find {name} and get in touch."
        )
    if tone == "editorial":
        pieces = [name, category]
        if city:
            pieces.append(city)
        return " · ".join(pieces) + ". Focused, clear, and easy to navigate."
    if tone == "practical":
        return (
            f"Find {name}, see the essential public details, and get in touch"
            + (f" in {city}" if city else "")
            + "."
        )
    return (
        f"{category}"
        + (f" in {city}" if city else "")
        + f", with a direct path to contact {name}."
    )


def _category_copy(facts, tone):
    category = _category_label(facts["category"])
    city = facts["city"]

    if city:
        base = f"{category} in {city}."
    else:
        base = f"{category}."

    if tone == "premium":
        return base + " A restrained presentation keeps the focus on the business and the next action."
    if tone == "neighborly":
        return base + " The essentials stay easy to find on any screen."
    if tone == "editorial":
        return base + " Clear hierarchy gives the business a stronger digital presence."
    if tone == "practical":
        return base + " Direct information and contact come first."
    return base + " A focused layout keeps the path to contact simple."


def _headline_for_family(facts, family):
    name = facts["name"] or "Local business"
    category = _category_label(facts["category"])
    city = facts["city"]

    if family == "utility":
        return f"A clearer way to reach {name}", "Straightforward information. Direct contact."
    if family == "poster":
        return name, f"{category}{(' · ' + city) if city else ''}"
    if family == "editorial":
        return name, f"A more deliberate digital presence for {category.lower()}."
    if family == "minimal":
        return name, f"{category}{(' · ' + city) if city else ''}"
    if family == "local_trust":
        return f"Meet {name}", f"{category}{(' in ' + city) if city else ''}"
    return name, f"{category}{(' in ' + city) if city else ''}"


def build_site_model(business, blueprint):
    validate_blueprint(blueprint)
    facts = build_fact_packet(business)
    tone = blueprint["copy_tone"]
    family = blueprint["layout_family"]

    category = _category_label(facts["category"])
    city = facts["city"]
    phone = facts["phone"]
    rating = facts["rating"]

    try:
        reviews = int(facts["reviews"] or 0)
    except (TypeError, ValueError):
        reviews = 0

    headline, supporting = _headline_for_family(facts, family)

    sections = []
    for name in blueprint["section_order"]:
        if name == "reputation" and (rating in (None, "") or reviews <= 0):
            continue
        if name == "local_presence" and not city:
            continue
        sections.append(name)

    hero_facts = [{"label": "Category", "value": category}]
    if city:
        hero_facts.append({"label": "Location", "value": city})
    if rating not in (None, "") and reviews > 0:
        hero_facts.append({"label": "Public rating", "value": f"{rating} ★ · {reviews} reviews"})
    if phone:
        hero_facts.append({"label": "Phone", "value": phone})

    if rating not in (None, "") and reviews > 0:
        reputation_heading = f"{rating} ★ from {reviews} public reviews"
        reputation_detail = "Public rating and review count shown from the current prospect record."
    else:
        reputation_heading = ""
        reputation_detail = ""

    return {
        "name": facts["name"],
        "category": category,
        "city": city,
        "phone": phone,
        "phone_href": _safe_phone_href(phone),
        "rating": rating,
        "reviews": reviews,
        "eyebrow": " · ".join([part for part in (category, city) if part]),
        "headline": headline,
        "supporting": supporting,
        "hero_body": _hero_body(facts, tone),
        "category_copy": _category_copy(facts, tone),
        "sections": sections,
        "has_reputation": rating not in (None, "") and reviews > 0,
        "reputation_heading": reputation_heading,
        "reputation_detail": reputation_detail,
        "contact_label": "Call now" if phone else "Contact",
        "contact_heading": f"Get in touch with {facts['name']}",
        "contact_copy": "Use the public contact information below to start the conversation.",
        "location_heading": city if city else "Local business",
        "location_copy": (
            f"Find {facts['name']} in {city} and contact the business directly."
            if city
            else f"Contact {facts['name']} directly."
        ),
        "layout_family": family,
        "hero_facts": hero_facts,
    }
