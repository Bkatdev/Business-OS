from pathlib import Path
import shutil
import tempfile

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parent

BASE_FILE = ROOT / "templates" / "base.html"
LEADS_FILE = ROOT / "templates" / "leads.html"
CALLS_FILE = ROOT / "templates" / "calls.html"
JS_FILE = ROOT / "static" / "app.js"
CSS_FILE = ROOT / "static" / "styles.css"

FILES = [
    BASE_FILE,
    LEADS_FILE,
    CALLS_FILE,
    JS_FILE,
    CSS_FILE,
]


print()
print("======================================")
print(" BUSINESS OS OPERATIONS UPGRADE")
print("======================================")
print()


for file in FILES:
    if not file.exists():
        raise SystemExit(
            f"STOPPED: Missing required file:\n{file}"
        )


backup_dir = Path(
    tempfile.mkdtemp(
        prefix="business_os_operations_"
    )
)


for file in FILES:
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

            <button
                class="sidebar-toggle"
                type="button"
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
                data-sidebar-toggle
            >
                ‹
            </button>

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
                title="Dashboard"
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
                title="Leads"
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
                title="Calls"
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
                title="Prospects"
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
                title="Audits"
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
                title="Agents"
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
                title="Approvals"
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
                title="Clients"
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


NEW_LEADS = r'''{% extends "base.html" %}

{% block title %}
Business OS · Leads
{% endblock %}

{% block heading %}
Leads
{% endblock %}


{% block actions %}

<a
    class="btn secondary"
    href="{{ url_for('calls') }}"
>
    View Calls
</a>

{% endblock %}


{% block content %}

<div class="operations-hero">

    <div>

        <span class="section-kicker">
            FRONT OFFICE
        </span>

        <h2>
            Lead Command Center
        </h2>

        <p>
            Review every inbound opportunity,
            find the leads that need attention,
            and move work through the pipeline.
        </p>

    </div>


    <div class="operations-count">

        <span>
            Total leads
        </span>

        <strong>
            {{ leads|length }}
        </strong>

    </div>

</div>


<div class="operations-toolbar">

    <div class="search-box">

        <span class="search-icon">
            ⌕
        </span>

        <input
            type="search"
            placeholder="Search name, phone, service, address..."
            autocomplete="off"
            data-lead-search
        >

    </div>


    <select data-lead-status>

        <option value="">
            All statuses
        </option>

        <option value="new">
            New
        </option>

        <option value="contacted">
            Contacted
        </option>

        <option value="estimate scheduled">
            Estimate Scheduled
        </option>

        <option value="won">
            Won
        </option>

        <option value="lost">
            Lost
        </option>

    </select>


    <select data-lead-priority>

        <option value="">
            All priorities
        </option>

        <option value="urgent">
            Urgent
        </option>

        <option value="normal">
            Normal
        </option>

    </select>


    <button
        type="button"
        class="filter-reset"
        data-lead-reset
    >
        Clear
    </button>

</div>


<div class="results-summary">

    <span>
        Showing
        <strong data-lead-count>
            {{ leads|length }}
        </strong>
        lead<span data-lead-plural>
            {% if leads|length != 1 %}s{% endif %}
        </span>
    </span>

</div>


<div class="operations-panel">

{% if leads %}

    <div class="operations-table-wrap">

        <table class="operations-table">

            <thead>

                <tr>
                    <th>Customer</th>
                    <th>Service</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Appointment</th>
                    <th>Source</th>
                    <th>Created</th>
                    <th></th>
                </tr>

            </thead>


            <tbody>

            {% for lead in leads %}

                <tr
                    class="clickable-row
                    {% if lead['priority'] == 'Urgent' %}
                        urgent-row
                    {% endif %}"
                    data-lead-row
                    data-href="{{ url_for(
                        'lead_detail',
                        lead_id=lead['id']
                    ) }}"
                    data-status="{{
                        (lead['status'] or 'New')
                        | lower
                    }}"
                    data-priority="{{
                        (lead['priority'] or 'Normal')
                        | lower
                    }}"
                    data-search="{{
                        lead['caller_name'] or ''
                    }} {{
                        lead['phone'] or ''
                    }} {{
                        lead['service_type'] or ''
                    }} {{
                        lead['address'] or ''
                    }} {{
                        lead['source'] or ''
                    }}"
                >

                    <td>

                        <div class="customer-cell">

                            <div class="customer-avatar">

                                {{
                                    (
                                        lead["caller_name"]
                                        or "?"
                                    )[0]
                                    | upper
                                }}

                            </div>


                            <div>

                                <a
                                    class="customer-name"
                                    href="{{ url_for(
                                        'lead_detail',
                                        lead_id=lead['id']
                                    ) }}"
                                >
                                    {{
                                        lead["caller_name"]
                                        or "Unknown Caller"
                                    }}
                                </a>

                                <span>
                                    {{
                                        lead["phone"]
                                        or "No phone provided"
                                    }}
                                </span>

                            </div>

                        </div>

                    </td>


                    <td>

                        <strong class="table-primary">
                            {{
                                lead["service_type"]
                                or "Not specified"
                            }}
                        </strong>

                        <span class="table-secondary">
                            {{
                                lead["lead_type"]
                                or "New Lead"
                            }}
                        </span>

                    </td>


                    <td>

                        {% if lead["priority"] == "Urgent" %}

                        <span class="ops-pill urgent">
                            <span class="pill-dot"></span>
                            Urgent
                        </span>

                        {% else %}

                        <span class="ops-pill normal">
                            Normal
                        </span>

                        {% endif %}

                    </td>


                    <td>

                        <span class="ops-pill status-{{
                            (lead['status'] or 'New')
                            | lower
                            | replace(' ', '-')
                        }}">
                            {{
                                lead["status"]
                                or "New"
                            }}
                        </span>

                    </td>


                    <td>

                        {% if lead["appointment_status"] == "Scheduled" %}

                        <span class="appointment-state scheduled">
                            ✓ Scheduled
                        </span>

                        {% else %}

                        <span class="appointment-state">
                            Not scheduled
                        </span>

                        {% endif %}

                    </td>


                    <td>

                        <span class="source-label">
                            {{
                                lead["source"]
                                or "Unknown"
                            }}
                        </span>

                    </td>


                    <td>

                        <span class="created-value">
                            {{ lead["created_at"] }}
                        </span>

                    </td>


                    <td class="row-action">
                        →
                    </td>

                </tr>

            {% endfor %}

            </tbody>

        </table>

    </div>


    <div
        class="filtered-empty"
        data-lead-empty
        hidden
    >

        <div class="empty-icon">
            ⌕
        </div>

        <h3>
            No matching leads
        </h3>

        <p>
            Change or clear your filters.
        </p>

    </div>


{% else %}

    <div class="operations-empty">

        <div class="empty-icon">
            ◎
        </div>

        <h3>
            No leads yet
        </h3>

        <p>
            Leads captured by the AI receptionist
            will automatically appear here.
        </p>

    </div>

{% endif %}

</div>

{% endblock %}
'''


