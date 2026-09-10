from pathlib import Path
import py_compile
import re
import shutil
import tempfile


ROOT = Path(__file__).resolve().parent

APP_FILE = ROOT / "app.py"
BASE_FILE = ROOT / "templates" / "base.html"
DASHBOARD_FILE = ROOT / "templates" / "dashboard.html"
STYLES_FILE = ROOT / "static" / "styles.css"


files = [
    APP_FILE,
    BASE_FILE,
    DASHBOARD_FILE,
    STYLES_FILE,
]


print()
print("======================================")
print(" BUSINESS OS PLATFORM UPGRADE")
print("======================================")
print()


for file in files:
    if not file.exists():
        raise SystemExit(
            f"STOPPED: required file not found: {file}"
        )


app_text = APP_FILE.read_text(
    encoding="utf-8"
)


dashboard_pattern = re.compile(
    r'@app\.route\("/"\)\s*'
    r'def dashboard\(\):.*?'
    r'(?=\n@app\.route\("/prospects"\))',
    re.DOTALL,
)


matches = dashboard_pattern.findall(
    app_text
)


if len(matches) != 1:
    raise SystemExit(
        "STOPPED: Could not safely identify the "
        "dashboard function in app.py.\n"
        "No files were changed."
    )


backup_dir = Path(
    tempfile.mkdtemp(
        prefix="business_os_upgrade_"
    )
)


for file in files:
    destination = (
        backup_dir
        / file.relative_to(ROOT)
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        file,
        destination,
    )


print(
    f"Safety backup created at:\n{backup_dir}"
)
print()


NEW_DASHBOARD_ROUTE = r'''@app.route("/")
def dashboard():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    clients = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE status = 'Client'
        """
    ).fetchone()[0]

    audited = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE audit_status = 'completed'
        """
    ).fetchone()[0]

    google_prospects = conn.execute(
        """
        SELECT COUNT(*)
        FROM businesses
        WHERE source = 'google_places'
        """
    ).fetchone()[0]

    pending_approvals = conn.execute(
        """
        SELECT COUNT(*)
        FROM approvals
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    total_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        """
    ).fetchone()[0]

    new_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'New'
        """
    ).fetchone()[0]

    urgent_leads_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE priority = 'Urgent'
          AND status NOT IN ('Won', 'Lost')
        """
    ).fetchone()[0]

    needs_follow_up = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status IN ('New', 'Contacted')
          AND appointment_status != 'Scheduled'
        """
    ).fetchone()[0]

    contacted_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Contacted'
        """
    ).fetchone()[0]

    scheduled_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Estimate Scheduled'
           OR appointment_status = 'Scheduled'
        """
    ).fetchone()[0]

    won_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Won'
        """
    ).fetchone()[0]

    lost_leads = conn.execute(
        """
        SELECT COUNT(*)
        FROM leads
        WHERE status = 'Lost'
        """
    ).fetchone()[0]

    recent_leads = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        ORDER BY leads.id DESC
        LIMIT 6
        """
    ).fetchall()

    urgent_leads = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        WHERE leads.priority = 'Urgent'
          AND leads.status NOT IN ('Won', 'Lost')
        ORDER BY leads.id DESC
        LIMIT 4
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    high_opportunity = sum(
        1
        for business in businesses
        if business["analysis"]["level"] == "High"
    )

    closed_leads = (
        won_leads + lost_leads
    )

    if closed_leads:
        conversion_rate = round(
            (won_leads / closed_leads) * 100
        )
    else:
        conversion_rate = 0

    pipeline = [
        {
            "name": "New",
            "count": new_leads,
        },
        {
            "name": "Contacted",
            "count": contacted_leads,
        },
        {
            "name": "Estimate Scheduled",
            "count": scheduled_leads,
        },
        {
            "name": "Won",
            "count": won_leads,
        },
    ]

    pipeline_max = max(
        [
            stage["count"]
            for stage in pipeline
        ]
        + [1]
    )

    return render_template(
        "dashboard.html",
        businesses=businesses[:8],
        total=len(businesses),
        high=high_opportunity,
        clients=clients,
        audited=audited,
        discovered=google_prospects,
        pending=pending_approvals,
        total_leads=total_leads,
        new_leads=new_leads,
        urgent_leads_count=urgent_leads_count,
        needs_follow_up=needs_follow_up,
        scheduled_leads=scheduled_leads,
        won_leads=won_leads,
        conversion_rate=conversion_rate,
        recent_leads=recent_leads,
        urgent_leads=urgent_leads,
        pipeline=pipeline,
        pipeline_max=pipeline_max,
    )

'''


