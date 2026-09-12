"""Business OS v14 - Founder Command Center read model.

Founder HQ prioritizes real revenue work from prospect, audit, concept, sales,
and follow-up state. Unknowns remain unknown and live actions remain locked.
"""
from __future__ import annotations

from datetime import datetime

from services.platform_foundation import usage_summary
from services.scoring import opportunity_analysis
from services.v13_sales import build_sales_brief
from services.v14_sales_workspace import ensure_sales_schema, sales_pipeline_metrics


def _next_action(business: dict, concept_count: int, followup: dict | None) -> tuple[str, str, int]:
    audit_status = str(business.get("audit_status") or "not_audited")
    status = str(business.get("status") or "Not Contacted")
    now_key = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if followup and str(followup.get("due_at") or "") <= now_key:
        return "Follow up now", "sales", 40
    if status in {"Contacted", "Demo", "Proposal"}:
        return "Advance conversation", "sales", 25
    if audit_status != "completed":
        return "Audit website", "audit", 0
    if concept_count <= 0:
        return "Build private concept", "concept", 5
    if status in {"Not Contacted", "Researching", "Qualified"}:
        return "Prepare owner outreach", "sales", 15
    return "Review prospect", "sales", 0


def build_founder_command(conn, *, limit: int = 12):
    ensure_sales_schema(conn)
    rows = conn.execute(
        """
        SELECT b.*,
               (SELECT COUNT(*) FROM website_concepts wc WHERE wc.business_id=b.id) AS concept_count
        FROM businesses b
        WHERE COALESCE(b.lifecycle_stage,'PROSPECT') != 'ACTIVE'
          AND COALESCE(b.status,'Not Contacted') NOT IN ('Client','Lost')
        ORDER BY b.id DESC
        """
    ).fetchall()

    prospects = []
    for row in rows:
        business = dict(row)
        analysis = opportunity_analysis(row)
        sales = build_sales_brief(row)
        concept_count = int(business.get("concept_count") or 0)
        followup_row = conn.execute(
            """
            SELECT * FROM sales_followups
            WHERE business_id=? AND status='OPEN'
            ORDER BY due_at ASC, id ASC LIMIT 1
            """,
            (business["id"],),
        ).fetchone()
        followup = dict(followup_row) if followup_row else None
        next_action, action_kind, urgency_bonus = _next_action(business, concept_count, followup)
        score = analysis.get("score")
        rank_score = int(score if score is not None else -1) + urgency_bonus
        if concept_count:
            rank_score += 8
        prospects.append(
            {
                "business": business,
                "analysis": analysis,
                "sales": sales,
                "concept_count": concept_count,
                "followup": followup,
                "next_action": next_action,
                "action_kind": action_kind,
                "rank_score": rank_score,
            }
        )

    prospects.sort(
        key=lambda item: (item["rank_score"], item["business"]["id"]),
        reverse=True,
    )
    pipeline = sales_pipeline_metrics(conn)

    return {
        "metrics": {
            "prospects": len(rows),
            "audited": sum(1 for r in rows if str(r["audit_status"] or "") == "completed"),
            "high_opportunity": sum(1 for p in prospects if p["analysis"].get("level") == "High"),
            "with_concepts": sum(1 for p in prospects if p["concept_count"] > 0),
            **pipeline,
        },
        "queue": prospects[: max(1, int(limit))],
        "usage": usage_summary(conn),
        "principles": {
            "publishing_locked": True,
            "live_actions_locked": True,
            "costs_measured_not_guessed": True,
        },
    }
