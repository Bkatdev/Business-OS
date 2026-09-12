"""Stable operator/client experience helpers for the v14 modular monolith.

This module intentionally owns read/navigation state only. It does not authorize
live provider actions and it does not implement production client authentication.
"""
from services.v14_client_portal import portal_view
from services.v14_production_site import selected_design
from services.website_versions import get_preview_version


def client_workspace_state(conn, business_id):
    business = conn.execute(
        "SELECT * FROM businesses WHERE id=? AND status='Client'", (business_id,)
    ).fetchone()
    if business is None:
        raise LookupError("Client not found")

    preview = get_preview_version(conn, business_id)
    design = selected_design(conn, business_id)
    design_state = "missing"
    if design and preview:
        design_state = (
            "ready"
            if int(design["website_version_id"]) == int(preview["id"])
            else "stale"
        )

    return {
        "business": dict(business),
        "has_reviewed_preview": bool(preview),
        "reviewed_preview_version": preview["version_number"] if preview else None,
        "design_state": design_state,
        "owner_preview_available": True,
    }


def owner_preview_state(conn, business_id, tab="today"):
    """Return a safe owner-preview read model plus explicit recovery metadata."""
    portal = portal_view(conn, business_id, tab=tab)
    workspace = client_workspace_state(conn, business_id)
    portal["workspace"] = workspace
    return portal
