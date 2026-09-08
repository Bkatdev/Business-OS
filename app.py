import csv
import io
import json

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services.db import connect, init_db, now_iso
from services.prospect_finder import discover
from services.scoring import opportunity_analysis
from services.website_auditor import audit_batch, audit_business_by_id


app = Flask(__name__)
app.secret_key = "business-os-local-v2"


STATUSES = [
    "Not Contacted",
    "Researching",
    "Qualified",
    "Contacted",
    "Demo",
    "Proposal",
    "Client",
    "Lost",
]


def analyze(business):
    return opportunity_analysis(business)


def businesses_with_analysis(rows):
    results = []

    for row in rows:
        business = dict(row)
        business["analysis"] = analyze(row)
        results.append(business)

    return results


@app.context_processor
def inject_global_counts():
    conn = connect()

    prospect_count = conn.execute(
        "SELECT COUNT(*) FROM businesses"
    ).fetchone()[0]

    pending_approvals = conn.execute(
        """
        SELECT COUNT(*)
        FROM approvals
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    conn.close()

    return {
        "global_prospect_count": prospect_count,
        "global_pending_approvals": pending_approvals,
    }


@app.route("/")
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

    conn.close()

    businesses = businesses_with_analysis(rows)

    high_opportunity = sum(
        1
        for business in businesses
        if business["analysis"]["level"] == "High"
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
    )


@app.route("/prospects")
def prospects():
    search = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    status = request.args.get("status", "").strip()
    audit = request.args.get("audit", "").strip()

    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    if search:
        search_lower = search.lower()

        businesses = [
            business
            for business in businesses
            if search_lower in (business["name"] or "").lower()
            or search_lower in (business["city"] or "").lower()
            or search_lower in (business["category"] or "").lower()
        ]

    if level:
        businesses = [
            business
            for business in businesses
            if business["analysis"]["level"] == level
        ]

    if status:
        businesses = [
            business
            for business in businesses
            if business["status"] == status
        ]

    if audit:
        businesses = [
            business
            for business in businesses
            if business["audit_status"] == audit
        ]

    return render_template(
        "prospects.html",
        businesses=businesses,
        q=search,
        level=level,
        status=status,
        audit=audit,
        statuses=STATUSES,
        pipeline_statuses=STATUSES,
    )


@app.route("/prospects/discover", methods=["POST"])
def discover_prospects():
    query = request.form.get("query", "").strip()
    category = request.form.get(
        "category",
        "Local Service Business",
    ).strip()

    page_size = request.form.get("page_size", "10")

    if not query:
        flash(
            "Enter a business search first.",
            "error",
        )
        return redirect(url_for("prospects"))

    try:
        result = discover(
            query,
            page_size,
            category,
        )

        flash(
            f"Google returned {result['returned']} businesses. "
            f"Added {len(result['added'])}. "
            f"Skipped {len(result['skipped'])} duplicates.",
            "success",
        )

    except Exception as exc:
        flash(
            f"Prospect discovery failed: {exc}",
            "error",
        )

    return redirect(url_for("prospects"))


@app.route("/prospects/add", methods=["POST"])
def add_prospect():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()

    if not name or not city:
        flash(
            "Business name and city are required.",
            "error",
        )
        return redirect(url_for("prospects"))

    conn = connect()

    conn.execute(
        """
        INSERT INTO businesses (
            name,
            city,
            category,
            reviews,
            rating,
            website,
            phone,
            email,
            online_booking,
            emergency_service,
            website_chat,
            estimate_form,
            status,
            notes,
            created_at,
            source,
            audit_status
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            0, 0, 0, 0,
            'Not Contacted',
            '',
            ?,
            'manual',
            'not_audited'
        )
        """,
        (
            name,
            city,
            request.form.get(
                "category",
                "Local Service Business",
            ).strip(),
            int(request.form.get("reviews") or 0),
            float(request.form.get("rating") or 0),
            request.form.get("website", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("email", "").strip(),
            now_iso(),
        ),
    )

    conn.commit()
    conn.close()

    flash(
        f"{name} was added.",
        "success",
    )

    return redirect(url_for("prospects"))


@app.route("/business/<int:bid>")
def business_detail(bid):
    conn = connect()

    business = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE id = ?
        """,
        (bid,),
    ).fetchone()

    approvals = conn.execute(
        """
        SELECT *
        FROM approvals
        WHERE business_id = ?
        ORDER BY id DESC
        """,
        (bid,),
    ).fetchall()

    conn.close()

    if business is None:
        return render_template("404.html"), 404

    evidence = {}

    raw_evidence = business["audit_evidence"]

    if raw_evidence:
        try:
            evidence = json.loads(raw_evidence)

        except json.JSONDecodeError:
            evidence = {
                "raw": raw_evidence
            }

    return render_template(
        "business_detail.html",
        business=dict(business),
        analysis=analyze(business),
        evidence=evidence,
        approvals=approvals,
        statuses=STATUSES,
        pipeline_statuses=STATUSES,
    )