NEW_CALLS = r'''{% extends "base.html" %}

{% block title %}
Business OS · Calls
{% endblock %}

{% block heading %}
Calls
{% endblock %}


{% block actions %}

<a
    class="btn secondary"
    href="{{ url_for('leads') }}"
>
    View Leads
</a>

{% endblock %}


{% block content %}

<div class="operations-hero">

    <div>

        <span class="section-kicker">
            AI RECEPTIONIST
        </span>

        <h2>
            Call Intelligence
        </h2>

        <p>
            Review inbound conversations,
            call outcomes, summaries, and
            the leads created from them.
        </p>

    </div>


    <div class="operations-count">

        <span>
            Recorded calls
        </span>

        <strong>
            {{ calls|length }}
        </strong>

    </div>

</div>


<div class="operations-toolbar">

    <div class="search-box">

        <span class="search-icon">
            ⌕
        </span>

        <input
            type="search"
            placeholder="Search caller, phone, summary..."
            autocomplete="off"
            data-call-search
        >

    </div>


    <select data-call-status>

        <option value="">
            All call statuses
        </option>

        <option value="completed">
            Completed
        </option>

    </select>


    <button
        type="button"
        class="filter-reset"
        data-call-reset
    >
        Clear
    </button>

</div>


<div class="results-summary">

    <span>
        Showing
        <strong data-call-count>
            {{ calls|length }}
        </strong>
        call<span data-call-plural>
            {% if calls|length != 1 %}s{% endif %}
        </span>
    </span>

</div>


<div class="operations-panel">

{% if calls %}

    <div class="operations-table-wrap">

        <table class="operations-table calls-table">

            <thead>

                <tr>
                    <th>Caller</th>
                    <th>Summary</th>
                    <th>Business</th>
                    <th>Duration</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th></th>
                </tr>

            </thead>


            <tbody>

            {% for call in calls %}

                <tr
                    class="
                    {% if call['lead_id'] %}
                        clickable-row
                    {% endif %}
                    "
                    data-call-row
                    {% if call["lead_id"] %}
                    data-href="{{ url_for(
                        'lead_detail',
                        lead_id=call['lead_id']
                    ) }}"
                    {% endif %}
                    data-status="{{
                        (call['call_status'] or '')
                        | lower
                    }}"
                    data-search="{{
                        call['caller_name'] or ''
                    }} {{
                        call['caller_phone'] or ''
                    }} {{
                        call['summary'] or ''
                    }} {{
                        call['business_name'] or ''
                    }}"
                >

                    <td>

                        <div class="customer-cell">

                            <div class="customer-avatar call-avatar">
                                ☎
                            </div>


                            <div>

                                {% if call["lead_id"] %}

                                <a
                                    class="customer-name"
                                    href="{{ url_for(
                                        'lead_detail',
                                        lead_id=call['lead_id']
                                    ) }}"
                                >
                                    {{
                                        call["caller_name"]
                                        or "Unknown Caller"
                                    }}
                                </a>

                                {% else %}

                                <strong class="customer-name">
                                    {{
                                        call["caller_name"]
                                        or "Unknown Caller"
                                    }}
                                </strong>

                                {% endif %}

                                <span>
                                    {{
                                        call["caller_phone"]
                                        or "No phone provided"
                                    }}
                                </span>

                            </div>

                        </div>

                    </td>


                    <td>

                        <div class="summary-preview">

                            {{
                                call["summary"]
                                or "No call summary available."
                            }}

                        </div>

                    </td>


                    <td>

                        <span class="source-label">
                            {{
                                call["business_name"]
                                or "Demo / Unassigned"
                            }}
                        </span>

                    </td>


                    <td>

                        {% set seconds =
                            call["duration_seconds"] or 0
                        %}

                        <span class="duration-value">

                            {% if seconds >= 60 %}

                                {{
                                    seconds // 60
                                }}m
                                {{
                                    seconds % 60
                                }}s

                            {% else %}

                                {{ seconds }}s

                            {% endif %}

                        </span>

                    </td>


                    <td>

                        <span class="ops-pill completed">
                            <span class="pill-dot"></span>

                            {{
                                call["call_status"]
                                or "Completed"
                            }}
                        </span>

                    </td>


                    <td>

                        <span class="created-value">
                            {{ call["created_at"] }}
                        </span>

                    </td>


                    <td class="row-action">

                        {% if call["lead_id"] %}
                            →
                        {% endif %}

                    </td>

                </tr>

            {% endfor %}

            </tbody>

        </table>

    </div>


    <div
        class="filtered-empty"
        data-call-empty
        hidden
    >

        <div class="empty-icon">
            ⌕
        </div>

        <h3>
            No matching calls
        </h3>

        <p>
            Change or clear your filters.
        </p>

    </div>


{% else %}

    <div class="operations-empty">

        <div class="empty-icon">
            ☎
        </div>

        <h3>
            No calls yet
        </h3>

        <p>
            Completed AI receptionist calls
            will appear here automatically.
        </p>

    </div>

{% endif %}

</div>

{% endblock %}
'''


