from pathlib import Path
import shutil
import sys


# ============================================================
# Business OS v12 - Website Studio UI Installer
# ============================================================
#
# This installer:
#
# 1. Verifies exact source anchors before changing existing files.
# 2. Creates backups of modified existing files.
# 3. Adds Website Studio routes to app.py.
# 4. Adds Website Studio awareness to the existing Clients nav.
# 5. Adds Website Studio access from Business Configuration.
# 6. Adds the v12 stylesheet to base.html.
# 7. Creates:
#       templates/website_studio.html
#       templates/website_preview.html
#       static/v12.css
#
# It DOES NOT:
# - enable live publishing
# - create public submission endpoints
# - send SMS
# - write appointments
# - call external providers
# - modify canonical business facts
#
# Re-running after successful installation aborts safely.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

APP_FILE = ROOT / "app.py"
BASE_TEMPLATE = ROOT / "templates" / "base.html"
CONFIG_TEMPLATE = ROOT / "templates" / "business_configuration.html"

STUDIO_TEMPLATE = ROOT / "templates" / "website_studio.html"
PREVIEW_TEMPLATE = ROOT / "templates" / "website_preview.html"
V12_CSS = ROOT / "static" / "v12.css"

BACKUP_DIR = ROOT / ".v12_ui_backup"


def fail(message):
    print()
    print("INSTALL ABORTED")
    print("Reason:", message)
    print()
    sys.exit(1)


def read(path):
    if not path.exists():
        fail(f"Required file not found: {path}")

    return path.read_text(
        encoding="utf-8"
    )


def write(path, content):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )


def require_once(text, anchor, label):
    count = text.count(anchor)

    if count != 1:
        fail(
            f"{label}: expected exact anchor once, "
            f"found {count}."
        )


def backup(path):
    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = BACKUP_DIR / path.name

    if not target.exists():
        shutil.copy2(
            path,
            target,
        )


print()
print("=" * 64)
print("Business OS v12 - Website Studio UI Installer")
print("=" * 64)
print("Repository:", ROOT)
print()


# ============================================================
# PRE-FLIGHT
# ============================================================

app_text = read(APP_FILE)
base_text = read(BASE_TEMPLATE)
config_text = read(CONFIG_TEMPLATE)


# Prevent accidental second installation.
if (
    "def website_studio(" in app_text
    or STUDIO_TEMPLATE.exists()
    or PREVIEW_TEMPLATE.exists()
    or V12_CSS.exists()
):
    fail(
        "Website Studio UI appears to already be installed. "
        "No files were changed."
    )


# ------------------------------------------------------------
# Exact app.py anchors from the inspected v11.1/v12 snapshot
# ------------------------------------------------------------

BUSINESS_CONFIG_IMPORT = (
    "from services.business_config import "
    "ensure_business_config_schema, configuration_view, "
    "add_service, toggle_service, add_intake_question, "
    "toggle_intake_question\n"
)

require_once(
    app_text,
    BUSINESS_CONFIG_IMPORT,
    "app.py business-config import",
)


CONFIGURATION_ROUTE = '''@app.route("/client/<int:bid>/configuration")
def business_configuration(bid):
    conn = connect()
    ensure_product_schema(conn)
    business = conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    if business is None:
        conn.close()
        return render_template("404.html"), 404
    config = configuration_view(conn, bid)
    readiness = readiness_for_business(conn, business)
    conn.close()
    return render_template("business_configuration.html", business=business, config=config, readiness=readiness)


'''

require_once(
    app_text,
    CONFIGURATION_ROUTE,
    "app.py configuration route",
)


# ------------------------------------------------------------
# Exact base.html anchors
# ------------------------------------------------------------

CLIENT_NAV_ENDPOINTS = """['clients', 'client_operations', 'client_onboarding', 'activate_client', 'business_configuration', 'add_business_service', 'toggle_business_service', 'add_business_intake_question', 'toggle_business_intake_question', 'update_client_retell_agent']"""

require_once(
    base_text,
    CLIENT_NAV_ENDPOINTS,
    "base.html Clients endpoint list",
)


V111_CSS_LINK = """    <link rel="stylesheet" href="{{ url_for('static', filename='v111.css') }}?v=1">
"""

require_once(
    base_text,
    V111_CSS_LINK,
    "base.html v111 stylesheet",
)


# ------------------------------------------------------------
# Exact Business Configuration action block
# ------------------------------------------------------------

CONFIG_ACTIONS = """{% block actions %}<a class="btn secondary" href="{{ url_for('client_operations', bid=business.id) }}">Client command center</a><a class="btn" href="{{ url_for('client_onboarding', bid=business.id) }}">Business profile</a>{% endblock %}
"""

require_once(
    config_text,
    CONFIG_ACTIONS,
    "business_configuration.html action block",
)


print("Pre-flight source verification: PASS")


# ============================================================
# BACKUPS
# ============================================================

backup(APP_FILE)
backup(BASE_TEMPLATE)
backup(CONFIG_TEMPLATE)

print("Protected backups created in .v12_ui_backup")


# ============================================================
# app.py IMPORTS
# ============================================================

WEBSITE_IMPORTS = '''from services.website_studio import website_studio_view
from services.website_versions import (
    WebsiteVersionConflict,
    WebsiteVersionNotFound,
    get_current_version,
    get_preview_version,
    list_versions,
    select_preview_version,
    synchronize_readiness,
    update_presentation,
)
from services.website_renderer import (
    WebsiteRenderNotFound,
    build_current_draft_render_model,
    build_preview_render_model,
)
'''

app_text = app_text.replace(
    BUSINESS_CONFIG_IMPORT,
    BUSINESS_CONFIG_IMPORT + WEBSITE_IMPORTS,
    1,
)


# ============================================================
# app.py ROUTES
# ============================================================

