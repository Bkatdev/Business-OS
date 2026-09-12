"""Read-only founder acceptance lab for exercising Business OS from three personas."""
from __future__ import annotations

from services.v14_client_experience import client_workspace_state
from services.v14_delivery import delivery_dashboard, active_release_for_business
from services.v14_production_site import selected_design


def acceptance_state(conn, business_id: int) -> dict:
    business = conn.execute(
        "SELECT * FROM businesses WHERE id=? AND status='Client'", (business_id,)
    ).fetchone()
    if business is None:
        raise LookupError("Client not found")

    workspace = client_workspace_state(conn, business_id)
    delivery = delivery_dashboard(conn, business_id)
    design = selected_design(conn, business_id)
    active_release = active_release_for_business(conn, business_id)
    latest_lead = conn.execute(
        "SELECT * FROM leads WHERE business_id=? ORDER BY id DESC LIMIT 1", (business_id,)
    ).fetchone()

    checks = [
        {
            "key": "reviewed_preview",
            "label": "Reviewed website preview selected",
            "ok": bool(workspace["has_reviewed_preview"]),
            "next": "website",
        },
        {
            "key": "production_design",
            "label": "Production design matches reviewed truth",
            "ok": workspace["design_state"] == "ready",
            "next": "design",
        },
        {
            "key": "local_release",
            "label": "Local customer test site is active",
            "ok": bool(active_release),
            "next": "delivery",
        },
    ]

    return {
        "business": dict(business),
        "workspace": workspace,
        "delivery": delivery,
        "design": design,
        "active_release": active_release,
        "latest_lead": dict(latest_lead) if latest_lead else None,
        "checks": checks,
        "ready_for_full_journey": all(item["ok"] for item in checks),
    }