NEW_JS = r'''// Business OS browser interactions.
// Server actions remain explicit and backend-controlled.

document.addEventListener("DOMContentLoaded", () => {

    setupSidebar();
    setupClickableRows();
    setupLeadFilters();
    setupCallFilters();

});


function setupSidebar() {

    const toggle = document.querySelector(
        "[data-sidebar-toggle]"
    );

    if (!toggle) {
        return;
    }

    const storageKey =
        "business-os-sidebar-collapsed";

    const saved =
        localStorage.getItem(storageKey);

    if (saved === "true") {
        document.body.classList.add(
            "sidebar-collapsed"
        );
    }


    updateSidebarButton(toggle);


    toggle.addEventListener(
        "click",
        () => {

            const collapsed =
                document.body.classList.toggle(
                    "sidebar-collapsed"
                );

            localStorage.setItem(
                storageKey,
                String(collapsed)
            );

            updateSidebarButton(toggle);

        }
    );

}


function updateSidebarButton(toggle) {

    const collapsed =
        document.body.classList.contains(
            "sidebar-collapsed"
        );

    toggle.textContent =
        collapsed ? "›" : "‹";

    toggle.setAttribute(
        "aria-label",
        collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
    );

    toggle.setAttribute(
        "title",
        collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
    );

}


function setupClickableRows() {

    const rows =
        document.querySelectorAll(
            ".clickable-row[data-href]"
        );

    rows.forEach((row) => {

        row.addEventListener(
            "click",
            (event) => {

                const interactive =
                    event.target.closest(
                        "a, button, input, select, textarea"
                    );

                if (interactive) {
                    return;
                }

                const href =
                    row.dataset.href;

                if (href) {
                    window.location.href =
                        href;
                }

            }
        );

    });

}


function setupLeadFilters() {

    const search =
        document.querySelector(
            "[data-lead-search]"
        );

    const status =
        document.querySelector(
            "[data-lead-status]"
        );

    const priority =
        document.querySelector(
            "[data-lead-priority]"
        );

    const reset =
        document.querySelector(
            "[data-lead-reset]"
        );

    const rows = [
        ...document.querySelectorAll(
            "[data-lead-row]"
        ),
    ];

    if (
        !search
        || !status
        || !priority
        || rows.length === 0
    ) {
        return;
    }


    const apply = () => {

        const query =
            search.value
                .trim()
                .toLowerCase();

        const wantedStatus =
            status.value
                .trim()
                .toLowerCase();

        const wantedPriority =
            priority.value
                .trim()
                .toLowerCase();


        let visible = 0;


        rows.forEach((row) => {

            const searchText =
                (
                    row.dataset.search
                    || ""
                ).toLowerCase();

            const rowStatus =
                (
                    row.dataset.status
                    || ""
                ).toLowerCase();

            const rowPriority =
                (
                    row.dataset.priority
                    || ""
                ).toLowerCase();


            const searchMatch =
                !query
                || searchText.includes(
                    query
                );

            const statusMatch =
                !wantedStatus
                || rowStatus ===
                    wantedStatus;

            const priorityMatch =
                !wantedPriority
                || rowPriority ===
                    wantedPriority;


            const show =
                searchMatch
                && statusMatch
                && priorityMatch;


            row.hidden = !show;


            if (show) {
                visible += 1;
            }

        });


        updateCount(
            "[data-lead-count]",
            "[data-lead-plural]",
            visible
        );


        const empty =
            document.querySelector(
                "[data-lead-empty]"
            );

        if (empty) {
            empty.hidden =
                visible !== 0;
        }

    };


    search.addEventListener(
        "input",
        apply
    );

    status.addEventListener(
        "change",
        apply
    );

    priority.addEventListener(
        "change",
        apply
    );


    if (reset) {

        reset.addEventListener(
            "click",
            () => {

                search.value = "";
                status.value = "";
                priority.value = "";

                apply();

                search.focus();

            }
        );

    }


    apply();

}


function setupCallFilters() {

    const search =
        document.querySelector(
            "[data-call-search]"
        );

    const status =
        document.querySelector(
            "[data-call-status]"
        );

    const reset =
        document.querySelector(
            "[data-call-reset]"
        );

    const rows = [
        ...document.querySelectorAll(
            "[data-call-row]"
        ),
    ];


    if (
        !search
        || !status
        || rows.length === 0
    ) {
        return;
    }


    const apply = () => {

        const query =
            search.value
                .trim()
                .toLowerCase();

        const wantedStatus =
            status.value
                .trim()
                .toLowerCase();

        let visible = 0;


        rows.forEach((row) => {

            const searchText =
                (
                    row.dataset.search
                    || ""
                ).toLowerCase();

            const rowStatus =
                (
                    row.dataset.status
                    || ""
                ).toLowerCase();


            const searchMatch =
                !query
                || searchText.includes(
                    query
                );

            const statusMatch =
                !wantedStatus
                || rowStatus ===
                    wantedStatus;

            const show =
                searchMatch
                && statusMatch;


            row.hidden = !show;


            if (show) {
                visible += 1;
            }

        });


        updateCount(
            "[data-call-count]",
            "[data-call-plural]",
            visible
        );


        const empty =
            document.querySelector(
                "[data-call-empty]"
            );

        if (empty) {
            empty.hidden =
                visible !== 0;
        }

    };


    search.addEventListener(
        "input",
        apply
    );

    status.addEventListener(
        "change",
        apply
    );


    if (reset) {

        reset.addEventListener(
            "click",
            () => {

                search.value = "";
                status.value = "";

                apply();

                search.focus();

            }
        );

    }


    apply();

}


function updateCount(
    countSelector,
    pluralSelector,
    count
) {

    const countElement =
        document.querySelector(
            countSelector
        );

    const pluralElement =
        document.querySelector(
            pluralSelector
        );


    if (countElement) {
        countElement.textContent =
            String(count);
    }


    if (pluralElement) {
        pluralElement.textContent =
            count === 1 ? "" : "s";
    }

}
'''