NEW_BASE = r'''<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>
        {% block title %}Business OS{% endblock %}
    </title>

    <link
        rel="stylesheet"
        href="{{ url_for(
            'static',
            filename='styles.css'
        ) }}"
    >
</head>


<body>

<div class="app-shell">

    <aside class="sidebar">

        <div class="sidebar-brand">
            <div class="brand-mark">
                B
            </div>

            <div class="brand-copy">
                <strong>Business OS</strong>
                <span>AI Growth Platform</span>
            </div>
        </div>


        <div class="sidebar-section-label">
            Command Center
        </div>


        <nav class="sidebar-nav">

            <a
                class="{% if request.endpoint == 'dashboard' %}
                    active
                {% endif %}"
                href="{{ url_for('dashboard') }}"
            >
                <span class="nav-icon">⌂</span>
                <span class="nav-label">
                    Dashboard
                </span>
            </a>


            <a
                class="{% if request.endpoint in [
                    'leads',
                    'lead_detail',
                    'update_lead_status'
                ] %}
                    active
                {% endif %}"
                href="{{ url_for('leads') }}"
            >
                <span class="nav-icon">◎</span>
                <span class="nav-label">
                    Leads
                </span>
            </a>


            <a
                class="{% if request.endpoint == 'calls' %}
                    active
                {% endif %}"
                href="{{ url_for('calls') }}"
            >
                <span class="nav-icon">☎</span>
                <span class="nav-label">
                    Calls
                </span>
            </a>

        </nav>


        <div class="sidebar-section-label">
            Growth
        </div>


        <nav class="sidebar-nav">

            <a
                class="{% if request.endpoint in [
                    'prospects',
                    'business_detail'
                ] %}
                    active
                {% endif %}"
                href="{{ url_for('prospects') }}"
            >
                <span class="nav-icon">⌕</span>

                <span class="nav-label">
                    Prospects
                </span>

                <span class="nav-count">
                    {{ global_prospect_count }}
                </span>
            </a>


            <a
                class="{% if request.endpoint == 'audits' %}
                    active
                {% endif %}"
                href="{{ url_for('audits') }}"
            >
                <span class="nav-icon">◇</span>
                <span class="nav-label">
                    Audits
                </span>
            </a>


            <a
                class="{% if request.endpoint == 'agents' %}
                    active
                {% endif %}"
                href="{{ url_for('agents') }}"
            >
                <span class="nav-icon">✦</span>
                <span class="nav-label">
                    Agents
                </span>
            </a>

        </nav>


        <div class="sidebar-section-label">
            Operations
        </div>


        <nav class="sidebar-nav">

            <a
                class="{% if request.endpoint == 'approvals' %}
                    active
                {% endif %}"
                href="{{ url_for('approvals') }}"
            >
                <span class="nav-icon">✓</span>

                <span class="nav-label">
                    Approvals
                </span>

                {% if global_pending_approvals %}
                <span class="nav-count alert">
                    {{ global_pending_approvals }}
                </span>
                {% endif %}
            </a>


            <a
                class="{% if request.endpoint == 'clients' %}
                    active
                {% endif %}"
                href="{{ url_for('clients') }}"
            >
                <span class="nav-icon">▣</span>
                <span class="nav-label">
                    Clients
                </span>
            </a>

        </nav>


        <div class="sidebar-footer">

            <div class="workspace-status">
                <span class="status-dot"></span>

                <div>
                    <strong>
                        Local Workspace
                    </strong>

                    <span>
                        Development environment
                    </span>
                </div>
            </div>

            <div class="version">
                Business OS · v3
            </div>

        </div>

    </aside>


    <main class="main">

        <header class="topbar">

            <div class="topbar-title">
                <small>
                    BUSINESS OS
                </small>

                <h1>
                    {% block heading %}
                        Command Center
                    {% endblock %}
                </h1>
            </div>


            <div class="topbar-actions">
                {% block actions %}
                {% endblock %}
            </div>

        </header>


        {% with
            msgs=get_flashed_messages(
                with_categories=true
            )
        %}

            {% if msgs %}
            <div class="flashes">

                {% for cat, msg in msgs %}
                <div class="flash {{ cat }}">
                    {{ msg }}
                </div>
                {% endfor %}

            </div>
            {% endif %}

        {% endwith %}


        <section class="page-content">
            {% block content %}
            {% endblock %}
        </section>

    </main>

</div>


<script
    src="{{ url_for(
        'static',
        filename='app.js'
    ) }}"
></script>

</body>
</html>
'''