WEBSITE_ROUTES = r'''@app.route("/client/<int:bid>/website")
def website_studio(bid):
    conn = connect()

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        studio = website_studio_view(
            conn,
            bid,
        )

        draft = get_current_version(
            conn,
            bid,
        )

        preview = get_preview_version(
            conn,
            bid,
        )

        versions = list_versions(
            conn,
            bid,
            limit=20,
        )

        render_model = (
            build_current_draft_render_model(
                conn,
                bid,
            )
        )

    except (
        WebsiteVersionNotFound,
        WebsiteRenderNotFound,
    ) as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "business_configuration",
                bid=bid,
            )
        )

    conn.close()

    return render_template(
        "website_studio.html",
        business=business,
        studio=studio,
        draft=draft,
        preview=preview,
        versions=versions,
        site=render_model,
    )


@app.route(
    "/client/<int:bid>/website/save",
    methods=["POST"],
)
def save_website_studio(bid):
    conn = connect()

    business = conn.execute(
        "SELECT id FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    changes = {
        "theme_key": (
            request.form.get(
                "theme_key",
                "classic",
            ).strip()
        ),
        "hero_headline": request.form.get(
            "hero_headline",
            "",
        ),
        "hero_supporting_text": request.form.get(
            "hero_supporting_text",
            "",
        ),
        "primary_cta_label": request.form.get(
            "primary_cta_label",
            "Request Service",
        ),
        "about_copy": request.form.get(
            "about_copy",
            "",
        ),
        "contact_intro": request.form.get(
            "contact_intro",
            "",
        ),
        "show_services": (
            request.form.get(
                "show_services"
            )
            == "1"
        ),
        "show_about": (
            request.form.get(
                "show_about"
            )
            == "1"
        ),
        "show_contact": (
            request.form.get(
                "show_contact"
            )
            == "1"
        ),
        "seo_title": request.form.get(
            "seo_title",
            "",
        ),
        "seo_description": request.form.get(
            "seo_description",
            "",
        ),
    }

    expected_version = request.form.get(
        "expected_current_version_id",
        "",
    ).strip()

    try:
        result = update_presentation(
            conn,
            bid,
            changes,
            expected_current_version_id=(
                expected_version
                if expected_version
                else None
            ),
        )

        synchronize_readiness(
            conn,
            bid,
        )

    except WebsiteVersionConflict as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    except (
        WebsiteVersionNotFound,
        ValueError,
    ) as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    if result.get(
        "created_new_version"
    ):
        flash(
            "Website draft saved as a new version. "
            "The reviewed preview was not changed.",
            "success",
        )

    else:
        flash(
            "No presentation changes were detected.",
            "success",
        )

    return redirect(
        url_for(
            "website_studio",
            bid=bid,
        )
    )


@app.route(
    "/client/<int:bid>/website/preview/select",
    methods=["POST"],
)
def select_website_preview(bid):
    raw_version = request.form.get(
        "version_id",
        "",
    ).strip()

    if not raw_version.isdigit():
        flash(
            "Choose a valid Website Studio version.",
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn = connect()

    business = conn.execute(
        "SELECT id FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        select_preview_version(
            conn,
            bid,
            int(raw_version),
        )

        synchronize_readiness(
            conn,
            bid,
        )

    except WebsiteVersionNotFound as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    flash(
        "Preview version selected. "
        "Nothing has been published.",
        "success",
    )

    return redirect(
        url_for(
            "website_studio",
            bid=bid,
        )
    )


@app.route("/client/<int:bid>/website/preview")
def website_preview(bid):
    conn = connect()

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=?",
        (bid,),
    ).fetchone()

    if business is None:
        conn.close()
        return render_template("404.html"), 404

    try:
        model = build_preview_render_model(
            conn,
            bid,
        )

    except WebsiteRenderNotFound as exc:
        conn.close()
        flash(
            str(exc),
            "error",
        )
        return redirect(
            url_for(
                "website_studio",
                bid=bid,
            )
        )

    conn.close()

    return render_template(
        "website_preview.html",
        business=business,
        site=model,
    )


'''

app_text = app_text.replace(
    CONFIGURATION_ROUTE,
    CONFIGURATION_ROUTE + WEBSITE_ROUTES,
    1,
)


# ============================================================
# base.html
# ============================================================

UPDATED_CLIENT_NAV_ENDPOINTS = """['clients', 'client_operations', 'client_onboarding', 'activate_client', 'business_configuration', 'add_business_service', 'toggle_business_service', 'add_business_intake_question', 'toggle_business_intake_question', 'update_client_retell_agent', 'website_studio', 'save_website_studio', 'select_website_preview', 'website_preview']"""

base_text = base_text.replace(
    CLIENT_NAV_ENDPOINTS,
    UPDATED_CLIENT_NAV_ENDPOINTS,
    1,
)

base_text = base_text.replace(
    V111_CSS_LINK,
    V111_CSS_LINK
    + """    <link rel="stylesheet" href="{{ url_for('static', filename='v12.css') }}?v=1">
""",
    1,
)


# ============================================================
# Business Configuration action
# ============================================================

UPDATED_CONFIG_ACTIONS = """{% block actions %}<a class="btn secondary" href="{{ url_for('client_operations', bid=business.id) }}">Client command center</a><a class="btn secondary" href="{{ url_for('website_studio', bid=business.id) }}">Website Studio</a><a class="btn" href="{{ url_for('client_onboarding', bid=business.id) }}">Business profile</a>{% endblock %}
"""

config_text = config_text.replace(
    CONFIG_ACTIONS,
    UPDATED_CONFIG_ACTIONS,
    1,
)


# ============================================================
# Website Studio template
# ============================================================

