from pathlib import Path
import shutil
import sqlite3
import tempfile
import py_compile

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parent

APP_FILE = ROOT / "app.py"
TRIAGE_FILE = ROOT / "services" / "lead_triage.py"
TEMPLATE_FILE = ROOT / "templates" / "lead_detail.html"
DASHBOARD_FILE = ROOT / "templates" / "dashboard.html"
CSS_FILE = ROOT / "static" / "styles.css"
DB_FILE = ROOT / "business_os.db"


def find_db_file():
    candidates = [
        ROOT / "db.py",
        ROOT / "services" / "db.py",
        ROOT / "database" / "db.py",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(ROOT.rglob("db.py"))

    for match in matches:
        text = match.read_text(
            encoding="utf-8"
        )

        if "CREATE TABLE IF NOT EXISTS leads" in text:
            return match

    return None


DB_CODE_FILE = find_db_file()


print()
print("======================================")
print(" BUSINESS OS LEAD INTELLIGENCE")
print("======================================")
print()


required = [
    APP_FILE,
    TRIAGE_FILE,
    TEMPLATE_FILE,
    DASHBOARD_FILE,
    CSS_FILE,
    DB_FILE,
]

if DB_CODE_FILE:
    required.append(DB_CODE_FILE)


for file in required:
    if not file.exists():
        raise SystemExit(
            f"STOPPED: Missing required file:\n{file}"
        )


if DB_CODE_FILE is None:
    raise SystemExit(
        "STOPPED: Could not locate db.py."
    )


backup_dir = Path(
    tempfile.mkdtemp(
        prefix="business_os_intelligence_"
    )
)


for file in required:
    backup = (
        backup_dir
        / file.relative_to(ROOT)
    )

    backup.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        file,
        backup,
    )


print("Safety backup created:")
print(backup_dir)
print()

print("Database code found:")
print(DB_CODE_FILE.relative_to(ROOT))
print()


NEW_TRIAGE = '''def triage_lead(
    priority="Normal",
    safety_flag="",
    preferred_time="",
    appointment_status="Not Scheduled",
    lead_status="New",
):
    priority = (
        priority or "Normal"
    ).strip()

    safety_flag = (
        safety_flag or ""
    ).strip()

    preferred_time = (
        preferred_time or ""
    ).strip()

    appointment_status = (
        appointment_status
        or "Not Scheduled"
    ).strip()

    lead_status = (
        lead_status or "New"
    ).strip()


    # Closed leads should never receive
    # active follow-up recommendations.

    if lead_status == "Won":
        return {
            "level": "Won",
            "next_action": "No follow-up required",
            "reason": (
                "This opportunity has been "
                "marked as won."
            ),
        }


    if lead_status == "Lost":
        return {
            "level": "Closed",
            "next_action": "No active follow-up",
            "reason": (
                "This opportunity has been "
                "marked as lost."
            ),
        }


    # Safety always takes precedence
    # for active opportunities.

    if priority == "Urgent" or safety_flag:
        return {
            "level": "Urgent",
            "next_action": "Escalate to owner",
            "reason": (
                safety_flag
                or "Lead was marked urgent."
            ),
        }


    if (
        lead_status == "Estimate Scheduled"
        or appointment_status == "Scheduled"
    ):
        return {
            "level": "Ready",
            "next_action": "Review scheduled estimate",
            "reason": (
                "Customer has an estimate "
                "scheduled."
            ),
        }


    if lead_status == "Contacted":
        return {
            "level": "Follow Up",
            "next_action": "Continue follow-up",
            "reason": (
                "Customer has been contacted "
                "but the opportunity is still open."
            ),
        }


    if preferred_time:
        return {
            "level": "Follow Up",
            "next_action": "Confirm estimate time",
            "reason": (
                f"Customer prefers "
                f"{preferred_time}."
            ),
        }


    return {
        "level": "Follow Up",
        "next_action": "Contact lead",
        "reason": (
            "Lead needs a response and no "
            "appointment has been scheduled."
        ),
    }
'''