NEW_DASHBOARD = r'''{% extends "base.html" %}

{% block title %}
Business OS · Command Center
{% endblock %}

{% block heading %}
Command Center
{% endblock %}

{% block actions %}
<a
    class="btn secondary"
    href="{{ url_for('prospects') }}"
>
    Find Prospects
</a>

<a
    class="btn"
    href="{{ url_for('leads') }}"
>
    View Leads
</a>
{% endblock %}


{% block content %}

<div class="command-hero">

    <div class="command-hero-copy">

        <div class="eyebrow">
            AI FRONT OFFICE
        </div>

        <h2>
            Know what needs attention
            before opportunities go cold.
        </h2>

        <p>
            Business OS brings incoming leads,
            calls, estimates, prospect research,
            and follow-up into one operating
            view.
        </p>

    </div>


    <div class="command-hero-stats">

        <div>
            <span>
                Leads captured
            </span>

            <strong>
                {{ total_leads }}
            </strong>
        </div>


        <div>
            <span>
                Closed win rate
            </span>

            <strong>
                {{ conversion_rate }}%
            </strong>
        </div>

    </div>

</div>


<div class="section-heading">

    <div>
        <span class="section-kicker">
            INCOMING DEMAND
        </span>

        <h2>
            Front Office
        </h2>
    </div>

    <a
        href="{{ url_for('leads') }}"
        class="text-link"
    >
        Open all leads →
    </a>

</div>


<div class="metric-grid">

    <a
        href="{{ url_for('leads') }}"
        class="metric-card"
    >
        <div class="metric-top">
            <span class="metric-icon">
                ◎
            </span>

            <span class="metric-label">
                New Leads
            </span>
        </div>

        <strong>
            {{ new_leads }}
        </strong>

        <p>
            Newly captured opportunities.
        </p>
    </a>


    <a
        href="{{ url_for('leads') }}"
        class="metric-card urgent"
    >
        <div class="metric-top">
            <span class="metric-icon">
                !
            </span>

            <span class="metric-label">
                Urgent
            </span>
        </div>

        <strong>
            {{ urgent_leads_count }}
        </strong>

        <p>
            Open leads marked urgent.
        </p>
    </a>


    <a
        href="{{ url_for('leads') }}"
        class="metric-card"
    >
        <div class="metric-top">
            <span class="metric-icon">
                ↗
            </span>

            <span class="metric-label">
                Need Follow-Up
            </span>
        </div>

        <strong>
            {{ needs_follow_up }}
        </strong>

        <p>
            Open leads without a scheduled estimate.
        </p>
    </a>


    <a
        href="{{ url_for('leads') }}"
        class="metric-card"
    >
        <div class="metric-top">
            <span class="metric-icon">
                ◷
            </span>

            <span class="metric-label">
                Estimates Scheduled
            </span>
        </div>

        <strong>
            {{ scheduled_leads }}
        </strong>

        <p>
            Leads with estimates on the board.
        </p>
    </a>


    <a
        href="{{ url_for('leads') }}"
        class="metric-card positive"
    >
        <div class="metric-top">
            <span class="metric-icon">
                ✓
            </span>

            <span class="metric-label">
                Won
            </span>
        </div>

        <strong>
            {{ won_leads }}
        </strong>

        <p>
            Opportunities marked as won.
        </p>
    </a>

</div>


<div class="dashboard-grid">

    <div class="dashboard-main">

        <div class="panel command-panel">

            <div class="panel-heading">

                <div>
                    <span class="section-kicker">
                        PIPELINE
                    </span>

                    <h3>
                        Lead Progress
                    </h3>
                </div>

                <span class="panel-meta">
                    {{ total_leads }} total leads
                </span>

            </div>


            <div class="pipeline-chart">

                {% for stage in pipeline %}

                <div class="pipeline-row">

                    <div class="pipeline-label">
                        <span>
                            {{ stage["name"] }}
                        </span>

                        <strong>
                            {{ stage["count"] }}
                        </strong>
                    </div>


                    <div class="pipeline-track">

                        <div
                            class="pipeline-fill"
                            style="width:
                                {{
                                    (
                                        stage['count']
                                        / pipeline_max
                                        * 100
                                    )
                                    | round
                                }}%;
                            "
                        ></div>

                    </div>

                </div>

                {% endfor %}

            </div>

        </div>


        <div class="panel command-panel">

            <div class="panel-heading">

                <div>
                    <span class="section-kicker">
                        ACTIVITY
                    </span>

                    <h3>
                        Recent Leads
                    </h3>
                </div>

                <a
                    href="{{ url_for('leads') }}"
                    class="text-link"
                >
                    View all →
                </a>

            </div>


            {% if recent_leads %}

            <div class="lead-feed">

                {% for lead in recent_leads %}

                <a
                    class="lead-feed-row"
                    href="{{ url_for(
                        'lead_detail',
                        lead_id=lead['id']
                    ) }}"
                >

                    <div class="lead-avatar">
                        {{
                            (
                                lead["caller_name"]
                                or "?"
                            )[0]
                            | upper
                        }}
                    </div>


                    <div class="lead-feed-main">

                        <div class="lead-feed-name">
                            {{
                                lead["caller_name"]
                                or "Unknown Caller"
                            }}
                        </div>

                        <div class="lead-feed-detail">
                            {{
                                lead["service_type"]
                                or "Service not specified"
                            }}

                            {% if lead["preferred_time"] %}
                                ·
                                {{ lead["preferred_time"] }}
                            {% endif %}
                        </div>

                    </div>


                    <div class="lead-feed-right">

                        {% if lead["priority"] == "Urgent" %}
                        <span class="status-pill urgent">
                            Urgent
                        </span>

                        {% else %}
                        <span class="status-pill">
                            {{ lead["status"] }}
                        </span>
                        {% endif %}

                        <span class="row-arrow">
                            →
                        </span>

                    </div>

                </a>

                {% endfor %}

            </div>


            {% else %}

            <div class="empty-state">
                <div class="empty-icon">
                    ◎
                </div>

                <h4>
                    No leads yet
                </h4>

                <p>
                    New receptionist leads will
                    appear here automatically.
                </p>
            </div>

            {% endif %}

        </div>

    </div>


    <div class="dashboard-side">

        <div class="panel command-panel urgent-panel">

            <div class="panel-heading">

                <div>
                    <span class="section-kicker danger">
                        ATTENTION
                    </span>

                    <h3>
                        Urgent Queue
                    </h3>
                </div>

                <span class="count-bubble">
                    {{ urgent_leads_count }}
                </span>

            </div>


            {% if urgent_leads %}

                <div class="urgent-list">

                    {% for lead in urgent_leads %}

                    <a
                        href="{{ url_for(
                            'lead_detail',
                            lead_id=lead['id']
                        ) }}"
                        class="urgent-item"
                    >

                        <div>
                            <strong>
                                {{
                                    lead["caller_name"]
                                    or "Unknown Caller"
                                }}
                            </strong>

                            <span>
                                {{
                                    lead["service_type"]
                                    or "Service request"
                                }}
                            </span>

                            {% if lead["safety_flag"] %}
                            <small>
                                {{ lead["safety_flag"] }}
                            </small>
                            {% endif %}
                        </div>

                        <span>
                            →
                        </span>

                    </a>

                    {% endfor %}

                </div>


            {% else %}

                <div class="clear-state">

                    <span class="clear-check">
                        ✓
                    </span>

                    <div>
                        <strong>
                            No open urgent leads
                        </strong>

                        <p>
                            Nothing currently requires
                            urgent escalation.
                        </p>
                    </div>

                </div>

            {% endif %}

        </div>


        <div class="panel command-panel">

            <div class="panel-heading">

                <div>
                    <span class="section-kicker">
                        GROWTH ENGINE
                    </span>

                    <h3>
                        Prospecting
                    </h3>
                </div>

            </div>


            <div class="mini-stats">

                <div>
                    <span>
                        Prospects
                    </span>

                    <strong>
                        {{ total }}
                    </strong>
                </div>


                <div>
                    <span>
                        Google
                    </span>

                    <strong>
                        {{ discovered }}
                    </strong>
                </div>


                <div>
                    <span>
                        Audited
                    </span>

                    <strong>
                        {{ audited }}
                    </strong>
                </div>


                <div>
                    <span>
                        High Opportunity
                    </span>

                    <strong>
                        {{ high }}
                    </strong>
                </div>

            </div>


            <a
                href="{{ url_for('prospects') }}"
                class="panel-button"
            >
                Open Opportunity Finder
                <span>→</span>
            </a>

        </div>

    </div>

</div>


<div class="section-heading lower">

    <div>
        <span class="section-kicker">
            PROSPECT RESEARCH
        </span>

        <h2>
            Recent Prospects
        </h2>
    </div>

</div>


<div class="panel">
    {% include "_table.html" %}
</div>

{% endblock %}
'''


