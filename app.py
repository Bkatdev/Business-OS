from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "business-os-local-dev"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "business_os.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Local Service Business',
                reviews INTEGER NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 0,
                website TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                online_booking INTEGER NOT NULL DEFAULT 0,
                emergency_service INTEGER NOT NULL DEFAULT 0,
                website_chat INTEGER NOT NULL DEFAULT 0,
                estimate_form INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Not Contacted',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            );
        """)

        count = db.execute("SELECT COUNT(*) AS count FROM businesses").fetchone()["count"]

        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")
            seed = [
                (
                    "Example Tree Service", "East Brunswick", "Tree Care", 125, 4.8,
                    "https://example.com", "(732) 555-0111", "hello@example.com",
                    0, 1, 0, 0, "Not Contacted",
                    "Strong first-test prospect: emergency intent plus several digital gaps.", now
                ),
                (
                    "Example Landscaping", "Old Bridge", "Landscaping", 65, 4.6,
                    "https://example.com", "(732) 555-0112", "",
                    1, 0, 0, 1, "Researching",
                    "Lower score because online booking and estimate intake already exist.", now
                ),
                (
                    "Example Auto Repair", "Marlboro", "Auto Repair", 210, 4.7,
                    "https://example.com", "(732) 555-0113", "",
                    0, 0, 1, 1, "Qualified",
                    "Established business with strong review volume.", now
                ),
            ]

            db.executemany("""
                INSERT INTO businesses (
                    name, city, category, reviews, rating, website, phone, email,
                    online_booking, emergency_service, website_chat, estimate_form,
                    status, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, seed)

            db.execute("""
                INSERT INTO approvals (business_id, title, description, status, created_at)
                VALUES (1, 'Review outreach draft',
                        'Approve the first outreach message before anything is sent.',
                        'Pending', ?)
            """, (now,))


def analyze_business(row):
    score = 0
    findings = []
    recommendations = []

    if not row["online_booking"]:
        score += 25
        findings.append("No online booking")
        recommendations.append("Add online booking or estimate scheduling")

    if row["emergency_service"]:
        score += 20
        findings.append("Offers emergency/high-intent service")
        recommendations.append("Use an AI receptionist for urgent inbound calls")

    if not row["website_chat"]:
        score += 15
        findings.append("No website chat")
        recommendations.append("Add website lead capture or AI chat")

    if not row["estimate_form"]:
        score += 20
        findings.append("No online estimate/request form")
        recommendations.append("Add an online estimate request workflow")

    if row["reviews"] >= 100:
        score += 20
        findings.append("Established business with 100+ reviews")

    if score >= 70:
        opportunity_level = "High"
    elif score >= 40:
        opportunity_level = "Medium"
    else:
        opportunity_level = "Low"

    business = dict(row)
    business.update({
        "score": score,
        "findings": findings,
        "recommendations": recommendations,
        "opportunity_level": opportunity_level,
    })
    return business


def all_analyzed_businesses():
    with get_db() as db:
        rows = db.execute("SELECT * FROM businesses ORDER BY id DESC").fetchall()
    return [analyze_business(row) for row in rows]


@app.context_processor
def inject_global_counts():
    with get_db() as db:
        prospect_count = db.execute("SELECT COUNT(*) AS c FROM businesses").fetchone()["c"]
        approval_count = db.execute(
            "SELECT COUNT(*) AS c FROM approvals WHERE status='Pending'"
        ).fetchone()["c"]
    return {
        "global_prospect_count": prospect_count,
        "global_approval_count": approval_count,
    }


@app.route("/")
def dashboard():
    businesses = all_analyzed_businesses()

    high_count = sum(1 for b in businesses if b["score"] >= 70)
    avg_score = round(sum(b["score"] for b in businesses) / len(businesses)) if businesses else 0
    client_count = sum(1 for b in businesses if b["status"] == "Client")

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        businesses=businesses[:6],
        total=len(businesses),
        high_count=high_count,
        avg_score=avg_score,
        client_count=client_count,
    )


@app.route("/prospects")
def prospects():
    query = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    status = request.args.get("status", "").strip()

    businesses = all_analyzed_businesses()

    if query:
        lowered = query.lower()
        businesses = [
            b for b in businesses
            if lowered in b["name"].lower()
            or lowered in b["city"].lower()
            or lowered in b["category"].lower()
        ]

    if level:
        businesses = [b for b in businesses if b["opportunity_level"] == level]

    if status:
        businesses = [b for b in businesses if b["status"] == status]

    return render_template(
        "prospects.html",
        active_page="prospects",
        businesses=businesses,
        query=query,
        level=level,
        status=status,
    )


@app.route("/business/<int:business_id>")
def business_detail(business_id):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()

    if row is None:
        return render_template("404.html", active_page="prospects"), 404

    return render_template(
        "business_detail.html",
        active_page="prospects",
        business=analyze_business(row),
    )


@app.route("/business/<int:business_id>/status", methods=["POST"])
def update_business_status(business_id):
    status = request.form.get("status", "Not Contacted")
    allowed = {
        "Not Contacted", "Researching", "Qualified", "Contacted",
        "Demo Scheduled", "Proposal Sent", "Client", "Not a Fit"
    }

    if status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for("business_detail", business_id=business_id))

    with get_db() as db:
        db.execute(
            "UPDATE businesses SET status = ? WHERE id = ?",
            (status, business_id)
        )

    flash("Pipeline status updated.", "success")
    return redirect(url_for("business_detail", business_id=business_id))


