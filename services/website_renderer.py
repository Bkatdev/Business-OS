"""
Business OS v12 - Website Renderer

Purpose
-------
Build the safe, deterministic read model used by Website Studio previews
and, later, the customer-facing website surface.

Architectural rules
-------------------
1. Business Configuration remains the source of truth for business facts.
2. Website Studio owns presentation, not business truth.
3. Website versions are tenant-bound.
4. Preview versions must be explicitly selected.
5. No arbitrary HTML, JavaScript, templates, or executable content.
6. No live publishing occurs here.
7. No provider action occurs here.
8. Missing information remains missing rather than being invented.
"""

import html
from urllib.parse import urlparse

from services.website_studio import (
    canonical_website_context,
    ensure_website_studio_schema,
)
from services.website_versions import (
    get_current_version,
    get_preview_version,
)


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

MAX_BUSINESS_NAME_LENGTH = 200
MAX_CITY_LENGTH = 120
MAX_CATEGORY_LENGTH = 160
MAX_PHONE_LENGTH = 80
MAX_EMAIL_LENGTH = 254
MAX_SERVICE_NAME_LENGTH = 200
MAX_SERVICE_DESCRIPTION_LENGTH = 2000
MAX_QUESTION_LABEL_LENGTH = 500
MAX_OPTION_LENGTH = 300
MAX_OPTIONS = 100

SAFE_URL_SCHEMES = {
    "http",
    "https",
}

ALLOWED_QUESTION_TYPES = {
    "text",
    "textarea",
    "email",
    "phone",
    "select",
    "radio",
    "checkbox",
    "date",
    "time",
    "number",
}

DEFAULT_QUESTION_TYPE = "text"


# ---------------------------------------------------------------------
# ERRORS
# ---------------------------------------------------------------------


class WebsiteRenderError(ValueError):
    """Base error for Website Studio rendering."""


class WebsiteRenderNotFound(WebsiteRenderError):
    """Raised when required tenant-owned render state cannot be resolved."""


# ---------------------------------------------------------------------
# BASIC SAFE VALUE HELPERS
# ---------------------------------------------------------------------


def _clean_text(value, max_length):
    """
    Normalize plain text.

    This function does not create HTML. The renderer's contract is that
    customer-controlled/business-controlled copy remains plain text.
    """
    if value is None:
        return ""

    text = str(value).replace("\x00", "").strip()

    if len(text) > max_length:
        text = text[:max_length]

    return text


def _escaped_text(value, max_length):
    """
    Return HTML-escaped text for future server-rendered surfaces.

    The primary read model still exposes plain text separately. This
    escaped value exists so future templates never need to trust raw
    business-controlled text.
    """
    return html.escape(
        _clean_text(value, max_length),
        quote=True,
    )


def _safe_bool(value):
    return bool(value)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_http_url(value):
    """
    Accept only explicit HTTP/HTTPS URLs.

    javascript:, data:, file:, vbscript:, malformed values, and relative
    executable-looking values are rejected.

    An empty URL remains empty.
    """
    value = _clean_text(value, 2048)

    if not value:
        return ""

    try:
        parsed = urlparse(value)
    except (TypeError, ValueError):
        return ""

    scheme = (parsed.scheme or "").lower()

    if scheme not in SAFE_URL_SCHEMES:
        return ""

    if not parsed.netloc:
        return ""

    return value


def _safe_email(value):
    """
    Conservative display-level email normalization.

    This is not intended to prove that an email address exists. It only
    prevents malformed values from becoming customer-facing contact
    actions.
    """
    value = _clean_text(
        value,
        MAX_EMAIL_LENGTH,
    )

    if not value:
        return ""

    if (
        value.count("@") != 1
        or " " in value
        or "\r" in value
        or "\n" in value
    ):
        return ""

    local, domain = value.rsplit("@", 1)

    if (
        not local
        or not domain
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
    ):
        return ""

    return value


def _safe_phone(value):
    """
    Preserve human-readable phone formatting while rejecting control
    characters and extreme input.
    """
    value = _clean_text(
        value,
        MAX_PHONE_LENGTH,
    )

    if not value:
        return ""

    if "\r" in value or "\n" in value:
        return ""

    return value