NEW_STYLES = r''':root {
    --bg: #f4f7f5;
    --surface: #ffffff;
    --surface-soft: #f8faf9;
    --surface-green: #f2faf5;

    --ink: #15231b;
    --ink-soft: #33483b;
    --muted: #718078;
    --muted-light: #97a29c;

    --line: #dfe7e1;
    --line-soft: #edf2ee;

    --sidebar: #0d1d14;
    --sidebar-deep: #09150e;
    --sidebar-text: #a9bbb0;

    --accent: #177548;
    --accent-dark: #115b38;
    --accent-soft: #e8f6ee;

    --danger: #b64242;
    --danger-soft: #fff0f0;

    --warning: #a96b16;
    --warning-soft: #fff7e8;

    --shadow-xs:
        0 1px 2px rgba(17, 35, 23, .04);

    --shadow-sm:
        0 5px 18px rgba(17, 35, 23, .045);

    --shadow-md:
        0 16px 40px rgba(17, 35, 23, .08);

    --radius-sm: 9px;
    --radius-md: 14px;
    --radius-lg: 19px;
    --radius-xl: 24px;
}


* {
    box-sizing: border-box;
}


html {
    background: var(--bg);
}


body {
    margin: 0;
    min-height: 100vh;
    background:
        radial-gradient(
            circle at 85% 0%,
            rgba(23, 117, 72, .045),
            transparent 28%
        ),
        var(--bg);

    color: var(--ink);

    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    -webkit-font-smoothing: antialiased;
}


a {
    color: var(--accent);
}


button,
input,
select,
textarea {
    font: inherit;
}


/* APP SHELL */

.app-shell,
.shell {
    display: grid;
    grid-template-columns: 250px minmax(0, 1fr);
    min-height: 100vh;
}


.sidebar,
aside {
    position: sticky;
    top: 0;

    display: flex;
    flex-direction: column;

    height: 100vh;
    padding: 24px 15px;

    overflow-y: auto;

    background:
        radial-gradient(
            circle at 10% 5%,
            rgba(67, 164, 106, .13),
            transparent 25%
        ),
        linear-gradient(
            180deg,
            var(--sidebar),
            var(--sidebar-deep)
        );

    color: white;
}


.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 11px;

    padding: 3px 8px 26px;
}


.brand-mark {
    display: flex;
    align-items: center;
    justify-content: center;

    width: 38px;
    height: 38px;

    border: 1px solid rgba(255,255,255,.13);
    border-radius: 11px;

    background:
        linear-gradient(
            145deg,
            #268e5b,
            #12623c
        );

    color: white;

    font-size: 17px;
    font-weight: 900;

    box-shadow:
        inset 0 1px rgba(255,255,255,.15),
        0 5px 18px rgba(0,0,0,.18);
}


.brand-copy {
    min-width: 0;
}


.brand-copy strong {
    display: block;
    color: white;
    font-size: 15px;
}


.brand-copy span {
    display: block;
    margin-top: 2px;

    color: #7f9789;
    font-size: 10px;
}


.brand {
    padding: 0 8px 28px;
}


.brand b,
.brand span {
    display: block;
}


.brand b {
    color: #fff;
    font-size: 18px;
}


.brand span {
    margin-top: 4px;
    color: #8fa697;
    font-size: 11px;
}


.sidebar-section-label {
    margin: 11px 10px 7px;

    color: #60776a;

    font-size: 9px;
    font-weight: 900;

    letter-spacing: .13em;
    text-transform: uppercase;
}


.sidebar-nav,
nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
}


.sidebar-nav a,
nav a {
    display: flex;
    align-items: center;

    min-height: 42px;

    padding: 9px 10px;

    border: 1px solid transparent;
    border-radius: 10px;

    color: var(--sidebar-text);

    text-decoration: none;

    font-size: 12px;
    font-weight: 650;

    transition:
        color 130ms ease,
        background 130ms ease,
        border-color 130ms ease,
        transform 130ms ease;
}


.sidebar-nav a:hover,
nav a:hover {
    background: rgba(255,255,255,.055);
    color: white;
}


.sidebar-nav a.active {
    border-color: rgba(119, 199, 149, .13);

    background:
        linear-gradient(
            90deg,
            rgba(40, 135, 83, .22),
            rgba(255,255,255,.035)
        );

    color: white;
}


.nav-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    width: 25px;
    margin-right: 5px;

    color: #84a491;

    font-size: 15px;
}


.active .nav-icon {
    color: #70d09a;
}


.nav-label {
    flex: 1;
}


.nav-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-width: 22px;
    height: 20px;

    padding: 0 6px;

    border-radius: 999px;

    background: rgba(255,255,255,.07);

    color: #9db0a4;

    font-size: 9px;
    font-weight: 900;
}


.nav-count.alert {
    background: rgba(207, 79, 79, .19);
    color: #ffb8b8;
}


.sidebar-footer {
    margin-top: auto;
    padding-top: 22px;
}


.workspace-status {
    display: flex;
    align-items: flex-start;
    gap: 9px;

    padding: 12px;

    border: 1px solid rgba(255,255,255,.065);
    border-radius: 11px;

    background: rgba(255,255,255,.025);
}


.status-dot {
    width: 7px;
    height: 7px;

    margin-top: 5px;

    border-radius: 50%;

    background: #56c983;

    box-shadow:
        0 0 0 4px rgba(86, 201, 131, .08);
}


.workspace-status strong,
.workspace-status span {
    display: block;
}


.workspace-status strong {
    color: #dce8df;
    font-size: 10px;
}


.workspace-status span {
    margin-top: 2px;
    color: #718679;
    font-size: 9px;
}


.version {
    margin-top: 13px;
    padding: 0 10px;

    color: #53675a;
    font-size: 9px;
}


/* MAIN AREA */

.main,
main {
    min-width: 0;
}


.topbar,
header {
    position: sticky;
    top: 0;
    z-index: 20;

    display: flex;
    align-items: center;
    justify-content: space-between;

    min-height: 82px;

    padding: 0 32px;

    border-bottom: 1px solid rgba(214, 224, 217, .88);

    background: rgba(255,255,255,.84);

    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}


.topbar-title small,
header small {
    display: block;

    color: #84918a;

    font-size: 9px;
    font-weight: 900;

    letter-spacing: .15em;
}


.topbar-title h1,
header h1 {
    margin: 4px 0 0;

    color: var(--ink);

    font-size: 21px;
    line-height: 1.15;
}


.topbar-actions,
.actions {
    display: flex;
    align-items: center;
    gap: 8px;
}


.page-content,
section {
    width: 100%;
    max-width: 1500px;

    margin: auto;

    padding: 28px 32px 52px;
}


/* BUTTONS */

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 38px;

    padding: 9px 14px;

    border: 1px solid transparent;
    border-radius: 10px;

    background:
        linear-gradient(
            180deg,
            #208354,
            var(--accent)
        );

    color: white;

    cursor: pointer;

    font-size: 12px;
    font-weight: 800;

    text-decoration: none;

    box-shadow:
        0 2px 5px rgba(23, 117, 72, .12);

    transition:
        transform 120ms ease,
        box-shadow 120ms ease,
        background 120ms ease;
}


.btn:hover {
    transform: translateY(-1px);

    box-shadow:
        0 6px 15px rgba(23,117,72,.16);
}


.btn.secondary {
    border-color: var(--line);
    background: white;
    color: var(--ink-soft);
    box-shadow: var(--shadow-xs);
}


/* FLASH MESSAGES */

.flashes {
    padding: 13px 32px 0;
}


.flash {
    padding: 11px 13px;

    border: 1px solid transparent;
    border-radius: 10px;

    font-size: 12px;
    font-weight: 700;
}


.flash.success {
    border-color: #bee4ca;
    background: #eaf8ef;
    color: #17633d;
}


.flash.error {
    border-color: #f0cccc;
    background: #fff0f0;
    color: #963d3d;
}


/* COMMAND CENTER HERO */

.command-hero {
    position: relative;
    overflow: hidden;

    display: flex;
    justify-content: space-between;
    gap: 40px;

    min-height: 215px;

    padding: 32px 34px;

    border: 1px solid #214934;
    border-radius: var(--radius-xl);

    background:
        radial-gradient(
            circle at 85% 20%,
            rgba(78, 188, 122, .2),
            transparent 25%
        ),
        linear-gradient(
            135deg,
            #10281b,
            #163d29 62%,
            #1c4b34
        );

    color: white;

    box-shadow: var(--shadow-md);
}


.command-hero::after {
    content: "";

    position: absolute;
    right: -75px;
    bottom: -120px;

    width: 300px;
    height: 300px;

    border: 1px solid rgba(255,255,255,.07);
    border-radius: 50%;

    box-shadow:
        0 0 0 35px rgba(255,255,255,.025),
        0 0 0 75px rgba(255,255,255,.018);
}


.command-hero-copy {
    position: relative;
    z-index: 2;

    max-width: 720px;
}


.eyebrow {
    display: inline-flex;

    padding: 6px 9px;

    border: 1px solid rgba(255,255,255,.09);
    border-radius: 999px;

    background: rgba(255,255,255,.07);

    color: #a9d9ba;

    font-size: 9px;
    font-weight: 900;

    letter-spacing: .13em;
}


.command-hero h2 {
    max-width: 680px;

    margin: 15px 0 10px;

    color: white;

    font-size: clamp(27px, 3vw, 38px);
    line-height: 1.12;

    letter-spacing: -.02em;
}


.command-hero p {
    max-width: 680px;

    margin: 0;

    color: #aec4b6;

    font-size: 13px;
    line-height: 1.7;
}


.command-hero-stats {
    position: relative;
    z-index: 2;

    display: grid;
    grid-template-columns: repeat(2, minmax(110px, 1fr));
    gap: 10px;

    align-self: flex-end;

    min-width: 285px;
}


.command-hero-stats div {
    padding: 15px;

    border: 1px solid rgba(255,255,255,.09);
    border-radius: 13px;

    background: rgba(255,255,255,.055);

    backdrop-filter: blur(8px);
}


.command-hero-stats span,
.command-hero-stats strong {
    display: block;
}


.command-hero-stats span {
    color: #98afa0;
    font-size: 9px;
    font-weight: 700;
}


.command-hero-stats strong {
    margin-top: 6px;

    color: white;

    font-size: 27px;
}


/* HEADINGS */

.section-heading {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;

    gap: 20px;

    margin: 31px 2px 13px;
}


.section-heading.lower {
    margin-top: 35px;
}


.section-heading h2 {
    margin: 3px 0 0;

    color: var(--ink);

    font-size: 19px;
}


.section-kicker {
    color: #839188;

    font-size: 9px;
    font-weight: 900;

    letter-spacing: .12em;
}


.section-kicker.danger {
    color: #bd5555;
}


.text-link {
    color: var(--accent);

    font-size: 11px;
    font-weight: 800;

    text-decoration: none;
}


.text-link:hover {
    text-decoration: underline;
}


/* METRICS */

.metric-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;

    margin-bottom: 18px;
}


.metric-card {
    position: relative;

    min-width: 0;

    padding: 17px;

    border: 1px solid var(--line);
    border-radius: 16px;

    background: var(--surface);

    color: var(--ink);

    text-decoration: none;

    box-shadow: var(--shadow-xs);

    transition:
        transform 130ms ease,
        border-color 130ms ease,
        box-shadow 130ms ease;
}


.metric-card:hover {
    transform: translateY(-2px);

    border-color: #c7d7cb;

    box-shadow: var(--shadow-sm);
}


.metric-card.urgent {
    border-color: #f0d1d1;

    background:
        linear-gradient(
            180deg,
            #fff,
            #fffafa
        );
}


.metric-card.positive {
    border-color: #cce4d4;

    background:
        linear-gradient(
            180deg,
            #fff,
            #fafffb
        );
}


.metric-top {
    display: flex;
    align-items: center;
    gap: 8px;
}


.metric-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    width: 27px;
    height: 27px;

    border-radius: 8px;

    background: var(--accent-soft);

    color: var(--accent);

    font-size: 12px;
    font-weight: 900;
}


.metric-card.urgent .metric-icon {
    background: var(--danger-soft);
    color: var(--danger);
}


.metric-label {
    color: var(--muted);

    font-size: 10px;
    font-weight: 800;
}


.metric-card > strong {
    display: block;

    margin-top: 13px;

    color: var(--ink);

    font-size: 28px;
    line-height: 1;
}


.metric-card p {
    margin: 8px 0 0;

    color: var(--muted-light);

    font-size: 9px;
    line-height: 1.45;
}


/* DASHBOARD LAYOUT */

.dashboard-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(300px, .75fr);
    gap: 16px;

    align-items: start;
}


.dashboard-main,
.dashboard-side {
    display: flex;
    flex-direction: column;
    gap: 16px;
}


/* PANELS */

.panel,
.detailhead,
.kpis > div {
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);

    background: var(--surface);

    box-shadow: var(--shadow-xs);
}


.panel {
    padding: 20px;
    margin-bottom: 18px;
}


.command-panel {
    margin: 0;
}


.panel.green {
    border-color: #c7e1d0;

    background:
        linear-gradient(
            180deg,
            #fff,
            #fbfffc
        );
}


.panel h3 {
    margin: 0 0 15px;
}


.panel-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;

    gap: 15px;

    margin-bottom: 18px;
}


.panel-heading h3 {
    margin: 3px 0 0;

    font-size: 15px;
}


.panel-meta {
    color: var(--muted-light);

    font-size: 9px;
}


.count-bubble {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-width: 25px;
    height: 25px;

    border-radius: 999px;

    background: var(--danger-soft);

    color: var(--danger);

    font-size: 10px;
    font-weight: 900;
}


/* PIPELINE */

.pipeline-chart {
    display: flex;
    flex-direction: column;
    gap: 15px;
}


.pipeline-label {
    display: flex;
    justify-content: space-between;

    margin-bottom: 6px;
}


.pipeline-label span {
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
}


.pipeline-label strong {
    color: var(--ink-soft);
    font-size: 10px;
}


.pipeline-track {
    overflow: hidden;

    height: 7px;

    border-radius: 999px;

    background: #edf2ee;
}


.pipeline-fill {
    min-width: 3px;
    height: 100%;

    border-radius: inherit;

    background:
        linear-gradient(
            90deg,
            #23915c,
            #63b985
        );

    transition: width 300ms ease;
}


/* LEAD FEED */

.lead-feed {
    margin: 0 -5px -5px;
}


.lead-feed-row {
    display: flex;
    align-items: center;
    gap: 11px;

    padding: 11px 8px;

    border-bottom: 1px solid var(--line-soft);
    border-radius: 9px;

    color: var(--ink);

    text-decoration: none;

    transition:
        background 120ms ease;
}


.lead-feed-row:last-child {
    border-bottom: 0;
}


.lead-feed-row:hover {
    background: var(--surface-soft);
}


.lead-avatar {
    display: flex;
    align-items: center;
    justify-content: center;

    flex: 0 0 auto;

    width: 33px;
    height: 33px;

    border-radius: 10px;

    background: var(--accent-soft);

    color: var(--accent-dark);

    font-size: 11px;
    font-weight: 900;
}


.lead-feed-main {
    min-width: 0;
    flex: 1;
}


.lead-feed-name {
    overflow: hidden;

    color: var(--ink);

    font-size: 11px;
    font-weight: 800;

    text-overflow: ellipsis;
    white-space: nowrap;
}


.lead-feed-detail {
    overflow: hidden;

    margin-top: 3px;

    color: var(--muted);

    font-size: 9px;

    text-overflow: ellipsis;
    white-space: nowrap;
}


.lead-feed-right {
    display: flex;
    align-items: center;
    gap: 8px;
}


.status-pill {
    display: inline-flex;

    padding: 5px 7px;

    border-radius: 999px;

    background: #eef3ef;

    color: #5f6d64;

    font-size: 8px;
    font-weight: 900;
}


.status-pill.urgent {
    background: var(--danger-soft);
    color: var(--danger);
}


.row-arrow {
    color: #a1aaa4;
    font-size: 12px;
}


/* URGENT QUEUE */

.urgent-panel {
    border-color: #efdada;

    background:
        linear-gradient(
            180deg,
            #fff,
            #fffdfd
        );
}


.urgent-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}


.urgent-item {
    display: flex;
    align-items: center;
    justify-content: space-between;

    gap: 10px;

    padding: 11px;

    border: 1px solid #f1dddd;
    border-radius: 11px;

    background: white;

    color: var(--ink);

    text-decoration: none;
}


.urgent-item:hover {
    border-color: #e7c0c0;
    background: #fffafa;
}


.urgent-item strong,
.urgent-item span,
.urgent-item small {
    display: block;
}


.urgent-item strong {
    font-size: 10px;
}


.urgent-item span {
    margin-top: 2px;

    color: var(--muted);

    font-size: 9px;
}


.urgent-item small {
    margin-top: 5px;

    color: var(--danger);

    font-size: 8px;
    line-height: 1.4;
}


.clear-state {
    display: flex;
    align-items: flex-start;
    gap: 11px;

    padding: 13px;

    border: 1px solid #d8e9dd;
    border-radius: 11px;

    background: #f8fcf9;
}


.clear-check {
    display: flex;
    align-items: center;
    justify-content: center;

    width: 27px;
    height: 27px;

    border-radius: 8px;

    background: var(--accent-soft);

    color: var(--accent);

    font-weight: 900;
}


.clear-state strong {
    display: block;

    color: var(--ink-soft);

    font-size: 10px;
}


.clear-state p {
    margin: 3px 0 0;

    color: var(--muted);

    font-size: 9px;
    line-height: 1.45;
}


/* MINI STATS */

.mini-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 9px;
}


.mini-stats div {
    padding: 11px;

    border: 1px solid var(--line-soft);
    border-radius: 11px;

    background: var(--surface-soft);
}


.mini-stats span,
.mini-stats strong {
    display: block;
}


.mini-stats span {
    color: var(--muted);

    font-size: 8px;
    font-weight: 700;
}


.mini-stats strong {
    margin-top: 5px;

    color: var(--ink);

    font-size: 20px;
}


.panel-button {
    display: flex;
    align-items: center;
    justify-content: space-between;

    margin-top: 12px;
    padding: 11px 12px;

    border-radius: 10px;

    background: var(--accent-soft);

    color: var(--accent-dark);

    font-size: 10px;
    font-weight: 900;

    text-decoration: none;
}


.panel-button:hover {
    background: #dcf0e4;
}


/* EMPTY STATE */

.empty-state {
    padding: 30px 20px;
    text-align: center;
}


.empty-icon {
    display: flex;
    align-items: center;
    justify-content: center;

    width: 38px;
    height: 38px;

    margin: auto;

    border-radius: 11px;

    background: var(--surface-soft);

    color: var(--muted);
}


.empty-state h4 {
    margin: 10px 0 4px;

    font-size: 12px;
}


.empty-state p {
    margin: 0;

    color: var(--muted);

    font-size: 9px;
}


/* EXISTING APP COMPONENTS */

.hero {
    padding: 28px;
    margin-bottom: 18px;

    border-radius: 22px;

    background:
        linear-gradient(
            135deg,
            #132a1d,
            #1c4932
        );

    color: #fff;

    box-shadow: var(--shadow-md);
}


.hero span {
    padding: 6px 9px;

    border-radius: 99px;

    background: rgba(255,255,255,.1);

    font-size: 10px;
    font-weight: 900;
    letter-spacing: .12em;
}


.hero h2 {
    margin: 14px 0 8px;
    font-size: 30px;
}


.hero p {
    max-width: 760px;

    margin: 0;

    color: #bad0c1;

    line-height: 1.6;
}


.kpis {
    display: grid;
    grid-template-columns: repeat(4,1fr);
    gap: 14px;

    margin-bottom: 18px;
}


.kpis > div {
    padding: 19px;
}


.kpis span {
    display: block;

    color: var(--muted);

    font-size: 12px;
}


.kpis strong {
    display: block;

    margin-top: 6px;

    font-size: 30px;
}


.tablewrap {
    overflow: auto;
}


table {
    width: 100%;

    border-collapse: collapse;

    min-width: 790px;
}


th {
    padding: 11px 12px;

    border-bottom: 1px solid var(--line);

    color: #7d8981;

    font-size: 10px;
    font-weight: 800;

    letter-spacing: .08em;
    text-align: left;
    text-transform: uppercase;
}


td {
    padding: 13px 12px;

    border-bottom: 1px solid var(--line-soft);

    font-size: 13px;
}


tbody tr {
    transition: background 110ms ease;
}


tbody tr:hover {
    background: #fafcfb;
}


td b,
td small {
    display: block;
}


td small {
    margin-top: 3px;

    color: var(--muted);

    font-size: 11px;
}


.badge {
    display: inline-flex;

    padding: 5px 8px;

    border-radius: 999px;

    background: #eef2ef;

    color: #5f6c63;

    font-size: 10px;
    font-weight: 900;
}


.badge.live {
    background: var(--accent-soft);
    color: #17603d;
}


.rowform,
.filters,
.gridform {
    display: flex;
    align-items: end;
    gap: 10px;
    flex-wrap: wrap;
}


.rowform label {
    flex: 1;
    min-width: 170px;
}


.filters {
    margin-bottom: 18px;
}


.filters input,
.filters select {
    flex: 1;
    min-width: 150px;
}


.gridform {
    display: grid;
    grid-template-columns: repeat(4,1fr);
}


label {
    color: #637067;

    font-size: 11px;
    font-weight: 800;
}


input,
select,
textarea {
    width: 100%;

    padding: 10px 11px;

    border: 1px solid #d9e0da;
    border-radius: 9px;

    outline: none;

    background: white;
    color: var(--ink);

    font-size: 13px;

    transition:
        border-color 120ms ease,
        box-shadow 120ms ease;
}


input:focus,
select:focus,
textarea:focus {
    border-color: #8ac2a0;

    box-shadow:
        0 0 0 3px rgba(23,117,72,.08);
}


label input,
label select {
    margin-top: 6px;
}


.muted {
    color: var(--muted);

    font-size: 12px;
    line-height: 1.6;
}


.detailhead {
    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 24px;
    margin-bottom: 18px;
}


.detailhead h2 {
    margin: 10px 0 5px;

    font-size: 30px;
}


.detailhead p {
    color: var(--muted);
}


.scorebox {
    min-width: 145px;

    padding: 16px;

    border-radius: 14px;

    background: #f4f7f4;

    text-align: center;
}


.scorebox span,
.scorebox small {
    display: block;

    color: var(--muted);

    font-size: 11px;
}


.scorebox strong {
    display: block;

    font-size: 38px;
}


.two {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 18px;
}


.features {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 10px;
}


.features > div {
    padding: 13px;

    border: 1px solid #e5ebe6;
    border-radius: 12px;

    background: #fbfcfb;
}


.features span,
.features strong {
    display: block;
}


.features span {
    color: var(--muted);

    font-size: 10px;

    text-transform: uppercase;
}


.features strong {
    margin-top: 5px;

    font-size: 13px;
}


.reason {
    display: flex;
    justify-content: space-between;

    padding: 10px 0;

    border-bottom: 1px solid var(--line-soft);

    font-size: 13px;
}


.reason strong {
    color: var(--accent);
}


.evidence {
    padding: 14px 0;

    border-top: 1px solid var(--line);
}


.evidence:first-of-type {
    border-top: 0;
}


.evidence p {
    color: #5f6b63;
    font-size: 12px;
}


.cards {
    display: grid;
    grid-template-columns: repeat(2,1fr);
    gap: 16px;
}


/* RESPONSIVE */

@media (max-width: 1150px) {

    .metric-grid {
        grid-template-columns:
            repeat(3, minmax(0, 1fr));
    }

    .dashboard-grid {
        grid-template-columns: 1fr;
    }

}


@media (max-width: 900px) {

    .app-shell,
    .shell {
        grid-template-columns: 1fr;
    }

    .sidebar,
    aside {
        display: none;
    }

    .command-hero {
        flex-direction: column;
    }

    .command-hero-stats {
        align-self: stretch;
    }

    .kpis {
        grid-template-columns:
            repeat(2,1fr);
    }

    .two {
        grid-template-columns: 1fr;
    }

    .gridform {
        grid-template-columns: 1fr 1fr;
    }

    .cards {
        grid-template-columns: 1fr;
    }

}


@media (max-width: 650px) {

    .topbar,
    header {
        min-height: 72px;
        padding: 0 16px;
    }

    .page-content,
    section {
        padding: 19px 14px 40px;
    }

    .topbar-actions,
    .actions {
        display: none;
    }

    .command-hero {
        min-height: auto;
        padding: 24px 21px;
    }

    .command-hero h2 {
        font-size: 27px;
    }

    .command-hero-stats {
        grid-template-columns: 1fr 1fr;
        min-width: 0;
    }

    .metric-grid {
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }

    .features,
    .gridform {
        grid-template-columns: 1fr;
    }

    .detailhead {
        align-items: flex-start;
        flex-direction: column;
    }

}


@media (max-width: 430px) {

    .metric-grid {
        grid-template-columns: 1fr;
    }

    .command-hero-stats {
        grid-template-columns: 1fr;
    }

}
'''