ACTIVITY_SCHEMA = '''
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL DEFAULT 'Status',
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id
        ON lead_activities(lead_id)
        """
    )

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_created_at
        ON lead_activities(created_at)
        """
    )

    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_created_activity
        AFTER INSERT ON leads
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Created',
                'Lead captured',
                'Lead entered Business OS.',
                NEW.created_at
            );
        END
        """
    )

    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_status_activity
        AFTER UPDATE OF status ON leads
        WHEN OLD.status != NEW.status
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Status',
                'Status changed to ' || NEW.status,
                'Previous status: ' || OLD.status,
                datetime('now', 'localtime')
            );
        END
        """
    )

'''


CSS_MARKER = """
/* ==========================================
   BUSINESS OS LEAD ACTIVITY
   ========================================== */
"""


CSS_ADDITION = r'''

/* ==========================================
   BUSINESS OS LEAD ACTIVITY
   ========================================== */

.lead-activity-card {
    margin-top: 18px;
}

.activity-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;

    margin-bottom: 18px;
}

.activity-header h3 {
    margin: 0;

    color: var(--ink);

    font-size: 14px;
}

.activity-header span {
    color: var(--muted);

    font-size: 9px;
}

.activity-timeline {
    position: relative;

    display: flex;
    flex-direction: column;
    gap: 0;
}

.activity-item {
    position: relative;

    display: grid;
    grid-template-columns: 22px minmax(0, 1fr);
    gap: 11px;

    padding-bottom: 18px;
}

.activity-item:last-child {
    padding-bottom: 0;
}

.activity-marker {
    position: relative;

    display: flex;
    justify-content: center;
}

.activity-marker::after {
    content: "";

    position: absolute;
    top: 12px;
    bottom: -18px;

    width: 1px;

    background: var(--line);
}

.activity-item:last-child
.activity-marker::after {
    display: none;
}

.activity-dot {
    position: relative;
    z-index: 1;

    width: 9px;
    height: 9px;

    margin-top: 3px;

    border: 2px solid white;
    border-radius: 50%;

    background: var(--accent);

    box-shadow:
        0 0 0 2px var(--accent-soft);
}

.activity-content {
    min-width: 0;
}

.activity-content strong {
    display: block;

    color: var(--ink-soft);

    font-size: 10px;
}

.activity-content p {
    margin: 4px 0 0;

    color: var(--muted);

    font-size: 9px;
    line-height: 1.5;
}

.activity-time {
    display: block;

    margin-top: 5px;

    color: #98a39d;

    font-size: 8px;
}

.activity-empty {
    padding: 18px;

    border: 1px dashed var(--line);
    border-radius: 12px;

    color: var(--muted);

    font-size: 9px;
    text-align: center;
}
'''


TIMELINE_TEMPLATE = r'''

<div class="card lead-activity-card">

    <div class="activity-header">

        <div>
            <h3>Lead Activity</h3>
            <span>
                History of this opportunity
            </span>
        </div>

        {% if activities %}
        <span>
            {{ activities|length }}
            event{% if activities|length != 1 %}s{% endif %}
        </span>
        {% endif %}

    </div>


    {% if activities %}

    <div class="activity-timeline">

        {% for activity in activities %}

        <div class="activity-item">

            <div class="activity-marker">
                <span class="activity-dot"></span>
            </div>

            <div class="activity-content">

                <strong>
                    {{ activity["title"] }}
                </strong>

                {% if activity["details"] %}
                <p>
                    {{ activity["details"] }}
                </p>
                {% endif %}

                <span class="activity-time">
                    {{ activity["created_at"] }}
                </span>

            </div>

        </div>

        {% endfor %}

    </div>

    {% else %}

    <div class="activity-empty">
        No activity recorded yet.
    </div>

    {% endif %}

</div>
'''


def restore():
    print()
    print("Restoring original files...")

    for file in required:
        backup = (
            backup_dir
            / file.relative_to(ROOT)
        )

        if backup.exists():
            shutil.copy2(
                backup,
                file,
            )


