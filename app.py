from flask import Flask, render_template
from businesses import businesses

app = Flask(__name__)


def analyze_business(business):
    score = 0
    findings = []

    if business["online_booking"] == False:
        score += 25
        findings.append("No online booking")

    if business["emergency_service"] == True:
        score += 20
        findings.append("Offers emergency/high-intent service")

    if business["website_chat"] == False:
        score += 15
        findings.append("No website chat")

    if business["estimate_form"] == False:
        score += 20
        findings.append("No online estimate/request form")

    if business["reviews"] >= 100:
        score += 20
        findings.append("Established business with 100+ reviews")

    return score, findings


@app.route("/")
def home():
    analyzed_businesses = []

    for business in businesses:
        score, findings = analyze_business(business)

        analyzed_businesses.append({
            "name": business["name"],
            "city": business["city"],
            "reviews": business["reviews"],
            "score": score,
            "findings": findings
        })

    return render_template(
        "dashboard.html",
        businesses=analyzed_businesses
    )


if __name__ == "__main__":
    app.run(debug=True)