new_app_text = dashboard_pattern.sub(
    NEW_DASHBOARD_ROUTE,
    app_text,
    count=1,
)


try:
    APP_FILE.write_text(
        new_app_text,
        encoding="utf-8",
    )

    BASE_FILE.write_text(
        NEW_BASE,
        encoding="utf-8",
    )

    DASHBOARD_FILE.write_text(
        NEW_DASHBOARD,
        encoding="utf-8",
    )

    STYLES_FILE.write_text(
        NEW_STYLES,
        encoding="utf-8",
    )

    py_compile.compile(
        str(APP_FILE),
        doraise=True,
    )

    try:
        from jinja2 import (
            Environment,
            FileSystemLoader,
        )

        env = Environment(
            loader=FileSystemLoader(
                str(
                    ROOT
                    / "templates"
                )
            )
        )

        env.get_template(
            "base.html"
        )

        env.get_template(
            "dashboard.html"
        )

    except Exception as exc:
        raise RuntimeError(
            "Template validation failed: "
            + str(exc)
        )

except Exception as exc:

    print()
    print("UPGRADE FAILED.")
    print("Restoring original files...")
    print()

    for file in files:
        backup = (
            backup_dir
            / file.relative_to(ROOT)
        )

        shutil.copy2(
            backup,
            file,
        )

    raise SystemExit(
        f"Original files restored.\n\n"
        f"Error: {exc}"
    )


print()
print("======================================")
print(" UPGRADE COMPLETE")
print("======================================")
print()
print("Updated:")
print("  app.py")
print("  templates/base.html")
print("  templates/dashboard.html")
print("  static/styles.css")
print()
print("Python validation: PASS")
print("Template validation: PASS")
print()
print("Next:")
print("  1. Refresh the dashboard")
print("  2. Test sidebar navigation")
print("  3. Open Leads")
print("  4. Open a lead")
print()
print("Do NOT delete this script until")
print("the browser test passes.")
print()