"""Single-tenant owner read model for Business OS v14.

This is deliberately read-only. Production client authentication is a separate
security boundary and remains disabled until it is implemented and verified.
Every query is tenant-scoped by business_id.
"""
from __future__ import annotations

from services.business_config import configuration_view
from services.v14_delivery import list_releases, active_release_for_business

OWNER_TABS = ("today", "leads", "calls", "schedule", "website", "settings")


def _rows(conn, sql, args=()):
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def _count(conn, sql, args=()):
    return int(conn.execute(sql, args).fetchone()[0])


def portal_view(conn, bid: int, tab: str = "today") -> dict:
    """Build a tenant-scoped owner experience for one client.

    Unknown tabs fail closed to Today rather than creating ad-hoc behavior.
    """
    tab = (tab or "today").strip().lower()
    if tab not in OWNER_TABS:
        tab = "today"

    business = conn.execute(
        "SELECT * FROM businesses WHERE id=? AND status='Client'", (bid,)
    ).fetchone()
    if business is None:
        raise LookupError("Client not found")

    leads = _rows(
        conn,
        "SELECT * FROM leads WHERE business_id=? ORDER BY id DESC LIMIT 50",
        (bid,),
    )
    calls = _rows(
        conn,
        "SELECT * FROM calls WHERE business_id=? ORDER BY id DESC LIMIT 50",
        (bid,),
    )
    appointments = _rows(
        conn,
        "SELECT a.*, l.caller_name, l.phone FROM appointments a "
        "LEFT JOIN leads l ON l.id=a.lead_id AND l.business_id=a.business_id "
        "WHERE a.business_id=? ORDER BY a.start_at ASC, a.id DESC LIMIT 50",
        (bid,),
    )
    attention = _rows(
        conn,
        "SELECT * FROM quarantine_items WHERE business_id=? AND status='Open' "
        "ORDER BY id DESC LIMIT 20",
        (bid,),
    )

    releases = list_releases(conn, bid)
    active_release = active_release_for_business(conn, bid)
    config = configuration_view(conn, bid)

    metrics = {
        "leads": _count(conn, "SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,)),
        "calls": _count(conn, "SELECT COUNT(*) FROM calls WHERE business_id=?", (bid,)),
        "appointments": _count(conn, "SELECT COUNT(*) FROM appointments WHERE business_id=?", (bid,)),
        "needs_you": _count(
            conn,
            "SELECT COUNT(*) FROM quarantine_items WHERE business_id=? AND status='Open'",
            (bid,),
        ),
    }

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
    }
