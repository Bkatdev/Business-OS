import json

from services.website_studio import (
    DEFAULT_PRESENTATION,
    _decode_presentation,
    _normalize_presentation,
    ensure_website_studio_schema,
    get_or_create_project,
    get_version_for_business,
    website_readiness,
)


# ---------------------------------------------------------------------
# WEBSITE STUDIO VERSIONING
# ---------------------------------------------------------------------
#
# Business Configuration owns canonical business truth.
#
# This module owns only Website Studio presentation-version behavior:
#
# - safe presentation normalization
# - immutable version creation
# - tenant-safe version history
# - preview-version selection
# - project readiness-state synchronization
#
# It does NOT:
#
# - publish websites
# - send SMS
# - schedule appointments
# - call external providers
# - modify canonical business facts
# - bypass the v11 governed execution spine
#
# Every version operation resolves ownership through:
#
# website_versions
#     -> website_projects
#         -> canonical business_id
#
# A version ID by itself is never trusted as proof of ownership.
# ---------------------------------------------------------------------


MAX_VERSION_HISTORY = 1000


class WebsiteVersionError(ValueError):
    """Base error for safe Website Studio version operations."""


class WebsiteProjectNotFound(WebsiteVersionError):
    """Raised when a canonical business cannot resolve a website project."""


class WebsiteVersionNotFound(WebsiteVersionError):
    """Raised when a version cannot be resolved for the requested tenant."""


class WebsiteVersionConflict(WebsiteVersionError):
    """Raised when an edit is based on a stale Website Studio version."""


def _project_for_business(conn, business_id):
    """
    Resolve exactly one Website Studio project for a canonical business.

    get_or_create_project() already fails closed when the canonical
    business does not exist.
    """
    ensure_website_studio_schema(conn)

    project = get_or_create_project(
        conn,
        business_id,
    )

    if not project:
        raise WebsiteProjectNotFound(
            "Website Studio project could not be resolved "
            "for this business."
        )

    return project


def _presentation_json(presentation):
    """
    Produce deterministic JSON for Website Studio presentation state.
    """
    normalized = _normalize_presentation(
        presentation or {}
    )

    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    )


def _version_to_dict(version):
    """
    Convert a SQLite row into the safe Website Studio version read model.
    """
    if not version:
        return None

    result = dict(version)

    result["presentation"] = _decode_presentation(
        result.get("presentation_json")
    )

    return result


def _current_version_row(conn, project):
    """
    Resolve the current draft while enforcing project ownership.
    """
    version_id = project["current_draft_version_id"]

    if version_id is None:
        return None

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
          AND v.project_id=?
          AND p.business_id=?
        """,
        (
            version_id,
            project["id"],
            project["business_id"],
        ),
    ).fetchone()


def _next_version_number(conn, project_id):
    """
    Determine the next monotonically increasing presentation version.
    """
    row = conn.execute(
        """
        SELECT COALESCE(MAX(version_number), 0)
        FROM website_versions
        WHERE project_id=?
        """,
        (project_id,),
    ).fetchone()

    current_max = int(row[0] or 0)

    if current_max >= MAX_VERSION_HISTORY:
        raise WebsiteVersionError(
            "Website Studio version limit reached. "
            "Review version retention before continuing."
        )

    return current_max + 1


def list_versions(conn, business_id, limit=50):
    """
    Return tenant-safe Website Studio version history.

    The caller cannot use this function to enumerate another business's
    versions because ownership is enforced through website_projects.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50

    limit = max(
        1,
        min(limit, 100),
    )

    rows = conn.execute(
        """
        SELECT
            v.*,
            p.business_id,
            p.status AS project_status
        FROM website_versions v
        JOIN website_projects p
          ON p.id = v.project_id
        WHERE v.project_id=?
          AND p.business_id=?
        ORDER BY
            v.version_number DESC,
            v.id DESC
        LIMIT ?
        """,
        (
            project["id"],
            business_id,
            limit,
        ),
    ).fetchall()

    return [
        _version_to_dict(row)
        for row in rows
    ]


