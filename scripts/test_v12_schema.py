import os
import sys
import tempfile
from pathlib import Path


# ------------------------------------------------------------
# REPOSITORY IMPORT SETUP
# ------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import services.db as db
from services.website_studio import (
    current_draft,
    get_or_create_project,
    get_version_for_business,
)
from services.website_versions import (
    WebsiteVersionConflict,
    WebsiteVersionNotFound,
    clear_preview_version,
    create_version,
    get_current_version,
    get_preview_version,
    list_versions,
    select_preview_version,
    synchronize_readiness,
    update_presentation,
    version_summary,
)


def remove_test_database(test_db):
    """
    Remove the isolated SQLite database and its WAL/SHM files.
    """
    for path in (
        test_db,
        Path(str(test_db) + "-wal"),
        Path(str(test_db) + "-shm"),
    ):
        if path.exists():
            os.remove(path)


def create_test_business(conn, name, suffix):
    """
    Create a canonical business using the actual v11.1 businesses schema.
    """
    timestamp = db.now_iso()

    return conn.execute(
        """
        INSERT INTO businesses (
            name,
            city,
            category,
            website,
            phone,
            email,
            status,
            notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            "Test City",
            "Local Service Business",
            "",
            f"555-01{suffix}",
            f"test{suffix}@example.com",
            "Not Contacted",
            "Isolated Website Studio test record.",
            timestamp,
        ),
    ).lastrowid


def print_check(label, value):
    print(f"{label}: {value}")


def main():
    # ------------------------------------------------------------
    # ISOLATED DATABASE
    # ------------------------------------------------------------
    #
    # This script MUST NOT touch the normal business_os.db.

    test_db = (
        Path(tempfile.gettempdir())
        / "business_os_v12_schema_test.db"
    )

    remove_test_database(test_db)

    db.DB_PATH = test_db

    print("Initializing isolated v12 test database...")
    print("DB:", test_db)

    db.init_db()

    conn = db.connect()

    try:
        # --------------------------------------------------------
        # 1. SCHEMA + DATABASE SAFETY
        # --------------------------------------------------------

        website_projects_exists = bool(
            conn.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table'
                  AND name='website_projects'
                """
            ).fetchone()
        )

        website_versions_exists = bool(
            conn.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table'
                  AND name='website_versions'
                """
            ).fetchone()
        )

        foreign_keys_enabled = (
            conn.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
            == 1
        )

        initial_integrity = (
            conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            == "ok"
        )

        print()
        print("=== 1. v12 SCHEMA ===")
        print_check(
            "website_projects",
            website_projects_exists,
        )
        print_check(
            "website_versions",
            website_versions_exists,
        )
        print_check(
            "foreign_keys",
            foreign_keys_enabled,
        )
        print_check(
            "integrity",
            initial_integrity,
        )

        # --------------------------------------------------------
        # 2. CANONICAL TENANTS
        # --------------------------------------------------------

        business_a = create_test_business(
            conn,
            "V12 Test Business A",
            "00",
        )

        business_b = create_test_business(
            conn,
            "V12 Test Business B",
            "01",
        )

        conn.commit()

        business_a_exists = (
            conn.execute(
                """
                SELECT id
                FROM businesses
                WHERE id=?
                """,
                (business_a,),
            ).fetchone()
            is not None
        )

        business_b_exists = (
            conn.execute(
                """
                SELECT id
                FROM businesses
                WHERE id=?
                """,
                (business_b,),
            ).fetchone()
            is not None
        )

        print()
        print("=== 2. CANONICAL BUSINESSES ===")
        print_check(
            "business_a_created",
            business_a_exists,
        )
        print_check(
            "business_b_created",
            business_b_exists,
        )

        # --------------------------------------------------------
        # 3. PROJECT CREATION + IDEMPOTENCY
        # --------------------------------------------------------

        project_a = get_or_create_project(
            conn,
            business_a,
        )

        project_a_again = get_or_create_project(
            conn,
            business_a,
        )

        project_b = get_or_create_project(
            conn,
            business_b,
        )

        project_a_created = bool(project_a)
        project_b_created = bool(project_b)

        same_project_on_repeat = (
            bool(project_a)
            and bool(project_a_again)
            and project_a["id"] == project_a_again["id"]
        )

        project_a_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM website_projects
            WHERE business_id=?
            """,
            (business_a,),
        ).fetchone()[0]

        exactly_one_project_for_a = (
            project_a_count == 1
        )

        nonexistent_business_id = 999999

        nonexistent_project = get_or_create_project(
            conn,
            nonexistent_business_id,
        )

        nonexistent_business_blocked = (
            nonexistent_project is None
        )

        print()
        print("=== 3. WEBSITE PROJECTS ===")
        print_check(
            "project_a_created",
            project_a_created,
        )
        print_check(
            "project_b_created",
            project_b_created,
        )
        print_check(
            "same_project_on_repeat",
            same_project_on_repeat,
        )
        print_check(
            "exactly_one_project_for_a",
            exactly_one_project_for_a,
        )
        print_check(
            "nonexistent_business_blocked",
            nonexistent_business_blocked,
        )

        # --------------------------------------------------------
        # 4. INITIAL VERSION
        # --------------------------------------------------------

        initial_a = current_draft(
            conn,
            business_a,
        )

        initial_version_created = bool(initial_a)

        initial_version_number_correct = (
            bool(initial_a)
            and initial_a["version_number"] == 1
        )

        initial_version_is_draft = (
            bool(initial_a)
            and initial_a["status"] == "DRAFT"
        )

        initial_version_owned_by_a = (
            bool(initial_a)
            and initial_a["business_id"] == business_a
        )

        initial_presentation_loaded = (
            bool(initial_a)
            and isinstance(
                initial_a.get("presentation"),
                dict,
            )
        )

        print()
        print("=== 4. INITIAL VERSION ===")
        print_check(
            "initial_version_created",
            initial_version_created,
        )
        print_check(
            "initial_version_number_correct",
            initial_version_number_correct,
        )
        print_check(
            "initial_version_is_draft",
            initial_version_is_draft,
        )
        print_check(
            "initial_version_owned_by_a",
            initial_version_owned_by_a,
        )
        print_check(
            "initial_presentation_loaded",
            initial_presentation_loaded,
        )

        # --------------------------------------------------------
        # 5. CREATE NEW PRESENTATION VERSION
        # --------------------------------------------------------

        version_2 = update_presentation(
            conn,
            business_a,
            {
                "theme_key": "modern",
                "hero_headline": "Reliable help starts here",
                "hero_supporting_text": (
                    "Tell us what you need and our team "
                    "will review your request."
                ),
                "primary_cta_label": "Request Service",
                "about_copy": (
                    "Professional local service with a "
                    "clear customer experience."
                ),
            },
            expected_current_version_id=initial_a["id"],
        )

        version_2_created = (
            bool(version_2)
            and version_2["created_new_version"] is True
        )

        version_2_number_correct = (
            bool(version_2)
            and version_2["version_number"] == 2
        )

        version_2_owned_by_a = (
            bool(version_2)
            and version_2["business_id"] == business_a
        )

        version_2_content_correct = (
            bool(version_2)
            and version_2["presentation"]["theme_key"]
            == "modern"
            and version_2["presentation"]["hero_headline"]
            == "Reliable help starts here"
        )

        current_after_edit = get_current_version(
            conn,
            business_a,
        )

        current_points_to_v2 = (
            current_after_edit["id"] == version_2["id"]
        )

        old_version_row = get_version_for_business(
            conn,
            business_a,
            initial_a["id"],
        )

        old_version_superseded = (
            bool(old_version_row)
            and old_version_row["status"]
            == "SUPERSEDED"
        )

        print()
        print("=== 5. VERSION CREATION ===")
        print_check(
            "version_2_created",
            version_2_created,
        )
        print_check(
            "version_2_number_correct",
            version_2_number_correct,
        )
        print_check(
            "version_2_owned_by_a",
            version_2_owned_by_a,
        )
        print_check(
            "version_2_content_correct",
            version_2_content_correct,
        )
        print_check(
            "current_points_to_v2",
            current_points_to_v2,
        )
        print_check(
            "old_version_superseded",
            old_version_superseded,
        )

        # --------------------------------------------------------
        # 6. UNCHANGED SAVE DEDUPLICATION
        # --------------------------------------------------------

        duplicate_save = update_presentation(
            conn,
            business_a,
            {
                "theme_key": "modern",
                "hero_headline": "Reliable help starts here",
                "hero_supporting_text": (
                    "Tell us what you need and our team "
                    "will review your request."
                ),
                "primary_cta_label": "Request Service",
                "about_copy": (
                    "Professional local service with a "
                    "clear customer experience."
                ),
            },
            expected_current_version_id=version_2["id"],
        )

        unchanged_save_reused_version = (
            duplicate_save["id"] == version_2["id"]
            and duplicate_save["created_new_version"] is False
        )

        version_count_after_duplicate = conn.execute(
            """
            SELECT COUNT(*)
            FROM website_versions
            WHERE project_id=?
            """,
            (project_a["id"],),
        ).fetchone()[0]

        duplicate_did_not_create_version = (
            version_count_after_duplicate == 2
        )

        print()
        print("=== 6. UNCHANGED SAVE DEDUPLICATION ===")
        print_check(
            "unchanged_save_reused_version",
            unchanged_save_reused_version,
        )
        print_check(
            "duplicate_did_not_create_version",
            duplicate_did_not_create_version,
        )

        # --------------------------------------------------------
        # 7. STALE EDIT PROTECTION
        # --------------------------------------------------------

        stale_edit_blocked = False

        try:
            update_presentation(
                conn,
                business_a,
                {
                    "hero_headline": (
                        "This stale edit must not win"
                    ),
                },
                expected_current_version_id=initial_a["id"],
            )

        except WebsiteVersionConflict:
            stale_edit_blocked = True

        current_after_stale_attempt = get_current_version(
            conn,
            business_a,
        )

        stale_edit_did_not_mutate_current = (
            current_after_stale_attempt["id"]
            == version_2["id"]
            and current_after_stale_attempt[
                "presentation"
            ]["hero_headline"]
            == "Reliable help starts here"
        )

        print()
        print("=== 7. STALE EDIT PROTECTION ===")
        print_check(
            "stale_edit_blocked",
            stale_edit_blocked,
        )
        print_check(
            "stale_edit_did_not_mutate_current",
            stale_edit_did_not_mutate_current,
        )

        # --------------------------------------------------------
        # 8. TENANT ISOLATION
        # --------------------------------------------------------

        cross_tenant_version_lookup = (
            get_version_for_business(
                conn,
                business_b,
                version_2["id"],
            )
        )

        cross_tenant_lookup_blocked = (
            cross_tenant_version_lookup is None
        )

        cross_tenant_preview_blocked = False

        try:
            select_preview_version(
                conn,
                business_b,
                version_2["id"],
            )

        except WebsiteVersionNotFound:
            cross_tenant_preview_blocked = True

        business_b_preview = get_preview_version(
            conn,
            business_b,
        )

        business_b_remains_unmodified = (
            business_b_preview is None
        )

        print()
        print("=== 8. TENANT ISOLATION ===")
        print_check(
            "cross_tenant_lookup_blocked",
            cross_tenant_lookup_blocked,
        )
        print_check(
            "cross_tenant_preview_blocked",
            cross_tenant_preview_blocked,
        )
        print_check(
            "business_b_remains_unmodified",
            business_b_remains_unmodified,
        )

        # --------------------------------------------------------
        # 9. EXPLICIT PREVIEW SELECTION
        # --------------------------------------------------------

        preview_v2 = select_preview_version(
            conn,
            business_a,
            version_2["id"],
        )

        preview_selected = (
            bool(preview_v2)
            and preview_v2["id"] == version_2["id"]
        )

        project_after_preview = conn.execute(
            """
            SELECT *
            FROM website_projects
            WHERE id=?
            """,
            (project_a["id"],),
        ).fetchone()

        project_preview_status_correct = (
            project_after_preview["status"]
            == "PREVIEW_READY"
        )

        # --------------------------------------------------------
        # 10. NEW EDIT MUST NOT SILENTLY CHANGE PREVIEW
        # --------------------------------------------------------

        version_3 = update_presentation(
            conn,
            business_a,
            {
                "hero_headline": (
                    "A newer draft that has not been reviewed"
                ),
            },
            expected_current_version_id=version_2["id"],
        )

        version_3_created = (
            version_3["created_new_version"] is True
            and version_3["version_number"] == 3
        )

        current_points_to_v3 = (
            get_current_version(
                conn,
                business_a,
            )["id"]
            == version_3["id"]
        )

        preview_after_new_edit = get_preview_version(
            conn,
            business_a,
        )

        preview_still_points_to_v2 = (
            bool(preview_after_new_edit)
            and preview_after_new_edit["id"]
            == version_2["id"]
        )

        project_after_new_edit = conn.execute(
            """
            SELECT *
            FROM website_projects
            WHERE id=?
            """,
            (project_a["id"],),
        ).fetchone()

        new_edit_returns_project_to_draft = (
            project_after_new_edit["status"]
            == "DRAFT"
        )

        print()
        print("=== 9. PREVIEW ISOLATION ===")
        print_check(
            "preview_selected",
            preview_selected,
        )
        print_check(
            "project_preview_status_correct",
            project_preview_status_correct,
        )
        print_check(
            "version_3_created",
            version_3_created,
        )
        print_check(
            "current_points_to_v3",
            current_points_to_v3,
        )
        print_check(
            "preview_still_points_to_v2",
            preview_still_points_to_v2,
        )
        print_check(
            "new_edit_returns_project_to_draft",
            new_edit_returns_project_to_draft,
        )

        # --------------------------------------------------------
        # 11. VERSION HISTORY
        # --------------------------------------------------------

        history = list_versions(
            conn,
            business_a,
            limit=50,
        )

        history_has_three_versions = (
            len(history) == 3
        )

        history_order_correct = (
            len(history) == 3
            and history[0]["version_number"] == 3
            and history[1]["version_number"] == 2
            and history[2]["version_number"] == 1
        )

        all_history_owned_by_a = all(
            item["business_id"] == business_a
            for item in history
        )

        print()
        print("=== 10. VERSION HISTORY ===")
        print_check(
            "history_has_three_versions",
            history_has_three_versions,
        )
        print_check(
            "history_order_correct",
            history_order_correct,
        )
        print_check(
            "all_history_owned_by_a",
            all_history_owned_by_a,
        )

        # --------------------------------------------------------
        # 12. CLEAR PREVIEW
        # --------------------------------------------------------

        clear_preview_version(
            conn,
            business_a,
        )

        preview_after_clear = get_preview_version(
            conn,
            business_a,
        )

        preview_cleared = (
            preview_after_clear is None
        )

        project_after_clear = conn.execute(
            """
            SELECT *
            FROM website_projects
            WHERE id=?
            """,
            (project_a["id"],),
        ).fetchone()

        clear_returns_project_to_draft = (
            project_after_clear["status"]
            == "DRAFT"
            and project_after_clear[
                "preview_version_id"
            ]
            is None
        )

        print()
        print("=== 11. CLEAR PREVIEW ===")
        print_check(
            "preview_cleared",
            preview_cleared,
        )
        print_check(
            "clear_returns_project_to_draft",
            clear_returns_project_to_draft,
        )

        # --------------------------------------------------------
        # 13. READINESS FAIL-CLOSED
        # --------------------------------------------------------
        #
        # Our isolated business intentionally does not have a configured
        # public service catalog. Website readiness should therefore not
        # claim it is ready to publish.

        readiness_result = synchronize_readiness(
            conn,
            business_a,
        )

        readiness_not_ready = (
            readiness_result["readiness"]["ready"]
            is False
        )

        readiness_needs_attention = (
            readiness_result["project"]["status"]
            == "NEEDS_ATTENTION"
        )

        no_preview_selected = (
            readiness_result["preview_selected"]
            is False
        )

        print()
        print("=== 12. READINESS FAIL-CLOSED ===")
        print_check(
            "readiness_not_ready",
            readiness_not_ready,
        )
        print_check(
            "readiness_needs_attention",
            readiness_needs_attention,
        )
        print_check(
            "no_preview_selected",
            no_preview_selected,
        )

        # --------------------------------------------------------
        # 14. VERSION SUMMARY / LIVE PUBLISHING LOCK
        # --------------------------------------------------------

        summary = version_summary(
            conn,
            business_a,
        )

        summary_version_count_correct = (
            summary["version_count"] == 3
        )

        live_publishing_locked = (
            summary["live_publishing_enabled"]
            is False
        )

        print()
        print("=== 13. PUBLISHING SAFETY ===")
        print_check(
            "summary_version_count_correct",
            summary_version_count_correct,
        )
        print_check(
            "live_publishing_locked",
            live_publishing_locked,
        )

        # --------------------------------------------------------
        # 15. FINAL DATABASE HEALTH
        # --------------------------------------------------------

        foreign_key_violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        foreign_key_check_clean = (
            len(foreign_key_violations) == 0
        )

        final_integrity_value = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        final_integrity_ok = (
            final_integrity_value == "ok"
        )

        print()
        print("=== 14. FINAL DATABASE HEALTH ===")
        print_check(
            "foreign_key_check_clean",
            foreign_key_check_clean,
        )
        print_check(
            "final_integrity",
            final_integrity_value,
        )

        # --------------------------------------------------------
        # FINAL RESULT
        # --------------------------------------------------------

        checks = [
            website_projects_exists,
            website_versions_exists,
            foreign_keys_enabled,
            initial_integrity,
            business_a_exists,
            business_b_exists,
            project_a_created,
            project_b_created,
            same_project_on_repeat,
            exactly_one_project_for_a,
            nonexistent_business_blocked,
            initial_version_created,
            initial_version_number_correct,
            initial_version_is_draft,
            initial_version_owned_by_a,
            initial_presentation_loaded,
            version_2_created,
            version_2_number_correct,
            version_2_owned_by_a,
            version_2_content_correct,
            current_points_to_v2,
            old_version_superseded,
            unchanged_save_reused_version,
            duplicate_did_not_create_version,
            stale_edit_blocked,
            stale_edit_did_not_mutate_current,
            cross_tenant_lookup_blocked,
            cross_tenant_preview_blocked,
            business_b_remains_unmodified,
            preview_selected,
            project_preview_status_correct,
            version_3_created,
            current_points_to_v3,
            preview_still_points_to_v2,
            new_edit_returns_project_to_draft,
            history_has_three_versions,
            history_order_correct,
            all_history_owned_by_a,
            preview_cleared,
            clear_returns_project_to_draft,
            readiness_not_ready,
            readiness_needs_attention,
            no_preview_selected,
            summary_version_count_correct,
            live_publishing_locked,
            foreign_key_check_clean,
            final_integrity_ok,
        ]

        passed = all(checks)

        print()
        print("=" * 52)

        if passed:
            print("v12 WEBSITE STUDIO FOUNDATION: ALL PASS")
        else:
            failed_count = sum(
                1
                for check in checks
                if not check
            )

            print(
                "v12 WEBSITE STUDIO FOUNDATION: FAIL"
            )
            print(
                "Failed checks:",
                failed_count,
            )

            raise SystemExit(1)

        print("=" * 52)

    finally:
        conn.close()


if __name__ == "__main__":
    main()