# ---------------------------------------------------------------------
# CANONICAL DATA HELPERS
# ---------------------------------------------------------------------


def _row_to_dict(row):
    if row is None:
        return {}

    if isinstance(row, dict):
        return dict(row)

    try:
        return dict(row)
    except (TypeError, ValueError):
        return {}


def _normalize_business(raw_business):
    business = _row_to_dict(raw_business)

    name = _clean_text(
        business.get("name"),
        MAX_BUSINESS_NAME_LENGTH,
    )

    city = _clean_text(
        business.get("city"),
        MAX_CITY_LENGTH,
    )

    category = _clean_text(
        business.get("category"),
        MAX_CATEGORY_LENGTH,
    )

    phone = _safe_phone(
        business.get("phone")
    )

    email = _safe_email(
        business.get("email")
    )

    website = _safe_http_url(
        business.get("website")
    )

    return {
        "id": business.get("id"),
        "name": name,
        "name_html": _escaped_text(
            name,
            MAX_BUSINESS_NAME_LENGTH,
        ),
        "city": city,
        "city_html": _escaped_text(
            city,
            MAX_CITY_LENGTH,
        ),
        "category": category,
        "category_html": _escaped_text(
            category,
            MAX_CATEGORY_LENGTH,
        ),
        "phone": phone,
        "phone_html": _escaped_text(
            phone,
            MAX_PHONE_LENGTH,
        ),
        "email": email,
        "email_html": _escaped_text(
            email,
            MAX_EMAIL_LENGTH,
        ),
        "website": website,
    }


def _normalize_profile(raw_profile):
    profile = _row_to_dict(raw_profile)

    service_area = _clean_text(
        profile.get("service_area"),
        2000,
    )

    business_hours = _clean_text(
        profile.get("business_hours"),
        3000,
    )

    industry = _clean_text(
        profile.get("industry"),
        200,
    )

    messaging_tone = _clean_text(
        profile.get("messaging_tone"),
        500,
    )

    return {
        "industry": industry,
        "industry_html": _escaped_text(
            industry,
            200,
        ),
        "service_area": service_area,
        "service_area_html": _escaped_text(
            service_area,
            2000,
        ),
        "business_hours": business_hours,
        "business_hours_html": _escaped_text(
            business_hours,
            3000,
        ),
        "messaging_tone": messaging_tone,
    }


def _normalize_service(raw_service):
    service = _row_to_dict(raw_service)

    name = _clean_text(
        service.get("name"),
        MAX_SERVICE_NAME_LENGTH,
    )

    description = _clean_text(
        service.get("description"),
        MAX_SERVICE_DESCRIPTION_LENGTH,
    )

    return {
        "id": service.get("id"),
        "name": name,
        "name_html": _escaped_text(
            name,
            MAX_SERVICE_NAME_LENGTH,
        ),
        "description": description,
        "description_html": _escaped_text(
            description,
            MAX_SERVICE_DESCRIPTION_LENGTH,
        ),
        "bookable": _safe_bool(
            service.get("bookable")
        ),
        "requires_estimate": _safe_bool(
            service.get("requires_estimate")
        ),
        "sort_order": _safe_int(
            service.get("sort_order"),
            0,
        ),
    }


def _parse_question_options(raw_options):
    """
    Convert intake options into a bounded list of plain-text values.

    canonical_website_context may expose options_json directly depending
    on the source row, so this helper safely handles JSON strings as well
    as already-decoded lists.
    """
    import json

    if raw_options is None:
        return []

    if isinstance(raw_options, str):
        raw_options = raw_options.strip()

        if not raw_options:
            return []

        try:
            decoded = json.loads(raw_options)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    else:
        decoded = raw_options

    if not isinstance(decoded, list):
        return []

    options = []

    for item in decoded[:MAX_OPTIONS]:
        if isinstance(item, dict):
            value = (
                item.get("label")
                or item.get("value")
                or ""
            )
        else:
            value = item

        cleaned = _clean_text(
            value,
            MAX_OPTION_LENGTH,
        )

        if cleaned:
            options.append(cleaned)

    return options


