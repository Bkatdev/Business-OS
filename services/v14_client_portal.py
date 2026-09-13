"""Single-tenant owner read model for Business OS.

The portal is deliberately read-only until production authentication and provider
permissions are enabled. Every query is tenant-scoped by business_id.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from services.business_config import configuration_view
from services.v14_delivery import list_releases, active_release_for_business

OWNER_TABS = ("today", "leads", "calls", "schedule", "website", "settings")


def _rows(conn, sql, args=()):
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def _count(conn, sql, args=()):
    return int(conn.execute(sql, args).fetchone()[0])


def _status_count(conn, bid, status):
    return _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=? AND status=?", (bid, status))


def portal_view(conn, bid: int, tab: str = "today") -> dict:
    """Build a safe, tenant-scoped owner experience for one client."""
    tab = (tab or "today").strip().lower()
    if tab not in OWNER_TABS:
        tab = "today"

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=? AND status='Client'", (bid,)
    ).fetchone()
    if business is None:
        raise LookupError("Client not found")

    leads = _rows(conn, "SELECT * FROM leads WHERE business_id=? ORDER BY id DESC LIMIT 50", (bid,))
    calls = _rows(conn, "SELECT * FROM calls WHERE business_id=? ORDER BY id DESC LIMIT 50", (bid,))
    appointments = _rows(
        conn,
        "SELECT a.*, l.caller_name, l.phone FROM appointments a "
        "LEFT JOIN leads l ON l.id=a.lead_id AND l.business_id=a.business_id "
        "WHERE a.business_id=? ORDER BY a.start_at ASC, a.id DESC LIMIT 50",
        (bid,),
    )
    attention = _rows(
        conn,
        "SELECT * FROM quarantine_items WHERE business_id=? AND status='Open' ORDER BY id DESC LIMIT 20",
        (bid,),
    )

    releases = list_releases(conn, bid)
    active_release = active_release_for_business(conn, bid)
    config = configuration_view(conn, bid)

    total = _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,))
    open_leads = _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=? AND status NOT IN ('Won','Lost')", (bid,))
    won = _status_count(conn, bid, "Won")
    lost = _status_count(conn, bid, "Lost")
    closed = won + lost
    conversion_rate = round((won / closed) * 100) if closed else 0
    website_leads = _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=? AND lower(source)='website'", (bid,))
    contacted = _status_count(conn, bid, "Contacted")
    estimate_scheduled = _status_count(conn, bid, "Estimate Scheduled")
    needs_you = _count(conn, "SELECT COUNT(*) FROM quarantine_items WHERE business_id=? AND status='Open'", (bid,))

    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    leads_this_month = _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=? AND created_at>=?", (bid, month_start))

    metrics = {
        "leads": total,
        "open_leads": open_leads,
        "won": won,
        "conversion_rate": conversion_rate,
        "website_leads": website_leads,
        "leads_this_month": leads_this_month,
        "contacted": contacted,
        "estimate_scheduled": estimate_scheduled,
        "calls": _count(conn, "SELECT COUNT(*) FROM calls WHERE business_id=?", (bid,)),
        "appointments": _count(conn, "SELECT COUNT(*) FROM appointments WHERE business_id=?", (bid,)),
        "needs_you": needs_you,
    }

    pipeline = [
        {"label": "New", "count": _status_count(conn, bid, "New")},
        {"label": "Contacted", "count": contacted},
        {"label": "Estimate", "count": estimate_scheduled},
        {"label": "Won", "count": won},
    ]
    pipeline_max = max([item["count"] for item in pipeline] + [1])

    return {
        "tab": tab,
        "tabs": OWNER_TABS,
        "business": dict(business),
        "leads": leads,
        "calls": calls,
        "appointments": appointments,
        "attention": attention,
        "releases": releases,
        "active_release": active_release,
        "config": config,
        "metrics": metrics,
        "pipeline": pipeline,
        "pipeline_max": pipeline_max,
    }
