import json

from services.db import connect, now_iso
from services.business_config import ensure_business_config_schema
from services.product_foundation import ensure_product_schema


WEBSITE_PROJECT_STATUSES = {
    "DRAFT",
    "PREVIEW_READY",
    "NEEDS_ATTENTION",
    "READY_TO_PUBLISH",
}

WEBSITE_VERSION_STATUSES = {
    "DRAFT",
    "SUPERSEDED",
}

ALLOWED_THEME_KEYS = {
    "classic",
    "modern",
    "bold",
}

DEFAULT_PRESENTATION = {
    "theme_key": "classic",
    "hero_headline": "",
    "hero_supporting_text": "",
    "primary_cta_label": "Request Service",
    "about_copy": "",
    "contact_intro": "",
    "show_services": True,
    "show_about": True,
    "show_contact": True,
    "seo_title": "",
    "seo_description": "",
}


def _table_exists(conn, table_name):
    return conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone() is not None


def _business_exists(conn, business_id):
    return conn.execute(
        "SELECT 1 FROM businesses WHERE id=?",
        (business_id,),
    ).fetchone() is not None


def ensure_website_studio_schema(conn=None):
    """
    Create only Website Studio-owned persistence.

    Canonical business facts remain in the existing Business OS tables.
    Website Studio stores project lifecycle and presentation-version state.
    """
    own_connection = conn is None
    conn = conn or connect()

    # Website Studio depends on canonical product/configuration truth.
    ensure_product_schema(conn)
    ensure_business_config_schema(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS website_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK(status IN (
                    'DRAFT',
                    'PREVIEW_READY',
                    'NEEDS_ATTENTION',
                    'READY_TO_PUBLISH'
                )),
            current_draft_version_id INTEGER,
            preview_version_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id)
                REFERENCES businesses(id)
                ON DELETE CASCADE
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS website_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK(status IN (
                    'DRAFT',
                    'SUPERSEDED'
                )),
            presentation_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id)
                REFERENCES website_projects(id)
                ON DELETE CASCADE,
            UNIQUE(project_id, version_number)
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_projects_business
        ON website_projects(business_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_versions_project
        ON website_versions(project_id, version_number)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_website_versions_status
        ON website_versions(project_id, status)
        """
    )

    # SQLite cannot safely declare these two circular foreign keys in the
    # CREATE TABLE above before website_versions exists. We therefore enforce
    # ownership in service-layer queries and verification tests.
    conn.commit()

    if own_connection:
        conn.close()


def _normalize_presentation(values):
    values = values or {}

    theme_key = (values.get("theme_key") or DEFAULT_PRESENTATION["theme_key"]).strip()
    if theme_key not in ALLOWED_THEME_KEYS:
        theme_key = DEFAULT_PRESENTATION["theme_key"]

    def clean_text(key, max_length):
        value = values.get(key)
        if value is None:
            value = DEFAULT_PRESENTATION[key]
        return str(value).strip()[:max_length]

    return {
        "theme_key": theme_key,
        "hero_headline": clean_text("hero_headline", 160),
        "hero_supporting_text": clean_text("hero_supporting_text", 500),
        "primary_cta_label": clean_text("primary_cta_label", 80)
        or DEFAULT_PRESENTATION["primary_cta_label"],
        "about_copy": clean_text("about_copy", 2000),
        "contact_intro": clean_text("contact_intro", 500),
        "show_services": bool(
            values.get("show_services", DEFAULT_PRESENTATION["show_services"])
        ),
        "show_about": bool(
            values.get("show_about", DEFAULT_PRESENTATION["show_about"])
        ),
        "show_contact": bool(
            values.get("show_contact", DEFAULT_PRESENTATION["show_contact"])
        ),
        "seo_title": clean_text("seo_title", 160),
        "seo_description": clean_text("seo_description", 320),
    }


def _decode_presentation(raw_json):
    try:
        data = json.loads(raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    return _normalize_presentation(data)


def _create_initial_version(conn, project_id):
    timestamp = now_iso()

    cur = conn.execute(
        """
        INSERT INTO website_versions (
            project_id,
            version_number,
            status,
            presentation_json,
            created_at,
            updated_at
        )
        VALUES (?, 1, 'DRAFT', ?, ?, ?)
        """,
        (
            project_id,
            json.dumps(DEFAULT_PRESENTATION, sort_keys=True),
            timestamp,
            timestamp,
        ),
    )

    version_id = cur.lastrowid

    conn.execute(
        """
        UPDATE website_projects
        SET current_draft_version_id=?,
            updated_at=?
        WHERE id=?
        """,
        (version_id, timestamp, project_id),
    )

    return version_id


def get_or_create_project(conn, business_id):
    """
    Resolve the Website Studio project for exactly one canonical business.

    This function never guesses tenant ownership.
    """
    ensure_website_studio_schema(conn)

    if not _business_exists(conn, business_id):
        return None

    project = conn.execute(
        """
        SELECT *
        FROM website_projects
        WHERE business_id=?
        """,
        (business_id,),
    ).fetchone()

    if project:
        if project["current_draft_version_id"] is None:
            _create_initial_version(conn, project["id"])
            conn.commit()

        return conn.execute(
            """
            SELECT *
            FROM website_projects
            WHERE id=?
            """,
            (project["id"],),
        ).fetchone()

    timestamp = now_iso()

    cur = conn.execute(
        """
        INSERT INTO website_projects (
            business_id,
            status,
            created_at,
            updated_at
        )
        VALUES (?, 'DRAFT', ?, ?)
        """,
        (business_id, timestamp, timestamp),
    )

    project_id = cur.lastrowid
    _create_initial_version(conn, project_id)
    conn.commit()

    return conn.execute(
        """
        SELECT *
        FROM website_projects
        WHERE id=?
        """,
        (project_id,),
    ).fetchone()


def get_version_for_business(conn, business_id, version_id):
    """
    Tenant-safe Website Studio version lookup.

    A version ID alone is never considered sufficient proof of ownership.
    """
    ensure_website_studio_schema(conn)

    return conn.execute(
        """
        SELECT
            v.*,
            p.business_id,
            p.status AS project_status
        FROM website_versions v
        JOIN website_projects p
          ON p.id = v.project_id
        WHERE v.id=?
          AND p.business_id=?
        """,
        (version_id, business_id),
    ).fetchone()


def current_draft(conn, business_id):
    project = get_or_create_project(conn, business_id)
    if not project:
        return None

    version = get_version_for_business(
        conn,
        business_id,
        project["current_draft_version_id"],
    )

    if not version:
        return None

    result = dict(version)
    result["presentation"] = _decode_presentation(
        version["presentation_json"]
    )
    return result


def canonical_website_context(conn, business_id):
    """
    Read canonical business truth for Website Studio.

    This function intentionally reads from existing authoritative tables.
    It does not create Website Studio copies of business facts.
    """
    ensure_website_studio_schema(conn)

    business = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE id=?
        """,
        (business_id,),
    ).fetchone()

    if not business:
        return None

    profile = conn.execute(
        """
        SELECT *
        FROM client_profiles
        WHERE business_id=?
        """,
        (business_id,),
    ).fetchone()

    services = conn.execute(
        """
        SELECT *
        FROM business_services
        WHERE business_id=?
          AND active=1
          AND public=1
        ORDER BY sort_order, id
        """,
        (business_id,),
    ).fetchall()

    schema = conn.execute(
        """
        SELECT *
        FROM intake_schemas
        WHERE business_id=?
          AND status='Active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (business_id,),
    ).fetchone()

    questions = []

    if schema:
        questions = conn.execute(
            """
            SELECT
                q.*,
                s.name AS service_name
            FROM intake_questions q
            LEFT JOIN business_services s
              ON s.id=q.service_id
             AND s.business_id=?
            WHERE q.schema_id=?
              AND q.active=1
            ORDER BY q.sort_order, q.id
            """,
            (business_id, schema["id"]),
        ).fetchall()

    return {
        "business": dict(business),
        "profile": dict(profile) if profile else {},
        "services": [dict(row) for row in services],
        "intake_schema": dict(schema) if schema else None,
        "intake_questions": [dict(row) for row in questions],
    }


def website_readiness(conn, business_id):
    """
    Website-specific readiness.

    This is intentionally different from full client activation readiness.
    A business should not need live Retell routing or live automation merely
    to create and preview a truthful website.
    """
    context = canonical_website_context(conn, business_id)

    if not context:
        return {
            "ready": False,
            "score": 0,
            "checks": [],
            "blockers": ["Business not found."],
        }

    business = context["business"]
    profile = context["profile"]
    services = context["services"]

    checks = [
        {
            "key": "business_name",
            "label": "Business name",
            "ok": bool((business.get("name") or "").strip()),
            "required": True,
        },
        {
            "key": "contact_channel",
            "label": "Customer contact channel",
            "ok": bool(
                (business.get("phone") or "").strip()
                or (business.get("email") or "").strip()
            ),
            "required": True,
        },
        {
            "key": "public_services",
            "label": "Public service catalog",
            "ok": bool(services),
            "required": True,
        },
        {
            "key": "service_area",
            "label": "Service area",
            "ok": bool((profile.get("service_area") or "").strip()),
            "required": False,
        },
        {
            "key": "business_hours",
            "label": "Business hours",
            "ok": bool((profile.get("business_hours") or "").strip()),
            "required": False,
        },
    ]

    required_checks = [item for item in checks if item["required"]]
    required_passed = sum(1 for item in required_checks if item["ok"])

    score = round(
        (sum(1 for item in checks if item["ok"]) / len(checks)) * 100
    ) if checks else 0

    blockers = [
        item["label"]
        for item in required_checks
        if not item["ok"]
    ]

    return {
        "ready": required_passed == len(required_checks),
        "score": score,
        "checks": checks,
        "blockers": blockers,
    }


def website_studio_view(conn, business_id):
    """
    Assemble the read model that future Website Studio routes/templates use.
    """
    project = get_or_create_project(conn, business_id)

    if not project:
        return None

    draft = current_draft(conn, business_id)
    context = canonical_website_context(conn, business_id)
    readiness = website_readiness(conn, business_id)

    return {
        "project": dict(project),
        "draft": draft,
        "canonical": context,
        "readiness": readiness,
        "allowed_themes": sorted(ALLOWED_THEME_KEYS),
    }