def _normalize_question(raw_question):
    question = _row_to_dict(raw_question)

    question_type = _clean_text(
        question.get("question_type"),
        50,
    ).lower()

    if question_type not in ALLOWED_QUESTION_TYPES:
        question_type = DEFAULT_QUESTION_TYPE

    label = _clean_text(
        question.get("label"),
        MAX_QUESTION_LABEL_LENGTH,
    )

    question_key = _clean_text(
        question.get("question_key"),
        200,
    )

    options = _parse_question_options(
        question.get("options_json")
    )

    return {
        "id": question.get("id"),
        "service_id": question.get("service_id"),
        "question_key": question_key,
        "label": label,
        "label_html": _escaped_text(
            label,
            MAX_QUESTION_LABEL_LENGTH,
        ),
        "question_type": question_type,
        "required": _safe_bool(
            question.get("required")
        ),
        "sort_order": _safe_int(
            question.get("sort_order"),
            0,
        ),
        "options": options,
        "options_html": [
            _escaped_text(
                option,
                MAX_OPTION_LENGTH,
            )
            for option in options
        ],
    }


# ---------------------------------------------------------------------
# PRESENTATION
# ---------------------------------------------------------------------


def _normalize_presentation_for_render(presentation):
    presentation = dict(
        presentation or {}
    )

    theme_key = _clean_text(
        presentation.get("theme_key"),
        50,
    )

    if theme_key not in {
        "classic",
        "modern",
        "bold",
    }:
        theme_key = "classic"

    hero_headline = _clean_text(
        presentation.get("hero_headline"),
        300,
    )

    hero_supporting_text = _clean_text(
        presentation.get("hero_supporting_text"),
        1000,
    )

    primary_cta_label = _clean_text(
        presentation.get("primary_cta_label"),
        100,
    )

    if not primary_cta_label:
        primary_cta_label = "Request Service"

    about_copy = _clean_text(
        presentation.get("about_copy"),
        5000,
    )

    contact_intro = _clean_text(
        presentation.get("contact_intro"),
        1500,
    )

    seo_title = _clean_text(
        presentation.get("seo_title"),
        200,
    )

    seo_description = _clean_text(
        presentation.get("seo_description"),
        500,
    )

    return {
        "theme_key": theme_key,
        "hero_headline": hero_headline,
        "hero_headline_html": _escaped_text(
            hero_headline,
            300,
        ),
        "hero_supporting_text": hero_supporting_text,
        "hero_supporting_text_html": _escaped_text(
            hero_supporting_text,
            1000,
        ),
        "primary_cta_label": primary_cta_label,
        "primary_cta_label_html": _escaped_text(
            primary_cta_label,
            100,
        ),
        "about_copy": about_copy,
        "about_copy_html": _escaped_text(
            about_copy,
            5000,
        ),
        "contact_intro": contact_intro,
        "contact_intro_html": _escaped_text(
            contact_intro,
            1500,
        ),
        "show_services": _safe_bool(
            presentation.get(
                "show_services",
                True,
            )
        ),
        "show_about": _safe_bool(
            presentation.get(
                "show_about",
                True,
            )
        ),
        "show_contact": _safe_bool(
            presentation.get(
                "show_contact",
                True,
            )
        ),
        "seo_title": seo_title,
        "seo_description": seo_description,
    }


# ---------------------------------------------------------------------
# DEFAULT COPY
# ---------------------------------------------------------------------


def _resolved_hero_headline(
    presentation,
    business,
):
    """
    Use explicitly configured Website Studio copy first.

    The only fallback is the verified canonical business name. We do not
    generate marketing claims.
    """
    explicit = presentation["hero_headline"]

    if explicit:
        return explicit

    return business["name"]


def _resolved_hero_supporting_text(
    presentation,
    profile,
):
    """
    No AI-generated claim is invented.

    If the owner has not written supporting copy, leave it blank.
    """
    explicit = presentation[
        "hero_supporting_text"
    ]

    if explicit:
        return explicit

    return ""


def _resolved_seo_title(
    presentation,
    business,
):
    if presentation["seo_title"]:
        return presentation["seo_title"]

    return business["name"]


def _resolved_seo_description(
    presentation,
):
    if presentation["seo_description"]:
        return presentation["seo_description"]

    return ""


