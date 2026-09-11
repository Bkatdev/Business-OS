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

from services.website_renderer import (
    WebsiteRenderNotFound,
    build_current_draft_render_model,
    build_preview_render_model,
    render_safety_summary,
)

from services.website_studio import (
    get_or_create_project,
)

from services.website_versions import (
    get_current_version,
    select_preview_version,
    update_presentation,
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


def print_check(label, value):
    print(f"{label}: {value}")


def create_business(
    conn,
    name,
    phone,
    email,
    website="",
):
    """
    Create a canonical business using the real Business OS businesses
    schema rather than inventing a Website Studio-owned business record.
    """
    timestamp = db.now_iso()

    cursor = conn.execute(
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
            website,
            phone,
            email,
            "Not Contacted",
            "Isolated v12 renderer test business.",
            timestamp,
        ),
    )

    return cursor.lastrowid


def configure_profile(
    conn,
    business_id,
    service_area,
    business_hours,
    industry="Local Services",
):
    """
    Configure canonical client-profile data.

    Website Studio must read this information rather than storing a
    duplicate copy.
    """
    timestamp = db.now_iso()

    existing = conn.execute(
        """
        SELECT business_id
        FROM client_profiles
        WHERE business_id=?
        """,
        (business_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE client_profiles
            SET service_area=?,
                business_hours=?,
                industry=?,
                updated_at=?
            WHERE business_id=?
            """,
            (
                service_area,
                business_hours,
                industry,
                timestamp,
                business_id,
            ),
        )

    else:
        conn.execute(
            """
            INSERT INTO client_profiles (
                business_id,
                service_area,
                business_hours,
                industry,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                business_id,
                service_area,
                business_hours,
                industry,
                timestamp,
            ),
        )


def create_service(
    conn,
    business_id,
    name,
    description,
    sort_order=0,
):
    """
    Create a canonical active/public service.
    """
    timestamp = db.now_iso()

    cursor = conn.execute(
        """
        INSERT INTO business_services (
            business_id,
            name,
            description,
            active,
            public,
            bookable,
            requires_estimate,
            sort_order,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 1, 1, 0, 1, ?, ?, ?)
        """,
        (
            business_id,
            name,
            description,
            sort_order,
            timestamp,
            timestamp,
        ),
    )

    return cursor.lastrowid


def create_intake_schema(
    conn,
    business_id,
):
    """
    Create the canonical active intake schema used by the website.
    """
    timestamp = db.now_iso()

    cursor = conn.execute(
        """
        INSERT INTO intake_schemas (
            business_id,
            name,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'Active', ?, ?)
        """,
        (
            business_id,
            "Website Request Intake",
            timestamp,
            timestamp,
        ),
    )

    return cursor.lastrowid


def create_intake_question(
    conn,
    schema_id,
    service_id,
    question_key,
    label,
    question_type,
    required,
    sort_order,
    options_json="[]",
):
    """
    Create one canonical intake question.
    """
    timestamp = db.now_iso()

    cursor = conn.execute(
        """
        INSERT INTO intake_questions (
            schema_id,
            service_id,
            question_key,
            label,
            question_type,
            required,
            sort_order,
            options_json,
            active,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            schema_id,
            service_id,
            question_key,
            label,
            question_type,
            required,
            sort_order,
            options_json,
            timestamp,
            timestamp,
        ),
    )

    return cursor.lastrowid


def main():
    # ------------------------------------------------------------
    # ISOLATED DATABASE
    # ------------------------------------------------------------

    test_db = (
        Path(tempfile.gettempdir())
        / "business_os_v12_renderer_test.db"
    )

    remove_test_database(test_db)

    db.DB_PATH = test_db

    print("Initializing isolated v12 renderer database...")
    print("DB:", test_db)

    db.init_db()

    conn = db.connect()

    try:
        checks = []

        # --------------------------------------------------------
        # 1. CREATE TWO CANONICAL TENANTS
        # --------------------------------------------------------

        business_a = create_business(
            conn,
            "Safe & Reliable <script>alert(1)</script>",
            "(555) 111-2222",
            "hello@example.com",
            "javascript:alert(1)",
        )

        business_b = create_business(
            conn,
            "Second Tenant",
            "(555) 333-4444",
            "second@example.com",
            "https://example.com",
        )

        configure_profile(
            conn,
            business_a,
            "Test City and surrounding communities",
            "Monday-Friday, 8 AM-5 PM",
        )

        configure_profile(
            conn,
            business_b,
            "Another Test Area",
            "Monday-Friday, 9 AM-4 PM",
        )

        service_a = create_service(
            conn,
            business_a,
            "General Service <b>unsafe</b>",
            (
                "Canonical service description "
                "<script>alert('service')</script>"
            ),
            sort_order=1,
        )

        create_service(
            conn,
            business_a,
            "Estimate Request",
            "Request an estimate for configured services.",
            sort_order=2,
        )

        service_b = create_service(
            conn,
            business_b,
            "Tenant B Service",
            "This must never appear for Tenant A.",
            sort_order=1,
        )

        schema_a = create_intake_schema(
            conn,
            business_a,
        )

        schema_b = create_intake_schema(
            conn,
            business_b,
        )

        create_intake_question(
            conn,
            schema_a,
            service_a,
            "issue_description",
            "What do you need help with?",
            "textarea",
            1,
            1,
        )

        create_intake_question(
            conn,
            schema_a,
            service_a,
            "urgency",
            "How soon do you need help?",
            "select",
            0,
            2,
            (
                '["Today", "This week", '
                '"<script>alert(1)</script>"]'
            ),
        )

        create_intake_question(
            conn,
            schema_b,
            service_b,
            "tenant_b_secret",
            "Tenant B only question",
            "text",
            1,
            1,
        )

        conn.commit()

        business_a_created = bool(business_a)
        business_b_created = bool(business_b)

        print()
        print("=== 1. CANONICAL TEST DATA ===")
        print_check(
            "business_a_created",
            business_a_created,
        )
        print_check(
            "business_b_created",
            business_b_created,
        )

        checks.extend(
            [
                business_a_created,
                business_b_created,
            ]
        )

        # --------------------------------------------------------
        # 2. CREATE WEBSITE STUDIO PROJECTS
        # --------------------------------------------------------

        project_a = get_or_create_project(
            conn,
            business_a,
        )

        project_b = get_or_create_project(
            conn,
            business_b,
        )

        projects_created = (
            bool(project_a)
            and bool(project_b)
        )

        print()
        print("=== 2. WEBSITE PROJECTS ===")
        print_check(
            "projects_created",
            projects_created,
        )

        checks.append(
            projects_created
        )

        # --------------------------------------------------------
        # 3. CONFIGURE PRESENTATION
        # --------------------------------------------------------

        initial_a = get_current_version(
            conn,
            business_a,
        )

        edited_a = update_presentation(
            conn,
            business_a,
            {
                "theme_key": "modern",
                "hero_headline": (
                    "Professional help "
                    "<img src=x onerror=alert(1)>"
                ),
                "hero_supporting_text": (
                    "Tell us what you need."
                ),
                "primary_cta_label": (
                    "Request <script>Service</script>"
                ),
                "about_copy": (
                    "Owner-controlled about text "
                    "<script>alert('about')</script>"
                ),
                "contact_intro": (
                    "Contact our team."
                ),
                "seo_title": (
                    "Safe Test Business"
                ),
                "seo_description": (
                    "Renderer safety test."
                ),
            },
            expected_current_version_id=(
                initial_a["id"]
            ),
        )

        presentation_version_created = (
            edited_a["created_new_version"]
            is True
        )

        print()
        print("=== 3. PRESENTATION VERSION ===")
        print_check(
            "presentation_version_created",
            presentation_version_created,
        )

        checks.append(
            presentation_version_created
        )

        # --------------------------------------------------------
        # 4. CURRENT DRAFT RENDER
        # --------------------------------------------------------

        model = build_current_draft_render_model(
            conn,
            business_a,
        )

        render_model_created = (
            model["business_id"]
            == business_a
        )

        correct_version_rendered = (
            model["version"]["id"]
            == edited_a["id"]
        )

        print()
        print("=== 4. CURRENT DRAFT RENDER ===")
        print_check(
            "render_model_created",
            render_model_created,
        )
        print_check(
            "correct_version_rendered",
            correct_version_rendered,
        )

        checks.extend(
            [
                render_model_created,
                correct_version_rendered,
            ]
        )

        # --------------------------------------------------------
        # 5. CANONICAL BUSINESS TRUTH
        # --------------------------------------------------------

        canonical_name_preserved = (
            model["business"]["name"]
            == (
                "Safe & Reliable "
                "<script>alert(1)</script>"
            )
        )

        business_name_html_escaped = (
            "<script>"
            not in model["business"]["name_html"]
            and "&lt;script&gt;"
            in model["business"]["name_html"]
        )

        unsafe_business_url_blocked = (
            model["business"]["website"]
            == ""
        )

        canonical_phone_reused = (
            model["contact"]["phone"]
            == "(555) 111-2222"
        )

        canonical_email_reused = (
            model["contact"]["email"]
            == "hello@example.com"
        )

        print()
        print("=== 5. CANONICAL BUSINESS TRUTH ===")
        print_check(
            "canonical_name_preserved",
            canonical_name_preserved,
        )
        print_check(
            "business_name_html_escaped",
            business_name_html_escaped,
        )
        print_check(
            "unsafe_business_url_blocked",
            unsafe_business_url_blocked,
        )
        print_check(
            "canonical_phone_reused",
            canonical_phone_reused,
        )
        print_check(
            "canonical_email_reused",
            canonical_email_reused,
        )

        checks.extend(
            [
                canonical_name_preserved,
                business_name_html_escaped,
                unsafe_business_url_blocked,
                canonical_phone_reused,
                canonical_email_reused,
            ]
        )

        # --------------------------------------------------------
        # 6. PRESENTATION XSS SAFETY
        # --------------------------------------------------------

        raw_headline_preserved_as_text = (
            "<img src=x onerror=alert(1)>"
            in model["hero"]["headline"]
        )

        headline_html_escaped = (
            "<img"
            not in model[
                "hero"
            ]["headline_html"]
            and "&lt;img"
            in model[
                "hero"
            ]["headline_html"]
        )

        cta_html_escaped = (
            "<script>"
            not in model[
                "hero"
            ]["primary_cta_label_html"]
            and "&lt;script&gt;"
            in model[
                "hero"
            ]["primary_cta_label_html"]
        )

        about_html_escaped = (
            "<script>"
            not in model[
                "presentation"
            ]["about_copy_html"]
            and "&lt;script&gt;"
            in model[
                "presentation"
            ]["about_copy_html"]
        )

        print()
        print("=== 6. PRESENTATION XSS SAFETY ===")
        print_check(
            "raw_headline_preserved_as_text",
            raw_headline_preserved_as_text,
        )
        print_check(
            "headline_html_escaped",
            headline_html_escaped,
        )
        print_check(
            "cta_html_escaped",
            cta_html_escaped,
        )
        print_check(
            "about_html_escaped",
            about_html_escaped,
        )

        checks.extend(
            [
                raw_headline_preserved_as_text,
                headline_html_escaped,
                cta_html_escaped,
                about_html_escaped,
            ]
        )

        # --------------------------------------------------------
        # 7. CANONICAL SERVICES
        # --------------------------------------------------------

        service_names = [
            service["name"]
            for service in model["services"]
        ]

        tenant_a_services_present = (
            "General Service <b>unsafe</b>"
            in service_names
            and "Estimate Request"
            in service_names
        )

        tenant_b_service_absent = (
            "Tenant B Service"
            not in service_names
        )

        service_html_escaped = any(
            (
                "&lt;b&gt;unsafe&lt;/b&gt;"
                in service["name_html"]
            )
            for service in model["services"]
        )

        service_script_escaped = any(
            (
                "&lt;script&gt;"
                in service["description_html"]
            )
            for service in model["services"]
        )

        print()
        print("=== 7. CANONICAL SERVICES ===")
        print_check(
            "tenant_a_services_present",
            tenant_a_services_present,
        )
        print_check(
            "tenant_b_service_absent",
            tenant_b_service_absent,
        )
        print_check(
            "service_html_escaped",
            service_html_escaped,
        )
        print_check(
            "service_script_escaped",
            service_script_escaped,
        )

        checks.extend(
            [
                tenant_a_services_present,
                tenant_b_service_absent,
                service_html_escaped,
                service_script_escaped,
            ]
        )

        # --------------------------------------------------------
        # 8. CANONICAL INTAKE
        # --------------------------------------------------------

        question_keys = [
            question["question_key"]
            for question in model[
                "intake"
            ]["questions"]
        ]

        tenant_a_questions_present = (
            "issue_description"
            in question_keys
            and "urgency"
            in question_keys
        )

        tenant_b_question_absent = (
            "tenant_b_secret"
            not in question_keys
        )

        urgency_question = next(
            (
                question
                for question in model[
                    "intake"
                ]["questions"]
                if question["question_key"]
                == "urgency"
            ),
            None,
        )

        intake_options_loaded = (
            bool(urgency_question)
            and urgency_question["options"][
                :2
            ]
            == [
                "Today",
                "This week",
            ]
        )

        malicious_option_escaped = (
            bool(urgency_question)
            and len(
                urgency_question[
                    "options_html"
                ]
            )
            == 3
            and "<script>"
            not in urgency_question[
                "options_html"
            ][2]
            and "&lt;script&gt;"
            in urgency_question[
                "options_html"
            ][2]
        )

        questions_grouped_by_service = (
            str(service_a)
            in model[
                "intake"
            ]["questions_by_service"]
        )

        print()
        print("=== 8. CANONICAL INTAKE ===")
        print_check(
            "tenant_a_questions_present",
            tenant_a_questions_present,
        )
        print_check(
            "tenant_b_question_absent",
            tenant_b_question_absent,
        )
        print_check(
            "intake_options_loaded",
            intake_options_loaded,
        )
        print_check(
            "malicious_option_escaped",
            malicious_option_escaped,
        )
        print_check(
            "questions_grouped_by_service",
            questions_grouped_by_service,
        )

        checks.extend(
            [
                tenant_a_questions_present,
                tenant_b_question_absent,
                intake_options_loaded,
                malicious_option_escaped,
                questions_grouped_by_service,
            ]
        )

        # --------------------------------------------------------
        # 9. PREVIEW MUST FAIL CLOSED
        # --------------------------------------------------------

        preview_blocked_without_selection = False

        try:
            build_preview_render_model(
                conn,
                business_a,
            )

        except WebsiteRenderNotFound:
            preview_blocked_without_selection = True

        print()
        print("=== 9. PREVIEW FAIL-CLOSED ===")
        print_check(
            "preview_blocked_without_selection",
            preview_blocked_without_selection,
        )

        checks.append(
            preview_blocked_without_selection
        )

        # --------------------------------------------------------
        # 10. EXPLICIT PREVIEW
        # --------------------------------------------------------

        select_preview_version(
            conn,
            business_a,
            edited_a["id"],
        )

        preview_model = (
            build_preview_render_model(
                conn,
                business_a,
            )
        )

        explicit_preview_correct = (
            preview_model[
                "version"
            ]["id"]
            == edited_a["id"]
        )

        preview_owned_by_correct_tenant = (
            preview_model["business_id"]
            == business_a
        )

        print()
        print("=== 10. EXPLICIT PREVIEW ===")
        print_check(
            "explicit_preview_correct",
            explicit_preview_correct,
        )
        print_check(
            "preview_owned_by_correct_tenant",
            preview_owned_by_correct_tenant,
        )

        checks.extend(
            [
                explicit_preview_correct,
                preview_owned_by_correct_tenant,
            ]
        )

        # --------------------------------------------------------
        # 11. PREVIEW IMMUTABILITY
        # --------------------------------------------------------

        newer_draft = update_presentation(
            conn,
            business_a,
            {
                "hero_headline": (
                    "Unreviewed newer draft"
                ),
            },
            expected_current_version_id=(
                edited_a["id"]
            ),
        )

        current_model = (
            build_current_draft_render_model(
                conn,
                business_a,
            )
        )

        preserved_preview_model = (
            build_preview_render_model(
                conn,
                business_a,
            )
        )

        current_is_newer_draft = (
            current_model[
                "version"
            ]["id"]
            == newer_draft["id"]
        )

        preview_remains_reviewed_version = (
            preserved_preview_model[
                "version"
            ]["id"]
            == edited_a["id"]
        )

        print()
        print("=== 11. PREVIEW IMMUTABILITY ===")
        print_check(
            "current_is_newer_draft",
            current_is_newer_draft,
        )
        print_check(
            "preview_remains_reviewed_version",
            preview_remains_reviewed_version,
        )

        checks.extend(
            [
                current_is_newer_draft,
                preview_remains_reviewed_version,
            ]
        )

        # --------------------------------------------------------
        # 12. CUSTOMER READINESS
        # --------------------------------------------------------

        customer_ready = (
            current_model["customer_ready"]
            is True
        )

        no_blocking_warnings = (
            len(
                current_model[
                    "blocking_warnings"
                ]
            )
            == 0
        )

        print()
        print("=== 12. CUSTOMER READINESS ===")
        print_check(
            "customer_ready",
            customer_ready,
        )
        print_check(
            "no_blocking_warnings",
            no_blocking_warnings,
        )

        checks.extend(
            [
                customer_ready,
                no_blocking_warnings,
            ]
        )

        # --------------------------------------------------------
        # 13. PUBLISHING MUST REMAIN LOCKED
        # --------------------------------------------------------

        renderer_says_not_published = (
            current_model[
                "publishing"
            ]["published"]
            is False
        )

        renderer_live_disabled = (
            current_model[
                "publishing"
            ]["live_enabled"]
            is False
        )

        renderer_has_no_provider = (
            current_model[
                "publishing"
            ]["provider"]
            is None
        )

        safety_summary = render_safety_summary(
            conn,
            business_a,
        )

        summary_live_disabled = (
            safety_summary[
                "live_publishing_enabled"
            ]
            is False
        )

        print()
        print("=== 13. PUBLISHING SAFETY ===")
        print_check(
            "renderer_says_not_published",
            renderer_says_not_published,
        )
        print_check(
            "renderer_live_disabled",
            renderer_live_disabled,
        )
        print_check(
            "renderer_has_no_provider",
            renderer_has_no_provider,
        )
        print_check(
            "summary_live_disabled",
            summary_live_disabled,
        )

        checks.extend(
            [
                renderer_says_not_published,
                renderer_live_disabled,
                renderer_has_no_provider,
                summary_live_disabled,
            ]
        )

        # --------------------------------------------------------
        # 14. DATABASE HEALTH
        # --------------------------------------------------------

        foreign_key_violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        foreign_key_check_clean = (
            len(foreign_key_violations)
            == 0
        )

        integrity_value = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        integrity_ok = (
            integrity_value == "ok"
        )

        print()
        print("=== 14. DATABASE HEALTH ===")
        print_check(
            "foreign_key_check_clean",
            foreign_key_check_clean,
        )
        print_check(
            "integrity",
            integrity_value,
        )

        checks.extend(
            [
                foreign_key_check_clean,
                integrity_ok,
            ]
        )

        # --------------------------------------------------------
        # FINAL RESULT
        # --------------------------------------------------------

        passed = all(checks)

        print()
        print("=" * 56)

        if passed:
            print(
                "v12 WEBSITE RENDERER: ALL PASS"
            )

        else:
            failed_count = sum(
                1
                for check in checks
                if not check
            )

            print(
                "v12 WEBSITE RENDERER: FAIL"
            )
            print(
                "Failed checks:",
                failed_count,
            )

            raise SystemExit(1)

        print("=" * 56)

    finally:
        conn.close()


if __name__ == "__main__":
    main()