CSS_MARKER = """
/* ==========================================
   BUSINESS OS OPERATIONS UPGRADE
   ========================================== */
"""


CSS_ADDITION = r'''

/* ==========================================
   BUSINESS OS OPERATIONS UPGRADE
   ========================================== */


/* SIDEBAR CONTROL */

.sidebar-toggle {
    display: flex;
    align-items: center;
    justify-content: center;

    flex: 0 0 auto;

    width: 27px;
    height: 27px;

    margin-left: auto;

    border: 1px solid rgba(255,255,255,.08);
    border-radius: 8px;

    background: rgba(255,255,255,.035);
    color: #9db1a4;

    cursor: pointer;

    font-size: 19px;
    line-height: 1;

    transition:
        background 120ms ease,
        color 120ms ease,
        border-color 120ms ease;
}


.sidebar-toggle:hover {
    border-color: rgba(255,255,255,.14);
    background: rgba(255,255,255,.07);
    color: white;
}


body.sidebar-collapsed .app-shell,
body.sidebar-collapsed .shell {
    grid-template-columns:
        76px minmax(0, 1fr);
}


body.sidebar-collapsed .sidebar,
body.sidebar-collapsed aside {
    width: 76px;
    padding-left: 10px;
    padding-right: 10px;
}


body.sidebar-collapsed .sidebar-brand {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
}


body.sidebar-collapsed .brand-copy,
body.sidebar-collapsed .sidebar-section-label,
body.sidebar-collapsed .nav-label,
body.sidebar-collapsed .nav-count,
body.sidebar-collapsed .sidebar-footer {
    display: none;
}


body.sidebar-collapsed .sidebar-brand {
    flex-direction: column;
    gap: 7px;
}


body.sidebar-collapsed .sidebar-toggle {
    margin-left: 0;
}


body.sidebar-collapsed .sidebar-nav a,
body.sidebar-collapsed nav a {
    justify-content: center;
    padding-left: 9px;
    padding-right: 9px;
}


body.sidebar-collapsed .nav-icon {
    width: 28px;
    margin-right: 0;
    font-size: 17px;
}


/* OPERATIONS HERO */

.operations-hero {
    display: flex;
    align-items: center;
    justify-content: space-between;

    gap: 28px;

    padding: 23px 25px;
    margin-bottom: 16px;

    border: 1px solid var(--line);
    border-radius: 18px;

    background:
        radial-gradient(
            circle at 92% 0%,
            rgba(32, 131, 84, .08),
            transparent 28%
        ),
        white;

    box-shadow: var(--shadow-xs);
}


.operations-hero h2 {
    margin: 4px 0 7px;

    color: var(--ink);

    font-size: 24px;
    letter-spacing: -.02em;
}


.operations-hero p {
    max-width: 720px;

    margin: 0;

    color: var(--muted);

    font-size: 11px;
    line-height: 1.6;
}


.operations-count {
    flex: 0 0 auto;

    min-width: 110px;

    padding: 13px 17px;

    border: 1px solid #d8e7dc;
    border-radius: 13px;

    background: var(--surface-green);
}


.operations-count span,
.operations-count strong {
    display: block;
}


.operations-count span {
    color: var(--muted);

    font-size: 9px;
    font-weight: 700;
}


.operations-count strong {
    margin-top: 4px;

    color: var(--accent-dark);

    font-size: 28px;
}


/* TOOLBAR */

.operations-toolbar {
    display: grid;
    grid-template-columns:
        minmax(260px, 1fr)
        180px
        170px
        auto;

    gap: 9px;

    margin-bottom: 8px;
}


.search-box {
    position: relative;
}


.search-box input {
    height: 42px;

    padding-left: 37px;

    border-radius: 11px;

    background: white;
}


.search-icon {
    position: absolute;

    top: 50%;
    left: 13px;

    transform: translateY(-50%);

    color: #8b9890;

    pointer-events: none;
}


.operations-toolbar select {
    height: 42px;

    border-radius: 11px;

    background: white;
}


.filter-reset {
    height: 42px;

    padding: 0 14px;

    border: 1px solid var(--line);
    border-radius: 11px;

    background: white;
    color: var(--ink-soft);

    cursor: pointer;

    font-size: 10px;
    font-weight: 800;
}


.filter-reset:hover {
    background: var(--surface-soft);
}


.results-summary {
    min-height: 25px;

    padding: 0 3px;

    color: var(--muted);

    font-size: 9px;
}


.results-summary strong {
    color: var(--ink-soft);
}


/* OPERATIONS TABLE */

.operations-panel {
    overflow: hidden;

    border: 1px solid var(--line);
    border-radius: 17px;

    background: white;

    box-shadow: var(--shadow-xs);
}


.operations-table-wrap {
    width: 100%;
    overflow-x: auto;
}


.operations-table {
    min-width: 1000px;
}


.operations-table th {
    padding-top: 12px;
    padding-bottom: 12px;

    background: #fafcfb;
}


.operations-table td {
    vertical-align: middle;

    padding-top: 14px;
    padding-bottom: 14px;
}


.operations-table tbody tr:last-child td {
    border-bottom: 0;
}


.clickable-row {
    cursor: pointer;
}


.clickable-row:hover {
    background: #f8fbf9;
}


.urgent-row {
    background:
        linear-gradient(
            90deg,
            rgba(182, 66, 66, .035),
            transparent 22%
        );
}


.urgent-row:hover {
    background:
        linear-gradient(
            90deg,
            rgba(182, 66, 66, .065),
            #fbfcfb 30%
        );
}


.customer-cell {
    display: flex;
    align-items: center;

    min-width: 175px;

    gap: 10px;
}


.customer-avatar {
    display: flex;
    align-items: center;
    justify-content: center;

    flex: 0 0 auto;

    width: 34px;
    height: 34px;

    border-radius: 10px;

    background: var(--accent-soft);
    color: var(--accent-dark);

    font-size: 11px;
    font-weight: 900;
}


.call-avatar {
    background: #eef3f0;
    color: #607168;
}


.customer-name {
    display: block;

    max-width: 185px;

    overflow: hidden;

    color: var(--ink);

    font-size: 11px;
    font-weight: 800;

    text-decoration: none;
    text-overflow: ellipsis;
    white-space: nowrap;
}


a.customer-name:hover {
    color: var(--accent);
    text-decoration: underline;
}


.customer-cell > div > span {
    display: block;

    max-width: 185px;

    margin-top: 3px;

    overflow: hidden;

    color: var(--muted);

    font-size: 9px;

    text-overflow: ellipsis;
    white-space: nowrap;
}


.table-primary {
    display: block;

    max-width: 180px;

    overflow: hidden;

    color: var(--ink-soft);

    font-size: 10px;

    text-overflow: ellipsis;
    white-space: nowrap;
}


.table-secondary {
    display: block;

    margin-top: 3px;

    color: var(--muted);

    font-size: 8px;
}


.ops-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;

    padding: 5px 8px;

    border-radius: 999px;

    background: #eef3ef;
    color: #607067;

    font-size: 8px;
    font-weight: 900;

    white-space: nowrap;
}


.ops-pill.urgent {
    border: 1px solid #f0d2d2;

    background: var(--danger-soft);
    color: var(--danger);
}


.ops-pill.normal {
    background: #f0f3f1;
    color: #66746c;
}


.ops-pill.status-new {
    background: #edf5ff;
    color: #386a9d;
}


.ops-pill.status-contacted {
    background: #f5f0ff;
    color: #6e51a5;
}


.ops-pill.status-estimate-scheduled {
    background: #fff7e7;
    color: #93631c;
}


.ops-pill.status-won {
    background: var(--accent-soft);
    color: var(--accent-dark);
}


.ops-pill.status-lost {
    background: #f4f4f4;
    color: #777;
}


.ops-pill.completed {
    background: var(--accent-soft);
    color: var(--accent-dark);
}


.pill-dot {
    width: 5px;
    height: 5px;

    border-radius: 50%;

    background: currentColor;
}


.appointment-state {
    color: var(--muted);

    font-size: 9px;
    white-space: nowrap;
}


.appointment-state.scheduled {
    color: var(--accent);

    font-weight: 800;
}


.source-label,
.created-value,
.duration-value {
    color: var(--muted);

    font-size: 9px;

    white-space: nowrap;
}


.duration-value {
    color: var(--ink-soft);

    font-weight: 800;
}


.row-action {
    width: 32px;

    color: #9aa59e;

    font-size: 13px;
    text-align: right;
}


.summary-preview {
    display: -webkit-box;

    max-width: 320px;

    overflow: hidden;

    color: var(--ink-soft);

    font-size: 9px;
    line-height: 1.45;

    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}


.operations-empty,
.filtered-empty {
    padding: 55px 20px;

    text-align: center;
}


.operations-empty h3,
.filtered-empty h3 {
    margin: 12px 0 5px;

    color: var(--ink);

    font-size: 13px;
}


.operations-empty p,
.filtered-empty p {
    margin: 0;

    color: var(--muted);

    font-size: 10px;
}


[hidden] {
    display: none !important;
}


/* CALLS */

.calls-table {
    min-width: 1050px;
}


/* RESPONSIVE OPERATIONS */

@media (max-width: 1050px) {

    .operations-toolbar {
        grid-template-columns:
            minmax(220px, 1fr)
            160px
            150px
            auto;
    }

}


@media (max-width: 900px) {

    .sidebar-toggle {
        display: none;
    }

    body.sidebar-collapsed .app-shell,
    body.sidebar-collapsed .shell,
    .app-shell,
    .shell {
        grid-template-columns:
            76px minmax(0, 1fr);
    }

    body.sidebar-collapsed .sidebar,
    body.sidebar-collapsed aside,
    .sidebar,
    aside {
        display: flex;
        width: 76px;
        padding: 20px 10px;
    }

    body.sidebar-collapsed .brand-copy,
    body.sidebar-collapsed .sidebar-section-label,
    body.sidebar-collapsed .nav-label,
    body.sidebar-collapsed .nav-count,
    body.sidebar-collapsed .sidebar-footer,
    .brand-copy,
    .sidebar-section-label,
    .nav-label,
    .nav-count,
    .sidebar-footer {
        display: none;
    }

    body.sidebar-collapsed .sidebar-brand,
    .sidebar-brand {
        justify-content: center;
        padding: 3px 0 24px;
    }

    body.sidebar-collapsed .sidebar-nav a,
    body.sidebar-collapsed nav a,
    .sidebar-nav a,
    nav a {
        justify-content: center;
        padding: 9px;
    }

    body.sidebar-collapsed .nav-icon,
    .nav-icon {
        width: 28px;
        margin-right: 0;
        font-size: 17px;
    }

    .operations-toolbar {
        grid-template-columns:
            minmax(220px, 1fr)
            1fr
            1fr;
    }

    .filter-reset {
        grid-column: 3;
    }

}


@media (max-width: 700px) {

    .operations-hero {
        align-items: flex-start;
        flex-direction: column;

        padding: 20px;
    }

    .operations-count {
        width: 100%;
    }

    .operations-toolbar {
        grid-template-columns: 1fr;
    }

    .operations-toolbar select,
    .filter-reset {
        grid-column: auto;
    }

}
'''