STUDIO_HTML = r'''{% extends "base.html" %}

{% block title %}Website Studio · {{ business.name }} · Business OS{% endblock %}
{% block heading %}Website Studio{% endblock %}

{% block actions %}
<a class="btn secondary" href="{{ url_for('business_configuration', bid=business.id) }}">Business Configuration</a>
{% if preview %}
<a class="btn" href="{{ url_for('website_preview', bid=business.id) }}" target="_blank" rel="noopener">Open Preview</a>
{% endif %}
{% endblock %}

{% block content %}

<div class="v12-studio-intro">
    <div>
        <span class="section-kicker">CUSTOMER FRONT DOOR</span>
        <h2>{{ business.name }}</h2>
        <p>
            Turn verified Business OS information into a professional web presence.
            Services, contact information, service area, and intake remain connected
            to the same canonical business configuration.
        </p>

        <div class="v12-chip-row">
            <span class="v12-chip">
                Draft v{{ draft.version_number }}
            </span>

            <span class="v12-chip">
                {{ site.services|length }} public services
            </span>

            <span class="v12-chip">
                {{ site.intake.questions|length }} intake questions
            </span>

            {% if preview %}
            <span class="v12-chip positive">
                Preview v{{ preview.version_number }}
            </span>
            {% else %}
            <span class="v12-chip muted">
                No reviewed preview
            </span>
            {% endif %}

            <span class="v12-chip locked">
                Live publishing locked
            </span>
        </div>
    </div>

    <div class="v12-readiness-card">
        <span>WEBSITE READINESS</span>
        <strong>{{ studio.readiness.score }}%</strong>
        <small>
            {{ studio.readiness.checks|selectattr('passed')|list|length }}
            of
            {{ studio.readiness.checks|length }}
            checks
        </small>
    </div>
</div>


{% if site.warnings %}
<div class="panel v12-warning-panel">
    <div class="v9-section-head">
        <div>
            <span class="section-kicker">READINESS</span>
            <h3>What still needs attention</h3>
            <p>
                Business OS will show missing information rather than invent it.
            </p>
        </div>
        <span class="count-bubble">{{ site.warnings|length }}</span>
    </div>

    <div class="v12-warning-list">
        {% for warning in site.warnings %}
        <div class="v12-warning {{ warning.severity }}">
            <strong>{{ warning.message }}</strong>
            <span>{{ warning.severity|upper }}</span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}


<div class="v12-studio-layout">

    <div class="v12-editor-column">

        <form
            method="POST"
            action="{{ url_for('save_website_studio', bid=business.id) }}"
            class="panel v12-editor"
        >
            <input
                type="hidden"
                name="expected_current_version_id"
                value="{{ draft.id }}"
            >

            <div class="v9-section-head">
                <div>
                    <span class="section-kicker">PRESENTATION</span>
                    <h3>Website appearance and copy</h3>
                    <p>
                        Presentation lives here. Verified business facts stay in
                        Business Configuration.
                    </p>
                </div>
            </div>

            <div class="v12-form-section">
                <label class="v12-field">
                    <span>Theme</span>
                    <select name="theme_key">
                        <option value="classic" {% if draft.presentation.theme_key == 'classic' %}selected{% endif %}>Classic</option>
                        <option value="modern" {% if draft.presentation.theme_key == 'modern' %}selected{% endif %}>Modern</option>
                        <option value="bold" {% if draft.presentation.theme_key == 'bold' %}selected{% endif %}>Bold</option>
                    </select>
                </label>
            </div>

            <div class="v12-form-section">
                <span class="v12-form-kicker">HERO</span>

                <label class="v12-field">
                    <span>Headline</span>
                    <input
                        name="hero_headline"
                        maxlength="160"
                        value="{{ draft.presentation.hero_headline }}"
                        placeholder="{{ business.name }}"
                    >
                </label>

                <label class="v12-field">
                    <span>Supporting text</span>
                    <textarea
                        name="hero_supporting_text"
                        maxlength="500"
                        rows="3"
                        placeholder="Short, factual explanation of how you help customers."
                    >{{ draft.presentation.hero_supporting_text }}</textarea>
                </label>

                <label class="v12-field">
                    <span>Primary button</span>
                    <input
                        name="primary_cta_label"
                        maxlength="80"
                        value="{{ draft.presentation.primary_cta_label }}"
                    >
                </label>
            </div>

            <div class="v12-form-section">
                <span class="v12-form-kicker">ABOUT</span>

                <label class="v12-field">
                    <span>About copy</span>
                    <textarea
                        name="about_copy"
                        maxlength="2000"
                        rows="6"
                        placeholder="Verified, owner-approved information about the business."
                    >{{ draft.presentation.about_copy }}</textarea>
                </label>
            </div>

            <div class="v12-form-section">
                <span class="v12-form-kicker">CONTACT</span>

                <label class="v12-field">
                    <span>Contact introduction</span>
                    <textarea
                        name="contact_intro"
                        maxlength="500"
                        rows="3"
                        placeholder="Optional introduction above the contact/request section."
                    >{{ draft.presentation.contact_intro }}</textarea>
                </label>
            </div>

            <div class="v12-form-section">
                <span class="v12-form-kicker">VISIBLE SECTIONS</span>

                <div class="v12-toggle-grid">
                    <label>
                        <input
                            type="checkbox"
                            name="show_services"
                            value="1"
                            {% if draft.presentation.show_services %}checked{% endif %}
                        >
                        <span>
                            <strong>Services</strong>
                            <small>Use active public services from Business Configuration.</small>
                        </span>
                    </label>

                    <label>
                        <input
                            type="checkbox"
                            name="show_about"
                            value="1"
                            {% if draft.presentation.show_about %}checked{% endif %}
                        >
                        <span>
                            <strong>About</strong>
                            <small>Show the owner-approved about section.</small>
                        </span>
                    </label>

                    <label>
                        <input
                            type="checkbox"
                            name="show_contact"
                            value="1"
                            {% if draft.presentation.show_contact %}checked{% endif %}
                        >
                        <span>
                            <strong>Contact & request</strong>
                            <small>Show verified contact information and intake preview.</small>
                        </span>
                    </label>
                </div>
            </div>

            <div class="v12-form-section">
                <span class="v12-form-kicker">SEARCH PREVIEW</span>

                <label class="v12-field">
                    <span>SEO title</span>
                    <input
                        name="seo_title"
                        maxlength="160"
                        value="{{ draft.presentation.seo_title }}"
                        placeholder="{{ business.name }}"
                    >
                </label>

                <label class="v12-field">
                    <span>SEO description</span>
                    <textarea
                        name="seo_description"
                        maxlength="320"
                        rows="3"
                        placeholder="Concise factual description for search results."
                    >{{ draft.presentation.seo_description }}</textarea>
                </label>
            </div>

            <div class="v12-save-bar">
                <div>
                    <strong>Draft version {{ draft.version_number }}</strong>
                    <span>
                        Saving creates a new immutable version only when something changed.
                    </span>
                </div>

                <button class="btn" type="submit">
                    Save Website Draft
                </button>
            </div>

        </form>


        <section class="panel v12-history">
            <div class="v9-section-head">
                <div>
                    <span class="section-kicker">VERSION HISTORY</span>
                    <h3>Website drafts</h3>
                    <p>
                        Preview selection is explicit. Editing a new draft does not
                        silently replace a reviewed preview.
                    </p>
                </div>

                <span class="count-bubble">{{ versions|length }}</span>
            </div>

            <div class="v12-version-list">
                {% for version in versions %}
                <div class="v12-version-row">
                    <div>
                        <strong>Version {{ version.version_number }}</strong>
                        <span>
                            {{ version.status|replace('_', ' ')|title }}
                            · {{ version.updated_at }}
                        </span>
                    </div>

                    <div class="v12-version-actions">
                        {% if preview and preview.id == version.id %}
                        <span class="v12-chip positive">Preview</span>
                        {% else %}
                        <form
                            method="POST"
                            action="{{ url_for('select_website_preview', bid=business.id) }}"
                        >
                            <input
                                type="hidden"
                                name="version_id"
                                value="{{ version.id }}"
                            >
                            <button
                                class="btn secondary"
                                type="submit"
                            >
                                Use for Preview
                            </button>
                        </form>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

    </div>


    <aside class="v12-studio-rail">

        <section class="panel v12-source-card">
            <span class="section-kicker">SHARED BUSINESS TRUTH</span>
            <h3>Connected configuration</h3>

            <div class="v12-source-list">
                <div>
                    <span>Business</span>
                    <strong>{{ site.business.name or 'Missing' }}</strong>
                </div>

                <div>
                    <span>Phone</span>
                    <strong>{{ site.contact.phone or 'Not configured' }}</strong>
                </div>

                <div>
                    <span>Email</span>
                    <strong>{{ site.contact.email or 'Not configured' }}</strong>
                </div>

                <div>
                    <span>Service area</span>
                    <strong>{{ site.contact.service_area or 'Not configured' }}</strong>
                </div>

                <div>
                    <span>Business hours</span>
                    <strong>{{ site.contact.business_hours or 'Not configured' }}</strong>
                </div>
            </div>

            <a
                class="btn secondary v12-full-button"
                href="{{ url_for('business_configuration', bid=business.id) }}"
            >
                Edit Business Configuration
            </a>
        </section>


        <section class="panel v12-source-card">
            <span class="section-kicker">PUBLIC SERVICES</span>
            <h3>{{ site.services|length }} available</h3>

            {% if site.services %}
            <div class="v12-mini-list">
                {% for service in site.services %}
                <div>
                    <strong>{{ service.name }}</strong>
                    <span>
                        {% if service.requires_estimate %}
                        Estimate first
                        {% elif service.bookable %}
                        Bookable
                        {% else %}
                        Request service
                        {% endif %}
                    </span>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="v9-empty">
                <strong>No public services configured.</strong>
                <span>
                    Website Studio will not invent services.
                </span>
            </div>
            {% endif %}
        </section>


        <section class="panel v12-source-card">
            <span class="section-kicker">PUBLISHING BOUNDARY</span>
            <h3>Preview only</h3>

            <p class="v12-muted-copy">
                Website Studio can prepare and review a customer-facing experience,
                but v12 does not contain a live publishing provider.
            </p>

            <div class="v12-lock-box">
                <strong>Live publishing is locked</strong>
                <span>
                    No domain, hosting provider, external deployment, SMS,
                    scheduling write, or customer communication is triggered here.
                </span>
            </div>

            {% if preview %}
            <a
                class="btn v12-full-button"
                href="{{ url_for('website_preview', bid=business.id) }}"
                target="_blank"
                rel="noopener"
            >
                Open Reviewed Preview
            </a>
            {% else %}
            <button
                class="btn secondary v12-full-button"
                type="button"
                disabled
            >
                Select a preview version first
            </button>
            {% endif %}
        </section>

    </aside>

</div>

{% endblock %}
'''