# ---------------------------------------------------------------------
# SERVICE / INTAKE ASSEMBLY
# ---------------------------------------------------------------------


def _build_services(raw_services):
    services = [
        _normalize_service(service)
        for service in (raw_services or [])
    ]

    services = [
        service
        for service in services
        if service["name"]
    ]

    services.sort(
        key=lambda item: (
            item["sort_order"],
            item["name"].lower(),
            _safe_int(item["id"], 0),
        )
    )

    return services


def _build_questions(raw_questions):
    questions = [
        _normalize_question(question)
        for question in (raw_questions or [])
    ]

    questions = [
        question
        for question in questions
        if (
            question["label"]
            and question["question_key"]
        )
    ]

    questions.sort(
        key=lambda item: (
            item["sort_order"],
            _safe_int(item["id"], 0),
        )
    )

    return questions


def _questions_by_service(questions):
    result = {}

    for question in questions:
        service_id = question["service_id"]

        key = (
            str(service_id)
            if service_id is not None
            else "general"
        )

        result.setdefault(
            key,
            [],
        ).append(question)

    return result


# ---------------------------------------------------------------------
# WARNINGS / COMPLETENESS
# ---------------------------------------------------------------------


def _build_warnings(
    business,
    profile,
    services,
    presentation,
):
    """
    Surface missing information rather than inventing it.
    """
    warnings = []

    if not business["name"]:
        warnings.append(
            {
                "code": "missing_business_name",
                "severity": "blocking",
                "message": (
                    "A verified business name is required."
                ),
            }
        )

    if not (
        business["phone"]
        or business["email"]
    ):
        warnings.append(
            {
                "code": "missing_contact_method",
                "severity": "blocking",
                "message": (
                    "Add a verified phone number or email address "
                    "before presenting the site as customer-ready."
                ),
            }
        )

    if not services:
        warnings.append(
            {
                "code": "missing_public_services",
                "severity": "blocking",
                "message": (
                    "At least one active public service is required."
                ),
            }
        )

    if not profile["service_area"]:
        warnings.append(
            {
                "code": "missing_service_area",
                "severity": "warning",
                "message": (
                    "Service area has not been configured."
                ),
            }
        )

    if not profile["business_hours"]:
        warnings.append(
            {
                "code": "missing_business_hours",
                "severity": "warning",
                "message": (
                    "Business hours have not been configured."
                ),
            }
        )

    if not presentation["about_copy"]:
        warnings.append(
            {
                "code": "missing_about_copy",
                "severity": "suggestion",
                "message": (
                    "About copy has not been added."
                ),
            }
        )

    return warnings


# ---------------------------------------------------------------------
# RENDER MODEL
# ---------------------------------------------------------------------