try:

    # ----------------------------------
    # 1. Smarter triage service
    # ----------------------------------

    TRIAGE_FILE.write_text(
        NEW_TRIAGE,
        encoding="utf-8",
    )


    # ----------------------------------
    # 2. Add persistent activity schema
    #    to db.py for future startups
    # ----------------------------------

    db_code = DB_CODE_FILE.read_text(
        encoding="utf-8"
    )


    schema_marker = (
        "CREATE TABLE IF NOT EXISTS "
        "lead_activities"
    )


    if schema_marker not in db_code:

        insert_marker = (
            '    existing = {\n'
        )

        if insert_marker not in db_code:
            raise RuntimeError(
                "Could not find safe db.py "
                "schema insertion point."
            )

        db_code = db_code.replace(
            insert_marker,
            ACTIVITY_SCHEMA
            + insert_marker,
            1,
        )

        DB_CODE_FILE.write_text(
            db_code,
            encoding="utf-8",
        )


    # ----------------------------------
    # 3. Upgrade the EXISTING database
    # ----------------------------------

    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row


    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL DEFAULT 'Status',
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )


    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id
        ON lead_activities(lead_id)
        """
    )


    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_activities_created_at
        ON lead_activities(created_at)
        """
    )


    # Backfill one creation event for every
    # existing lead that has no activity yet.

    con.execute(
        """
        INSERT INTO lead_activities (
            lead_id,
            activity_type,
            title,
            details,
            created_at
        )
        SELECT
            leads.id,
            'Created',
            'Lead captured',
            'Existing lead added to activity history.',
            leads.created_at
        FROM leads
        WHERE NOT EXISTS (
            SELECT 1
            FROM lead_activities
            WHERE lead_activities.lead_id = leads.id
        )
        """
    )


    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_created_activity
        AFTER INSERT ON leads
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Created',
                'Lead captured',
                'Lead entered Business OS.',
                NEW.created_at
            );
        END
        """
    )


    con.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_lead_status_activity
        AFTER UPDATE OF status ON leads
        WHEN OLD.status != NEW.status
        BEGIN
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                title,
                details,
                created_at
            )
            VALUES (
                NEW.id,
                'Status',
                'Status changed to ' || NEW.status,
                'Previous status: ' || OLD.status,
                datetime('now', 'localtime')
            );
        END
        """
    )


    con.commit()
    con.close()


    # ----------------------------------
    # 4. Upgrade lead_detail route
    # ----------------------------------

    app = APP_FILE.read_text(
        encoding="utf-8"
    )


    old_call_close = '''    call = conn.execute(
        """
        SELECT *
        FROM calls
        WHERE lead_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (lead_id,),
    ).fetchone()

    conn.close()
'''


    new_call_close = '''    call = conn.execute(
        """
        SELECT *
        FROM calls
        WHERE lead_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (lead_id,),
    ).fetchone()

    activities = conn.execute(
        """
        SELECT *
        FROM lead_activities
        WHERE lead_id = ?
        ORDER BY id DESC
        """,
        (lead_id,),
    ).fetchall()

    conn.close()
'''


    if (
        "FROM lead_activities"
        not in app
    ):

        if old_call_close not in app:
            raise RuntimeError(
                "Could not find lead_detail "
                "database block in app.py."
            )

        app = app.replace(
            old_call_close,
            new_call_close,
            1,
        )


    old_triage = '''    triage = triage_lead(
        priority=lead["priority"],
        safety_flag=lead["safety_flag"],
        preferred_time=lead["preferred_time"],
        appointment_status=lead["appointment_status"],
    )
'''


    new_triage = '''    triage = triage_lead(
        priority=lead["priority"],
        safety_flag=lead["safety_flag"],
        preferred_time=lead["preferred_time"],
        appointment_status=lead["appointment_status"],
        lead_status=lead["status"],
    )
'''


    if "lead_status=lead[\"status\"]" not in app:

        if old_triage not in app:
            raise RuntimeError(
                "Could not find triage call "
                "in app.py."
            )

        app = app.replace(
            old_triage,
            new_triage,
            1,
        )


    old_render = '''        lead=lead,
        call=call,
        triage=triage,
    )
'''


    new_render = '''        lead=lead,
        call=call,
        triage=triage,
        activities=activities,
    )
'''


    if "activities=activities" not in app:

        if old_render not in app:
            raise RuntimeError(
                "Could not find lead_detail "
                "render block in app.py."
            )

        app = app.replace(
            old_render,
            new_render,
            1,
        )


    # ----------------------------------
    # 5. Fix lifecycle consistency
    # ----------------------------------

    old_appointment_logic = '''    appointment_status = None

    if status == "Estimate Scheduled":
        appointment_status = "Scheduled"

    if appointment_status:
        conn.execute(
            """
            UPDATE leads
            SET status = ?,
                appointment_status = ?
            WHERE id = ?
            """,
            (
                status,
                appointment_status,
                lead_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE leads
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                lead_id,
            ),
        )
'''


    new_appointment_logic = '''    if status == "Estimate Scheduled":
        appointment_status = "Scheduled"
    elif status in ("New", "Lost"):
        appointment_status = "Not Scheduled"
    else:
        appointment_status = None

    if appointment_status is not None:
        conn.execute(
            """
            UPDATE leads
            SET status = ?,
                appointment_status = ?
            WHERE id = ?
            """,
            (
                status,
                appointment_status,
                lead_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE leads
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                lead_id,
            ),
        )
'''


    if old_appointment_logic in app:
        app = app.replace(
            old_appointment_logic,
            new_appointment_logic,
            1,
        )


    # ----------------------------------
    # 6. Fix scheduled dashboard count
    # ----------------------------------

    old_scheduled_query = '''        WHERE status = 'Estimate Scheduled'
           OR appointment_status = 'Scheduled'
'''


    new_scheduled_query = '''        WHERE status = 'Estimate Scheduled'
'''


    if old_scheduled_query in app:
        app = app.replace(
            old_scheduled_query,
            new_scheduled_query,
            1,
        )


    APP_FILE.write_text(
        app,
        encoding="utf-8",
    )


    # ----------------------------------
    # 7. Add activity timeline to UI
    # ----------------------------------

    template = TEMPLATE_FILE.read_text(
        encoding="utf-8"
    )


    if "lead-activity-card" not in template:

        end_marker = "{% endblock %}"

        if end_marker not in template:
            raise RuntimeError(
                "Could not find end of "
                "lead_detail.html."
            )

        template = template.rsplit(
            end_marker,
            1,
        )

        template = (
            template[0]
            + TIMELINE_TEMPLATE
            + "\n"
            + end_marker
            + template[1]
        )

        TEMPLATE_FILE.write_text(
            template,
            encoding="utf-8",
        )


    # ----------------------------------
    # 8. Add activity styling
    # ----------------------------------

    css = CSS_FILE.read_text(
        encoding="utf-8"
    )


    if CSS_MARKER not in css:
        css = (
            css.rstrip()
            + "\n"
            + CSS_ADDITION
            + "\n"
        )

        CSS_FILE.write_text(
            css,
            encoding="utf-8",
        )


    # ----------------------------------
    # 9. Validate Python
    # ----------------------------------

    py_compile.compile(
        str(APP_FILE),
        doraise=True,
    )

    py_compile.compile(
        str(TRIAGE_FILE),
        doraise=True,
    )

    py_compile.compile(
        str(DB_CODE_FILE),
        doraise=True,
    )


    # ----------------------------------
    # 10. Validate templates
    # ----------------------------------

    env = Environment(
        loader=FileSystemLoader(
            str(ROOT / "templates")
        )
    )

    env.get_template(
        "lead_detail.html"
    )

    env.get_template(
        "dashboard.html"
    )


    # ----------------------------------
    # 11. Validate database migration
    # ----------------------------------

    con = sqlite3.connect(DB_FILE)

    activity_count = con.execute(
        """
        SELECT COUNT(*)
        FROM lead_activities
        """
    ).fetchone()[0]

    lead_count = con.execute(
        """
        SELECT COUNT(*)
        FROM leads
        """
    ).fetchone()[0]

    con.close()


except Exception as exc:

    restore()

    raise SystemExit(
        "\nUPGRADE FAILED.\n"
        "Original files restored.\n\n"
        f"Error: {exc}"
    )


print()
print("======================================")
print(" LEAD INTELLIGENCE UPGRADE COMPLETE")
print("======================================")
print()

print("Updated:")
print("  app.py")
print(f"  {DB_CODE_FILE.relative_to(ROOT)}")
print("  services/lead_triage.py")
print("  templates/lead_detail.html")
print("  static/styles.css")
print("  business_os.db")
print()

print("Python validation: PASS")
print("Template validation: PASS")
print("Database migration: PASS")
print()

print(f"Existing leads: {lead_count}")
print(f"Activity records: {activity_count}")
print()

print("Next browser test:")
print("  1. Open a lead")
print("  2. Confirm Lead Activity appears")
print("  3. Mark lead Contacted")
print("  4. Confirm timeline updates")
print("  5. Mark Won")
print("  6. Confirm triage says no follow-up")
print("  7. Reopen")
print("  8. Confirm appointment resets")
print()
print("Do not delete this script yet.")