try:

    BASE_FILE.write_text(
        NEW_BASE,
        encoding="utf-8",
    )

    LEADS_FILE.write_text(
        NEW_LEADS,
        encoding="utf-8",
    )

    CALLS_FILE.write_text(
        NEW_CALLS,
        encoding="utf-8",
    )

    JS_FILE.write_text(
        NEW_JS,
        encoding="utf-8",
    )


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


    env = Environment(
        loader=FileSystemLoader(
            str(ROOT / "templates")
        )
    )


    env.get_template(
        "base.html"
    )

    env.get_template(
        "leads.html"
    )

    env.get_template(
        "calls.html"
    )


except Exception as exc:

    print()
    print("UPGRADE FAILED.")
    print("Restoring original files...")
    print()

    for file in FILES:

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
print(" OPERATIONS UPGRADE COMPLETE")
print("======================================")
print()
print("Updated:")
print("  templates/base.html")
print("  templates/leads.html")
print("  templates/calls.html")
print("  static/app.js")
print("  static/styles.css")
print()
print("Template validation: PASS")
print()
print("Test these next:")
print("  1. Dashboard")
print("  2. Leads")
print("  3. Lead search")
print("  4. Lead filters")
print("  5. Open a lead")
print("  6. Calls")
print("  7. Call search")
print("  8. Sidebar collapse button")
print()
print("Do not delete this script yet.")
print()