# ============================================================
# Safe customer-facing preview template
# ============================================================

PREVIEW_HTML = r'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>{{ site.seo.title or site.business.name }}</title>

    {% if site.seo.description %}
    <meta
        name="description"
        content="{{ site.seo.description }}"
    >
    {% endif %}

    <link
        rel="stylesheet"
        href="{{ url_for('static', filename='v12.css') }}?v=1"
    >
</head>

<body class="v12-preview-body">

<div class="v12-preview-toolbar">
    <div>
        <strong>Business OS Website Preview</strong>
        <span>
            Version {{ site.version.number }} · Not published
        </span>
    </div>

    <a
        href="{{ url_for('website_studio', bid=business.id) }}"
    >
        Back to Website Studio
    </a>
</div>


<main class="v12-public-site theme-{{ site.presentation.theme_key }}">

    <header class="v12-public-header">
        <div class="v12-public-container">
            <a class="v12-public-brand" href="#top">
                {{ site.business.name }}
            </a>

            <nav aria-label="Website sections">
                {% if site.sections.services and site.services %}
                <a href="#services">Services</a>
                {% endif %}

                {% if site.sections.about and site.presentation.about_copy %}
                <a href="#about">About</a>
                {% endif %}

                {% if site.sections.contact %}
                <a href="#contact">Contact</a>
                {% endif %}
            </nav>
        </div>
    </header>


    <section id="top" class="v12-public-hero">
        <div class="v12-public-container v12-public-hero-grid">

            <div>
                {% if site.profile.industry %}
                <span class="v12-public-eyebrow">
                    {{ site.profile.industry }}
                </span>
                {% endif %}

                <h1>{{ site.hero.headline }}</h1>

                {% if site.hero.supporting_text %}
                <p>{{ site.hero.supporting_text }}</p>
                {% endif %}

                {% if site.sections.contact %}
                <a
                    class="v12-public-button"
                    href="#contact"
                >
                    {{ site.hero.primary_cta_label }}
                </a>
                {% endif %}
            </div>

            <div class="v12-public-trust-card">
                <span>Serving</span>
                <strong>
                    {{ site.profile.service_area or site.business.city or 'Local customers' }}
                </strong>

                {% if site.profile.business_hours %}
                <small>{{ site.profile.business_hours }}</small>
                {% endif %}
            </div>

        </div>
    </section>


    {% if site.sections.services %}
    <section id="services" class="v12-public-section">
        <div class="v12-public-container">

            <div class="v12-public-section-heading">
                <span>Services</span>
                <h2>How we can help</h2>
            </div>

            {% if site.services %}
            <div class="v12-public-service-grid">
                {% for service in site.services %}
                <article class="v12-public-service-card">
                    <h3>{{ service.name }}</h3>

                    {% if service.description %}
                    <p>{{ service.description }}</p>
                    {% endif %}

                    <small>
                        {% if service.requires_estimate %}
                        Estimate required
                        {% elif service.bookable %}
                        Available to book
                        {% else %}
                        Request service
                        {% endif %}
                    </small>
                </article>
                {% endfor %}
            </div>
            {% else %}
            <p class="v12-public-muted">
                Service information is being configured.
            </p>
            {% endif %}

        </div>
    </section>
    {% endif %}


    {% if site.sections.about and site.presentation.about_copy %}
    <section id="about" class="v12-public-section v12-public-section-alt">
        <div class="v12-public-container v12-public-copy-section">
            <span>About</span>
            <h2>{{ site.business.name }}</h2>
            <p>{{ site.presentation.about_copy }}</p>
        </div>
    </section>
    {% endif %}


    {% if site.sections.contact %}
    <section id="contact" class="v12-public-section">
        <div class="v12-public-container">

            <div class="v12-public-section-heading">
                <span>Contact</span>
                <h2>{{ site.hero.primary_cta_label }}</h2>

                {% if site.presentation.contact_intro %}
                <p>{{ site.presentation.contact_intro }}</p>
                {% endif %}
            </div>

            <div class="v12-public-contact-grid">

                <div class="v12-public-contact-card">
                    {% if site.contact.phone %}
                    <div>
                        <span>Phone</span>
                        <strong>{{ site.contact.phone }}</strong>
                    </div>
                    {% endif %}

                    {% if site.contact.email %}
                    <div>
                        <span>Email</span>
                        <strong>{{ site.contact.email }}</strong>
                    </div>
                    {% endif %}

                    {% if site.contact.service_area %}
                    <div>
                        <span>Service area</span>
                        <strong>{{ site.contact.service_area }}</strong>
                    </div>
                    {% endif %}

                    {% if site.contact.business_hours %}
                    <div>
                        <span>Hours</span>
                        <strong>{{ site.contact.business_hours }}</strong>
                    </div>
                    {% endif %}
                </div>


                <div class="v12-public-request-card">
                    <span class="v12-public-eyebrow">
                        Request preview
                    </span>

                    <h3>Tell us what you need</h3>

                    <p>
                        This preview shows the verified intake structure.
                        Submission is intentionally disabled until the governed
                        public intake endpoint is installed and tested.
                    </p>

                    {% if site.intake.questions %}
                    <div class="v12-public-question-preview">
                        {% for question in site.intake.questions %}
                        <label>
                            <span>
                                {{ question.label }}
                                {% if question.required %} *{% endif %}
                            </span>

                            {% if question.question_type in ['select', 'radio'] and question.options %}
                            <select disabled>
                                <option>Select an option</option>
                                {% for option in question.options %}
                                <option>{{ option }}</option>
                                {% endfor %}
                            </select>

                            {% elif question.question_type == 'textarea' %}
                            <textarea
                                rows="3"
                                disabled
                                placeholder="Preview only"
                            ></textarea>

                            {% else %}
                            <input
                                disabled
                                placeholder="Preview only"
                            >
                            {% endif %}
                        </label>
                        {% endfor %}
                    </div>
                    {% endif %}

                    <button
                        class="v12-public-button"
                        type="button"
                        disabled
                    >
                        Preview only · Submission locked
                    </button>
                </div>

            </div>
        </div>
    </section>
    {% endif %}


    <footer class="v12-public-footer">
        <div class="v12-public-container">
            <strong>{{ site.business.name }}</strong>
            <span>
                Website preview generated from verified Business OS configuration.
            </span>
        </div>
    </footer>