def build_render_model(
    conn,
    business_id,
    version=None,
):
    """
    Build a safe Website Studio render model for one tenant.

    Parameters
    ----------
    conn:
        Business OS database connection.

    business_id:
        Canonical tenant/business ID.

    version:
        Optional tenant-owned version dictionary.

        When omitted, the current Website Studio draft is used.

        This function never accepts a naked version ID as proof of
        ownership.

    Returns
    -------
    dict
        Deterministic presentation model suitable for Website Studio
        templates.

    Important
    ---------
    This is NOT publishing.
    """
    ensure_website_studio_schema(conn)

    canonical = canonical_website_context(
        conn,
        business_id,
    )

    if not canonical:
        raise WebsiteRenderNotFound(
            "Canonical website context could not be resolved."
        )

    if version is None:
        version = get_current_version(
            conn,
            business_id,
        )

    if not version:
        raise WebsiteRenderNotFound(
            "Website Studio version could not be resolved."
        )

    version_business_id = version.get(
        "business_id"
    )

    if version_business_id != business_id:
        raise WebsiteRenderNotFound(
            "Website Studio version does not belong "
            "to this business."
        )

    business = _normalize_business(
        canonical.get("business")
    )

    if business.get("id") != business_id:
        raise WebsiteRenderNotFound(
            "Canonical business ownership could not be verified."
        )

    profile = _normalize_profile(
        canonical.get("profile")
    )

    services = _build_services(
        canonical.get("services")
    )

    questions = _build_questions(
        canonical.get("intake_questions")
    )

    presentation = _normalize_presentation_for_render(
        version.get("presentation")
    )

    hero_headline = _resolved_hero_headline(
        presentation,
        business,
    )

    hero_supporting_text = (
        _resolved_hero_supporting_text(
            presentation,
            profile,
        )
    )

    seo_title = _resolved_seo_title(
        presentation,
        business,
    )

    seo_description = (
        _resolved_seo_description(
            presentation,
        )
    )

    warnings = _build_warnings(
        business,
        profile,
        services,
        presentation,
    )

    blocking_warnings = [
        warning
        for warning in warnings
        if warning["severity"] == "blocking"
    ]

    return {
        "business_id": business_id,
        "project_id": version.get(
            "project_id"
        ),
        "version": {
            "id": version.get("id"),
            "number": version.get(
                "version_number"
            ),
            "status": version.get(
                "status"
            ),
        },
        "business": business,
        "profile": profile,
        "presentation": presentation,
        "hero": {
            "headline": hero_headline,
            "headline_html": _escaped_text(
                hero_headline,
                300,
            ),
            "supporting_text": (
                hero_supporting_text
            ),
            "supporting_text_html": (
                _escaped_text(
                    hero_supporting_text,
                    1000,
                )
            ),
            "primary_cta_label": (
                presentation[
                    "primary_cta_label"
                ]
            ),
            "primary_cta_label_html": (
                presentation[
                    "primary_cta_label_html"
                ]
            ),
        },
        "services": services,
        "intake": {
            "questions": questions,
            "questions_by_service": (
                _questions_by_service(
                    questions
                )
            ),
        },
        "contact": {
            "phone": business["phone"],
            "phone_html": business[
                "phone_html"
            ],
            "email": business["email"],
            "email_html": business[
                "email_html"
            ],
            "service_area": profile[
                "service_area"
            ],
            "service_area_html": profile[
                "service_area_html"
            ],
            "business_hours": profile[
                "business_hours"
            ],
            "business_hours_html": profile[
                "business_hours_html"
            ],
        },
        "seo": {
            "title": seo_title,
            "description": seo_description,
        },
        "sections": {
            "services": (
                presentation[
                    "show_services"
                ]
            ),
            "about": (
                presentation[
                    "show_about"
                ]
            ),
            "contact": (
                presentation[
                    "show_contact"
                ]
            ),
        },
        "warnings": warnings,
        "blocking_warnings": (
            blocking_warnings
        ),
        "customer_ready": (
            len(blocking_warnings) == 0
        ),

        # v12.0 safety boundary:
        #
        # A render model can be previewed locally/internally.
        # It cannot publish itself or trigger an external action.
        "publishing": {
            "live_enabled": False,
            "provider": None,
            "published": False,
        },
    }


def build_current_draft_render_model(
    conn,
    business_id,
):
    """
    Build the operator's current Website Studio draft.
    """
    version = get_current_version(
        conn,
        business_id,
    )

    return build_render_model(
        conn,
        business_id,
        version=version,
    )


def build_preview_render_model(
    conn,
    business_id,
):
    """
    Build only the explicitly selected preview.

    Fail closed if no preview has been selected.

    We intentionally do NOT fall back to the current draft because that
    could expose unreviewed edits.
    """
    version = get_preview_version(
        conn,
        business_id,
    )

    if not version:
        raise WebsiteRenderNotFound(
            "No Website Studio preview version "
            "has been explicitly selected."
        )

    return build_render_model(
        conn,
        business_id,
        version=version,
    )


def render_safety_summary(
    conn,
    business_id,
):
    """
    Compact safety/readiness summary for the future Studio interface.
    """
    model = build_current_draft_render_model(
        conn,
        business_id,
    )

    preview = get_preview_version(
        conn,
        business_id,
    )

    return {
        "business_id": business_id,
        "current_version_id": (
            model["version"]["id"]
        ),
        "preview_version_id": (
            preview["id"]
            if preview
            else None
        ),
        "customer_ready": (
            model["customer_ready"]
        ),
        "blocking_warning_count": len(
            model["blocking_warnings"]
        ),
        "warning_count": len(
            model["warnings"]
        ),
        "live_publishing_enabled": False,
    }