@app.route(
    "/business/<int:bid>/audit",
    methods=["POST"],
)
def audit_one(bid):
    try:
        result = audit_business_by_id(bid)

        if result["ok"]:
            flash(
                "Website audit completed successfully.",
                "success",
            )

        else:
            flash(
                "Website audit could not fully complete: "
                + result.get(
                    "message",
                    result.get(
                        "status",
                        "Unknown error",
                    ),
                ),
                "error",
            )

    except Exception as exc:
        flash(
            f"Website audit failed: {exc}",
            "error",
        )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route(
    "/business/<int:bid>/status",
    methods=["POST"],
)
def update_status(bid):
    status = request.form.get(
        "status",
        "Not Contacted",
    )

    if status not in STATUSES:
        status = "Not Contacted"

    conn = connect()

    conn.execute(
        """
        UPDATE businesses
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            bid,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        "Pipeline status updated.",
        "success",
    )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route(
    "/business/<int:bid>/notes",
    methods=["POST"],
)
def update_notes(bid):
    notes = request.form.get(
        "notes",
        "",
    )

    conn = connect()

    conn.execute(
        """
        UPDATE businesses
        SET notes = ?
        WHERE id = ?
        """,
        (
            notes,
            bid,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        "Notes saved.",
        "success",
    )

    return redirect(
        url_for(
            "business_detail",
            bid=bid,
        )
    )


@app.route("/audits")
def audits():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    return render_template(
        "audits.html",
        businesses=businesses,
    )


@app.route(
    "/audits/run",
    methods=["POST"],
)
def run_audits():
    mode = request.form.get(
        "mode",
        "not_audited",
    )

    try:
        results = audit_batch(
            mode=mode,
            limit=25,
        )

        completed = sum(
            1
            for _, _, result in results
            if result["ok"]
        )

        failed = len(results) - completed

        flash(
            f"Audit finished. "
            f"{completed} completed. "
            f"{failed} could not complete.",
            "success",
        )

    except Exception as exc:
        flash(
            f"Audit run failed: {exc}",
            "error",
        )

    return redirect(
        url_for("audits")
    )


@app.route("/agents")
def agents():
    return render_template(
        "agents.html"
    )


@app.route("/approvals")
def approvals():
    conn = connect()

    rows = conn.execute(
        """
        SELECT
            approvals.*,
            businesses.name AS business_name
        FROM approvals
        LEFT JOIN businesses
            ON businesses.id = approvals.business_id
        ORDER BY approvals.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "approvals.html",
        approvals=rows,
    )


@app.route(
    "/approvals/<int:approval_id>/<action>",
    methods=["POST"],
)
def approval_action(
    approval_id,
    action,
):
    if action == "approve":
        status = "Approved"
    else:
        status = "Rejected"

    conn = connect()

    conn.execute(
        """
        UPDATE approvals
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            approval_id,
        ),
    )

    conn.commit()
    conn.close()

    flash(
        f"Approval marked {status.lower()}.",
        "success",
    )

    return redirect(
        url_for("approvals")
    )


@app.route("/clients")
def clients():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        WHERE status = 'Client'
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    businesses = businesses_with_analysis(rows)

    return render_template(
        "clients.html",
        businesses=businesses,
    )


@app.route("/prospects/export")
def export_prospects():
    conn = connect()

    rows = conn.execute(
        """
        SELECT *
        FROM businesses
        ORDER BY id
        """
    ).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    headers = [
        "name",
        "city",
        "category",
        "reviews",
        "rating",
        "website",
        "phone",
        "email",
        "status",
        "address",
        "source",
        "audit_status",
    ]

    writer.writerow(headers)

    for row in rows:
        writer.writerow(
            [
                row[header]
                if header in row.keys()
                else ""
                for header in headers
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=business_os_prospects.csv"
        },
    )


@app.route(
    "/prospects/import",
    methods=["POST"],
)
def import_prospects():
    upload = request.files.get("file")

    if not upload or not upload.filename:
        flash(
            "Choose a CSV file first.",
            "error",
        )
        return redirect(
            url_for("prospects")
        )

    text = upload.stream.read().decode(
        "utf-8-sig"
    )

    reader = csv.DictReader(
        io.StringIO(text)
    )

    conn = connect()

    added = 0
    skipped = 0

    for row in reader:
        name = (
            row.get("name")
            or ""
        ).strip()

        city = (
            row.get("city")
            or ""
        ).strip()

        if not name or not city:
            skipped += 1
            continue

        website = (
            row.get("website")
            or ""
        ).strip()

        phone = (
            row.get("phone")
            or ""
        ).strip()

        duplicate = conn.execute(
            """
            SELECT id
            FROM businesses
            WHERE LOWER(name) = LOWER(?)
              AND (
                (phone != '' AND phone = ?)
                OR
                (
                    website != ''
                    AND LOWER(website) = LOWER(?)
                )
                OR
                LOWER(city) = LOWER(?)
              )
            LIMIT 1
            """,
            (
                name,
                phone,
                website,
                city,
            ),
        ).fetchone()

        if duplicate:
            skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO businesses (
                name,
                city,
                category,
                reviews,
                rating,
                website,
                phone,
                email,
                online_booking,
                emergency_service,
                website_chat,
                estimate_form,
                status,
                notes,
                created_at,
                address,
                source,
                audit_status
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                0, 0, 0, 0,
                ?, '',
                ?, ?,
                'csv',
                'not_audited'
            )
            """,
            (
                name,
                city,
                (
                    row.get("category")
                    or "Local Service Business"
                ).strip(),
                int(
                    float(
                        row.get("reviews")
                        or 0
                    )
                ),
                float(
                    row.get("rating")
                    or 0
                ),
                website,
                phone,
                (
                    row.get("email")
                    or ""
                ).strip(),
                (
                    row.get("status")
                    or "Not Contacted"
                ).strip(),
                now_iso(),
                (
                    row.get("address")
                    or ""
                ).strip(),
            ),
        )

        added += 1

    conn.commit()
    conn.close()

    flash(
        f"CSV import complete. "
        f"{added} added. "
        f"{skipped} skipped.",
        "success",
    )

    return redirect(
        url_for("prospects")
    )


@app.errorhandler(404)
def page_not_found(error):
    return (
        render_template("404.html"),
        404,
    )


if __name__ == "__main__":
    init_db()

    app.run(
        debug=True
    )