</main>

</body>
</html>
'''


# ============================================================
# v12 CSS
# ============================================================

V12_CSS_TEXT = r'''/* =========================================================
   Business OS v12 · Website Studio
   Extends the v9.2 / v10.2 visual language.
   ========================================================= */


/* ---------------------------------------------------------
   Internal Website Studio
   --------------------------------------------------------- */

.v12-studio-intro{
    display:grid;
    grid-template-columns:minmax(0,1fr) 180px;
    gap:24px;
    align-items:center;
    padding:24px;
    margin-bottom:18px;
    border:1px solid var(--border,#e2e8ee);
    border-radius:16px;
    background:linear-gradient(180deg,#fff,#fbfcfd);
}

.v12-studio-intro h2{
    margin:5px 0 7px;
    font-size:26px;
    color:#172033;
}

.v12-studio-intro p{
    max-width:78ch;
    margin:0;
    color:#667085;
    line-height:1.55;
}

.v12-chip-row{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin-top:16px;
}

.v12-chip{
    display:inline-flex;
    align-items:center;
    min-height:28px;
    padding:5px 9px;
    border:1px solid #dde4ea;
    border-radius:999px;
    background:#f5f7f9;
    color:#5d6975;
    font-size:10px;
    font-weight:800;
    letter-spacing:.04em;
    text-transform:uppercase;
}

.v12-chip.positive{
    border-color:#cce8d8;
    background:#effaf4;
    color:#28734a;
}

.v12-chip.muted{
    color:#7b8794;
}

.v12-chip.locked{
    border-color:#ecd8b7;
    background:#fff9ec;
    color:#845f1d;
}

.v12-readiness-card{
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    min-height:135px;
    padding:16px;
    border:1px solid #e3e8ed;
    border-radius:14px;
    background:#fff;
    text-align:center;
}

.v12-readiness-card span{
    font-size:10px;
    font-weight:800;
    letter-spacing:.07em;
    color:#7b8794;
}

.v12-readiness-card strong{
    margin:7px 0 2px;
    font-size:34px;
    color:#172033;
}

.v12-readiness-card small{
    color:#89939d;
}

.v12-studio-layout{
    display:grid;
    grid-template-columns:minmax(0,1.65fr) minmax(280px,.7fr);
    gap:18px;
    align-items:start;
}

.v12-editor-column{
    min-width:0;
}

.v12-editor{
    margin:0;
}

.v12-form-section{
    padding:18px 0;
    border-top:1px solid #edf0f3;
}

.v12-form-section:first-of-type{
    border-top:0;
}

.v12-form-kicker{
    display:block;
    margin-bottom:12px;
    font-size:10px;
    font-weight:800;
    letter-spacing:.08em;
    color:#87919c;
}

.v12-field{
    display:grid;
    gap:7px;
    margin-top:13px;
}

.v12-field:first-of-type{
    margin-top:0;
}

.v12-field>span{
    font-size:12px;
    font-weight:800;
    color:#3f4b59;
}

.v12-field input,
.v12-field textarea,
.v12-field select{
    width:100%;
    box-sizing:border-box;
    padding:11px 12px;
    border:1px solid #dce3e9;
    border-radius:10px;
    background:#fff;
    color:#172033;
    font:inherit;
    outline:none;
    transition:border-color .15s ease,box-shadow .15s ease;
}

.v12-field textarea{
    resize:vertical;
    line-height:1.5;
}

.v12-field input:focus,
.v12-field textarea:focus,
.v12-field select:focus{
    border-color:#8cb9a3;
    box-shadow:0 0 0 3px rgba(68,135,103,.10);
}

.v12-toggle-grid{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:10px;
}

.v12-toggle-grid label{
    display:flex;
    gap:10px;
    align-items:flex-start;
    padding:13px;
    border:1px solid #e4e9ed;
    border-radius:11px;
    background:#fbfcfd;
    cursor:pointer;
}

.v12-toggle-grid input{
    margin-top:3px;
}

.v12-toggle-grid strong,
.v12-toggle-grid small{
    display:block;
}

.v12-toggle-grid strong{
    font-size:12px;
    color:#344054;
}

.v12-toggle-grid small{
    margin-top:3px;
    color:#89939d;
    line-height:1.4;
}

.v12-save-bar{
    display:flex;
    justify-content:space-between;
    gap:20px;
    align-items:center;
    padding-top:18px;
    border-top:1px solid #edf0f3;
}

.v12-save-bar strong,
.v12-save-bar span{
    display:block;
}

.v12-save-bar strong{
    color:#344054;
}

.v12-save-bar span{
    margin-top:3px;
    font-size:11px;
    color:#89939d;
}

.v12-studio-rail{
    display:grid;
    gap:18px;
}

.v12-source-card{
    margin:0;
}

.v12-source-card h3{
    margin:5px 0 14px;
}

.v12-source-list{
    display:grid;
    margin-bottom:14px;
}

.v12-source-list>div{
    display:grid;
    gap:3px;
    padding:10px 0;
    border-top:1px solid #edf0f3;
}

.v12-source-list>div:first-child{
    border-top:0;
}

.v12-source-list span{
    font-size:10px;
    font-weight:800;
    letter-spacing:.04em;
    text-transform:uppercase;
    color:#89939d;
}

.v12-source-list strong{
    color:#344054;
    line-height:1.4;
}

.v12-full-button{
    width:100%;
    box-sizing:border-box;
    justify-content:center;
    text-align:center;
}

.v12-mini-list{
    display:grid;
    margin-bottom:14px;
}

.v12-mini-list>div{
    padding:10px 0;
    border-top:1px solid #edf0f3;
}

.v12-mini-list>div:first-child{
    border-top:0;
}

.v12-mini-list strong,
.v12-mini-list span{
    display:block;
}

.v12-mini-list strong{
    color:#344054;
}

.v12-mini-list span{
    margin-top:3px;
    font-size:11px;
    color:#89939d;
}

.v12-muted-copy{
    color:#667085;
    line-height:1.55;
}

.v12-lock-box{
    margin:14px 0;
    padding:13px;
    border:1px solid #ecd8b7;
    border-radius:11px;
    background:#fff9ec;
}

.v12-lock-box strong,
.v12-lock-box span{
    display:block;
}

.v12-lock-box strong{
    color:#6f511b;
}

.v12-lock-box span{
    margin-top:5px;
    font-size:11px;
    line-height:1.45;
    color:#8b6a2d;
}

.v12-warning-panel{
    margin-bottom:18px;
}

.v12-warning-list{
    display:grid;
}

.v12-warning{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:16px;
    padding:11px 0;
    border-top:1px solid #edf0f3;
}

.v12-warning:first-child{
    border-top:0;
}

.v12-warning strong{
    font-size:12px;
    color:#45515f;
}

.v12-warning span{
    font-size:9px;
    font-weight:900;
    letter-spacing:.07em;
}

.v12-warning.blocking span{
    color:#9a3d36;
}

.v12-warning.warning span{
    color:#845f1d;
}

.v12-warning.suggestion span{
    color:#667085;
}

.v12-history{
    margin-top:18px;
}

.v12-version-list{
    display:grid;
}

.v12-version-row{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:16px;
    padding:13px 0;
    border-top:1px solid #edf0f3;
}

.v12-version-row:first-child{
    border-top:0;
}

.v12-version-row strong,
.v12-version-row span{
    display:block;
}

.v12-version-row strong{
    color:#344054;
}

.v12-version-row span{
    margin-top:3px;
    font-size:11px;
    color:#89939d;
}

.v12-version-actions form{
    margin:0;
}


/* ---------------------------------------------------------
   Customer-facing Website Preview
   --------------------------------------------------------- */

.v12-preview-body{
    margin:0;
    background:#fff;
    color:#182230;
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

.v12-preview-toolbar{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:20px;
    padding:10px 22px;
    background:#101828;
    color:#fff;
    font-size:12px;
}

.v12-preview-toolbar strong,
.v12-preview-toolbar span{
    display:block;
}

.v12-preview-toolbar span{
    margin-top:2px;
    color:#aeb8c5;
    font-size:10px;
}

.v12-preview-toolbar a{
    color:#fff;
    font-weight:700;
    text-decoration:none;
}

.v12-public-site{
    --site-accent:#2f7d5b;
    --site-ink:#16231d;
    --site-muted:#65716b;
    --site-soft:#f5f8f6;
    --site-border:#e1e8e4;
}

.v12-public-site.theme-modern{
    --site-accent:#315c8a;
    --site-ink:#182433;
    --site-muted:#687586;
    --site-soft:#f4f7fa;
    --site-border:#dfe6ed;
}

.v12-public-site.theme-bold{
    --site-accent:#996321;
    --site-ink:#251d15;
    --site-muted:#756a5d;
    --site-soft:#faf6ef;
    --site-border:#ebe1d4;
}

.v12-public-container{
    width:min(1120px,calc(100% - 40px));
    margin:0 auto;
}

.v12-public-header{
    position:sticky;
    top:0;
    z-index:10;
    border-bottom:1px solid var(--site-border);
    background:rgba(255,255,255,.96);
    backdrop-filter:blur(10px);
}

.v12-public-header .v12-public-container{
    display:flex;
    justify-content:space-between;
    align-items:center;
    min-height:70px;
    gap:24px;
}

.v12-public-brand{
    color:var(--site-ink);
    font-size:17px;
    font-weight:850;
    text-decoration:none;
}

.v12-public-header nav{
    display:flex;
    gap:22px;
}

.v12-public-header nav a{
    color:var(--site-muted);
    font-size:13px;
    font-weight:700;
    text-decoration:none;
}

.v12-public-hero{
    padding:92px 0 82px;
    background:
        radial-gradient(circle at 88% 10%,var(--site-soft),transparent 42%),
        #fff;
}

.v12-public-hero-grid{
    display:grid;
    grid-template-columns:minmax(0,1.35fr) minmax(250px,.65fr);
    gap:70px;
    align-items:center;
}

.v12-public-eyebrow,
.v12-public-section-heading>span,
.v12-public-copy-section>span{
    display:block;
    margin-bottom:11px;
    color:var(--site-accent);
    font-size:11px;
    font-weight:850;
    letter-spacing:.1em;
    text-transform:uppercase;
}

.v12-public-hero h1{
    max-width:760px;
    margin:0;
    color:var(--site-ink);
    font-size:clamp(40px,6vw,68px);
    line-height:1.03;
    letter-spacing:-.035em;
}

.v12-public-hero p{
    max-width:690px;
    margin:24px 0 0;
    color:var(--site-muted);
    font-size:18px;
    line-height:1.65;
}

.v12-public-button{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    margin-top:28px;
    padding:13px 19px;
    border:0;
    border-radius:10px;
    background:var(--site-accent);
    color:#fff;
    font:inherit;
    font-size:13px;
    font-weight:800;
    text-decoration:none;
}

.v12-public-button:disabled{
    opacity:.55;
    cursor:not-allowed;
}

.v12-public-trust-card{
    padding:26px;
    border:1px solid var(--site-border);
    border-radius:18px;
    background:#fff;
    box-shadow:0 18px 50px rgba(30,45,36,.07);
}

.v12-public-trust-card span,
.v12-public-trust-card strong,
.v12-public-trust-card small{
    display:block;
}

.v12-public-trust-card span{
    color:var(--site-muted);
    font-size:11px;
    font-weight:800;
    letter-spacing:.07em;
    text-transform:uppercase;
}

.v12-public-trust-card strong{
    margin-top:8px;
    color:var(--site-ink);
    font-size:22px;
    line-height:1.25;
}

.v12-public-trust-card small{
    margin-top:12px;
    color:var(--site-muted);
    line-height:1.5;
}

.v12-public-section{
    padding:78px 0;
}

.v12-public-section-alt{
    background:var(--site-soft);
}

.v12-public-section-heading{
    max-width:680px;
    margin-bottom:30px;
}

.v12-public-section-heading h2,
.v12-public-copy-section h2{
    margin:0;
    color:var(--site-ink);
    font-size:34px;
    letter-spacing:-.02em;
}

.v12-public-section-heading p,
.v12-public-copy-section p{
    color:var(--site-muted);
    line-height:1.7;
}

.v12-public-service-grid{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:15px;
}

.v12-public-service-card{
    padding:22px;
    border:1px solid var(--site-border);
    border-radius:15px;
    background:#fff;
}

.v12-public-service-card h3{
    margin:0;
    color:var(--site-ink);
}

.v12-public-service-card p{
    margin:10px 0 17px;
    color:var(--site-muted);
    line-height:1.6;
}

.v12-public-service-card small{
    color:var(--site-accent);
    font-weight:750;
}

.v12-public-copy-section{
    max-width:780px;
    margin-left:0;
}

.v12-public-contact-grid{
    display:grid;
    grid-template-columns:minmax(250px,.75fr) minmax(0,1.25fr);
    gap:18px;
}

.v12-public-contact-card,
.v12-public-request-card{
    padding:24px;
    border:1px solid var(--site-border);
    border-radius:16px;
    background:#fff;
}

.v12-public-contact-card>div{
    padding:13px 0;
    border-top:1px solid var(--site-border);
}

.v12-public-contact-card>div:first-child{
    border-top:0;
}

.v12-public-contact-card span,
.v12-public-contact-card strong{
    display:block;
}

.v12-public-contact-card span{
    color:var(--site-muted);
    font-size:11px;
    font-weight:800;
    text-transform:uppercase;
}

.v12-public-contact-card strong{
    margin-top:5px;
    color:var(--site-ink);
}

.v12-public-request-card h3{
    margin:0;
    color:var(--site-ink);
    font-size:22px;
}

.v12-public-request-card>p{
    color:var(--site-muted);
    line-height:1.6;
}

.v12-public-question-preview{
    display:grid;
    gap:12px;
    margin-top:20px;
}

.v12-public-question-preview label{
    display:grid;
    gap:6px;
}

.v12-public-question-preview label>span{
    color:var(--site-ink);
    font-size:12px;
    font-weight:750;
}

.v12-public-question-preview input,
.v12-public-question-preview textarea,
.v12-public-question-preview select{
    box-sizing:border-box;
    width:100%;
    padding:11px;
    border:1px solid var(--site-border);
    border-radius:9px;
    background:#fafbfa;
    color:#7b847f;
    font:inherit;
}

.v12-public-muted{
    color:var(--site-muted);
}

.v12-public-footer{
    padding:32px 0;
    border-top:1px solid var(--site-border);
}

.v12-public-footer .v12-public-container{
    display:flex;
    justify-content:space-between;
    gap:20px;
}

.v12-public-footer strong{
    color:var(--site-ink);
}

.v12-public-footer span{
    color:var(--site-muted);
    font-size:12px;
}


/* ---------------------------------------------------------
   Responsive behavior
   --------------------------------------------------------- */

@media(max-width:1000px){

    .v12-studio-layout{
        grid-template-columns:1fr;
    }

    .v12-studio-rail{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }

    .v12-studio-rail .v12-source-card:last-child{
        grid-column:1/-1;
    }

    .v12-public-service-grid{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }
}


@media(max-width:760px){

    .v12-studio-intro{
        grid-template-columns:1fr;
    }

    .v12-readiness-card{
        align-items:flex-start;
        text-align:left;
        min-height:0;
    }

    .v12-toggle-grid,
    .v12-studio-rail{
        grid-template-columns:1fr;
    }

    .v12-studio-rail .v12-source-card:last-child{
        grid-column:auto;
    }

    .v12-save-bar,
    .v12-version-row{
        align-items:stretch;
        flex-direction:column;
    }

    .v12-save-bar .btn,
    .v12-version-actions .btn{
        width:100%;
    }

    .v12-preview-toolbar{
        align-items:flex-start;
        flex-direction:column;
    }

    .v12-public-header .v12-public-container{
        align-items:flex-start;
        flex-direction:column;
        padding:16px 0;
    }

    .v12-public-header nav{
        flex-wrap:wrap;
        gap:12px 18px;
    }

    .v12-public-hero{
        padding:60px 0;
    }

    .v12-public-hero-grid,
    .v12-public-contact-grid{
        grid-template-columns:1fr;
        gap:28px;
    }

    .v12-public-service-grid{
        grid-template-columns:1fr;
    }

    .v12-public-footer .v12-public-container{
        flex-direction:column;
    }
}


@media(max-width:520px){

    .v12-public-container{
        width:min(100% - 28px,1120px);
    }

    .v12-public-hero h1{
        font-size:38px;
    }

    .v12-public-section{
        padding:58px 0;
    }
}
'''


# ============================================================
# WRITE EVERYTHING
# ============================================================

write(
    APP_FILE,
    app_text,
)

write(
    BASE_TEMPLATE,
    base_text,
)

write(
    CONFIG_TEMPLATE,
    config_text,
)

write(
    STUDIO_TEMPLATE,
    STUDIO_HTML,
)

write(
    PREVIEW_TEMPLATE,
    PREVIEW_HTML,
)

write(
    V12_CSS,
    V12_CSS_TEXT,
)


# ============================================================
# POST-INSTALL VERIFICATION
# ============================================================

final_app = read(APP_FILE)
final_base = read(BASE_TEMPLATE)
final_config = read(CONFIG_TEMPLATE)

required_app_markers = [
    "def website_studio(bid):",
    "def save_website_studio(bid):",
    "def select_website_preview(bid):",
    "def website_preview(bid):",
    "from services.website_renderer import (",
]

required_base_markers = [
    "filename='v12.css'",
    "'website_studio'",
    "'website_preview'",
]

required_config_markers = [
    "url_for('website_studio', bid=business.id)",
]

for marker in required_app_markers:
    if marker not in final_app:
        fail(
            "Post-install app.py verification failed: "
            + marker
        )

for marker in required_base_markers:
    if marker not in final_base:
        fail(
            "Post-install base.html verification failed: "
            + marker
        )

for marker in required_config_markers:
    if marker not in final_config:
        fail(
            "Post-install Business Configuration verification "
            "failed: "
            + marker
        )

for path in (
    STUDIO_TEMPLATE,
    PREVIEW_TEMPLATE,
    V12_CSS,
):
    if not path.exists():
        fail(
            f"Expected generated file missing: {path}"
        )


print()
print("Website Studio UI installation: PASS")
print()
print("Created:")
print("  templates/website_studio.html")
print("  templates/website_preview.html")
print("  static/v12.css")
print()
print("Modified:")
print("  app.py")
print("  templates/base.html")
print("  templates/business_configuration.html")
print()
print("Safety state:")
print("  Live publishing: LOCKED")
print("  Public form submission: NOT INSTALLED")
print("  External provider actions: NOT INSTALLED")
print()
print("Next: compile and inspect the Git diff.")
print()