def get_current_version(conn, business_id):
    """
    Return the current Website Studio draft for one business.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    row = _current_version_row(
        conn,
        project,
    )

    if not row:
        raise WebsiteVersionNotFound(
            "Current Website Studio draft could not be resolved."
        )

    return _version_to_dict(row)


def get_preview_version(conn, business_id):
    """
    Resolve the explicitly selected preview version.

    Preview never guesses.

    If no preview version has been selected, this returns None rather
    than silently exposing the current draft as a public preview.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    preview_version_id = project["preview_version_id"]

    if preview_version_id is None:
        return None

    version = get_version_for_business(
        conn,
        business_id,
        preview_version_id,
    )

    if not version:
        return None

    if version["project_id"] != project["id"]:
        return None

    return _version_to_dict(version)


def create_version(
    conn,
    business_id,
    presentation,
    expected_current_version_id=None,
):
    """
    Create a new immutable Website Studio presentation version.

    Existing versions are not overwritten.

    expected_current_version_id provides optimistic concurrency
    protection. A stale browser/editor cannot silently overwrite work
    created after the page was loaded.

    This function changes Website Studio presentation state only.
    It never modifies canonical Business Configuration.
    """
    ensure_website_studio_schema(conn)

    project = _project_for_business(
        conn,
        business_id,
    )

    current = _current_version_row(
        conn,
        project,
    )

    if not current:
        raise WebsiteVersionNotFound(
            "Current Website Studio draft could not be resolved."
        )

    if expected_current_version_id is not None:
        try:
            expected_id = int(
                expected_current_version_id
            )
        except (TypeError, ValueError):
            raise WebsiteVersionConflict(
                "Invalid expected Website Studio version."
            )

        if expected_id != current["id"]:
            raise WebsiteVersionConflict(
                "This Website Studio draft changed after it was loaded. "
                "Reload the latest version before saving."
            )

    normalized = _normalize_presentation(
        presentation or {}
    )

    current_presentation = _decode_presentation(
        current["presentation_json"]
    )

    # Avoid generating meaningless duplicate versions when the normalized
    # presentation has not actually changed.
    if normalized == current_presentation:
        result = _version_to_dict(current)
        result["created_new_version"] = False
        return result

    next_number = _next_version_number(
        conn,
        project["id"],
    )

    timestamp = __import__(
        "services.db",
        fromlist=["now_iso"],
    ).now_iso()

    try:
        cursor = conn.execute(
            """
            INSERT INTO website_versions (
                project_id,
                version_number,
                status,
                presentation_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, 'DRAFT', ?, ?, ?)
            """,
            (
                project["id"],
                next_number,
                _presentation_json(normalized),
                timestamp,
                timestamp,
            ),
        )

        new_version_id = cursor.lastrowid

        # The previous current draft remains historical evidence.
        conn.execute(
            """
            UPDATE website_versions
            SET status='SUPERSEDED',
                updated_at=?
            WHERE id=?
              AND project_id=?
              AND status='DRAFT'
            """,
            (
                timestamp,
                current["id"],
                project["id"],
            ),
        )

        # Any presentation edit means the new draft has not yet been
        # explicitly selected for preview.
        #
        # We intentionally preserve preview_version_id so an already
        # reviewed preview does not silently change when a newer draft
        # is edited.
        conn.execute(
            """
            UPDATE website_projects
            SET current_draft_version_id=?,
                status='DRAFT',
                updated_at=?
            WHERE id=?
              AND business_id=?
            """,
            (
                new_version_id,
                timestamp,
                project["id"],
                business_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    version = get_version_for_business(
        conn,
        business_id,
        new_version_id,
    )

    if not version:
        raise WebsiteVersionNotFound(
            "New Website Studio version was created but "
            "could not be safely resolved."
        )

    result = _version_to_dict(version)
    result["created_new_version"] = True

    return result


def update_presentation(
    conn,
    business_id,
    changes,
    expected_current_version_id=None,
):
    """
    Safely update Website Studio presentation state.

    The caller may send only the fields it wants to change.

    Unknown keys are ignored by the canonical presentation normalizer.
    Canonical business facts are not accepted here.
    """
    current = get_current_version(
        conn,
        business_id,
    )

    merged = dict(
        current["presentation"]
    )

    if isinstance(changes, dict):
        for key, value in changes.items():
            if key in DEFAULT_PRESENTATION:
                merged[key] = value

    return create_version(
        conn,
        business_id,
        merged,
        expected_current_version_id=(
            expected_current_version_id
        ),
    )


def select_preview_version(
    conn,
    business_id,
    version_id,
):
    """
    Explicitly select one tenant-owned version for safe preview.

    This does NOT publish anything.
    """
    ensure_website_studio_schema(conn)

    project = _project_for_business(
        conn,
        business_id,
    )

    try:
        version_id = int(version_id)
    except (TypeError, ValueError):
        raise WebsiteVersionNotFound(
            "Invalid Website Studio version."
        )

    version = get_version_for_business(
        conn,
        business_id,
        version_id,
    )

    if (
        not version
        or version["project_id"] != project["id"]
    ):
        raise WebsiteVersionNotFound(
            "Website Studio version does not belong "
            "to this business."
        )

    timestamp = __import__(
        "services.db",
        fromlist=["now_iso"],
    ).now_iso()

    try:
        conn.execute(
            """
            UPDATE website_projects
            SET preview_version_id=?,
                status='PREVIEW_READY',
                updated_at=?
            WHERE id=?
              AND business_id=?
            """,
            (
                version_id,
                timestamp,
                project["id"],
                business_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return get_preview_version(
        conn,
        business_id,
    )


def clear_preview_version(
    conn,
    business_id,
):
    """
    Remove explicit preview selection.

    No website is published or unpublished because live publishing does
    not exist in v12.0.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    timestamp = __import__(
        "services.db",
        fromlist=["now_iso"],
    ).now_iso()

    try:
        conn.execute(
            """
            UPDATE website_projects
            SET preview_version_id=NULL,
                status='DRAFT',
                updated_at=?
            WHERE id=?
              AND business_id=?
            """,
            (
                timestamp,
                project["id"],
                business_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return True


def synchronize_readiness(
    conn,
    business_id,
):
    """
    Synchronize Website Studio project state with website readiness.

    This is a local readiness transition only.

    READY_TO_PUBLISH means:
        "Website Studio believes the configured project has the required
        canonical information to reach a future publishing boundary."

    It does NOT mean:
        - published
        - externally hosted
        - provider accepted
        - customer reachable

    No live provider action occurs here.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    readiness = website_readiness(
        conn,
        business_id,
    )

    preview = get_preview_version(
        conn,
        business_id,
    )

    if readiness["ready"] and preview:
        next_status = "READY_TO_PUBLISH"

    elif readiness["ready"]:
        next_status = "DRAFT"

    else:
        next_status = "NEEDS_ATTENTION"

    timestamp = __import__(
        "services.db",
        fromlist=["now_iso"],
    ).now_iso()

    try:
        conn.execute(
            """
            UPDATE website_projects
            SET status=?,
                updated_at=?
            WHERE id=?
              AND business_id=?
            """,
            (
                next_status,
                timestamp,
                project["id"],
                business_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    updated = conn.execute(
        """
        SELECT *
        FROM website_projects
        WHERE id=?
          AND business_id=?
        """,
        (
            project["id"],
            business_id,
        ),
    ).fetchone()

    return {
        "project": dict(updated),
        "readiness": readiness,
        "preview_selected": bool(preview),
    }


def version_summary(conn, business_id):
    """
    Small tenant-safe read model for the future Website Studio UI.
    """
    project = _project_for_business(
        conn,
        business_id,
    )

    current = get_current_version(
        conn,
        business_id,
    )

    preview = get_preview_version(
        conn,
        business_id,
    )

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM website_versions
        WHERE project_id=?
        """,
        (project["id"],),
    ).fetchone()[0]

    return {
        "project": dict(project),
        "current_version": current,
        "preview_version": preview,
        "version_count": int(count or 0),
        "live_publishing_enabled": False,
    }