@app.route("/business/<int:business_id>/notes", methods=["POST"])
def update_business_notes(business_id):
    notes = request.form.get("notes", "").strip()

    with get_db() as db:
        db.execute(
            "UPDATE businesses SET notes = ? WHERE id = ?",
            (notes, business_id)
        )

    flash("Notes saved.", "success")
    return redirect(url_for("business_detail", business_id=business_id))


@app.route("/prospects/add", methods=["POST"])
def add_prospect():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()

    if not name or not city:
        flash("Business name and city are required.", "error")
        return redirect(request.referrer or url_for("prospects"))

    def checkbox(name):
        return 1 if request.form.get(name) == "on" else 0

    with get_db() as db:
        db.execute("""
            INSERT INTO businesses (
                name, city, category, reviews, rating, website, phone, email,
                online_booking, emergency_service, website_chat, estimate_form,
                status, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            city,
            request.form.get("category", "Local Service Business").strip() or "Local Service Business",
            int(request.form.get("reviews", 0) or 0),
            float(request.form.get("rating", 0) or 0),
            request.form.get("website", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("email", "").strip(),
            checkbox("online_booking"),
            checkbox("emergency_service"),
            checkbox("website_chat"),
            checkbox("estimate_form"),
            "Not Contacted",
            request.form.get("notes", "").strip(),
            datetime.now().isoformat(timespec="seconds"),
        ))

    flash("Prospect added.", "success")
    return redirect(url_for("prospects"))


@app.route("/prospects/import", methods=["POST"])
def import_prospects():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename.lower().endswith(".csv"):
        flash("Choose a CSV file first.", "error")
        return redirect(request.referrer or url_for("prospects"))

    text = uploaded.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    imported = 0

    with get_db() as db:
        for row in reader:
            name = (row.get("name") or "").strip()
            city = (row.get("city") or "").strip()

            if not name or not city:
                continue

            def truthy(key):
                return 1 if str(row.get(key, "")).strip().lower() in {
                    "1", "true", "yes", "y"
                } else 0

            db.execute("""
                INSERT INTO businesses (
                    name, city, category, reviews, rating, website, phone, email,
                    online_booking, emergency_service, website_chat, estimate_form,
                    status, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                city,
                (row.get("category") or "Local Service Business").strip(),
                int(row.get("reviews") or 0),
                float(row.get("rating") or 0),
                (row.get("website") or "").strip(),
                (row.get("phone") or "").strip(),
                (row.get("email") or "").strip(),
                truthy("online_booking"),
                truthy("emergency_service"),
                truthy("website_chat"),
                truthy("estimate_form"),
                (row.get("status") or "Not Contacted").strip(),
                (row.get("notes") or "").strip(),
                datetime.now().isoformat(timespec="seconds"),
            ))
            imported += 1

    flash(f"Imported {imported} prospects.", "success")
    return redirect(url_for("prospects"))


@app.route("/prospects/export")
def export_prospects():
    businesses = all_analyzed_businesses()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "name", "city", "category", "reviews", "rating", "website",
        "phone", "email", "score", "opportunity_level", "status"
    ])

    for b in businesses:
        writer.writerow([
            b["name"], b["city"], b["category"], b["reviews"], b["rating"],
            b["website"], b["phone"], b["email"], b["score"],
            b["opportunity_level"], b["status"]
        ])

    memory = io.BytesIO(output.getvalue().encode("utf-8"))
    memory.seek(0)

    return send_file(
        memory,
        mimetype="text/csv",
        as_attachment=True,
        download_name="business_os_prospects.csv",
    )


@app.route("/audits")
def audits():
    businesses = all_analyzed_businesses()
    return render_template(
        "audits.html",
        active_page="audits",
        businesses=businesses,
    )


@app.route("/agents")
def agents():
    agents_data = [
        {
            "name": "Prospect Finder",
            "purpose": "Discover qualified local service businesses.",
            "status": "Not connected",
            "stage": "Planned",
        },
        {
            "name": "Website Auditor",
            "purpose": "Inspect websites for lead-capture and automation gaps.",
            "status": "Local rules only",
            "stage": "Prototype",
        },
        {
            "name": "Research Agent",
            "purpose": "Collect public business context for personalized outreach.",
            "status": "Not connected",
            "stage": "Planned",
        },
        {
            "name": "Demo Builder",
            "purpose": "Create tailored demo concepts for qualified prospects.",
            "status": "Not connected",
            "stage": "Planned",
        },
    ]

    return render_template(
        "agents.html",
        active_page="agents",
        agents=agents_data,
    )


@app.route("/approvals")
def approvals():
    with get_db() as db:
        approvals_rows = db.execute("""
            SELECT approvals.*, businesses.name AS business_name
            FROM approvals
            LEFT JOIN businesses ON businesses.id = approvals.business_id
            ORDER BY approvals.id DESC
        """).fetchall()

    return render_template(
        "approvals.html",
        active_page="approvals",
        approvals=[dict(row) for row in approvals_rows],
    )


@app.route("/approvals/<int:approval_id>/<action>", methods=["POST"])
def approval_action(approval_id, action):
    if action not in {"approve", "reject"}:
        return redirect(url_for("approvals"))

    new_status = "Approved" if action == "approve" else "Rejected"

    with get_db() as db:
        db.execute(
            "UPDATE approvals SET status = ? WHERE id = ?",
            (new_status, approval_id)
        )

    flash(f"Approval marked {new_status.lower()}.", "success")
    return redirect(url_for("approvals"))


@app.route("/clients")
def clients():
    businesses = [b for b in all_analyzed_businesses() if b["status"] == "Client"]

    return render_template(
        "clients.html",
        active_page="clients",
        businesses=businesses,
    )


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html", active_page=""), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
