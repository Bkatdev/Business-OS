from flask import Flask
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
    business_cards = ""

    for business in businesses:
        score, findings = analyze_business(business)

        findings_html = ""

        for finding in findings:
            findings_html += f"<li>{finding}</li>"

        business_cards += f"""
        <div style="
            border: 1px solid #cccccc;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 10px;
        ">
            <h2>{business["name"]}</h2>

            <p><strong>Location:</strong> {business["city"]}</p>
            <p><strong>Reviews:</strong> {business["reviews"]}</p>

            <p>
                <strong>Opportunity Score:</strong>
                {score} / 100
            </p>

            <h3>Findings</h3>

            <ul>
                {findings_html}
            </ul>
        </div>
        """

    return f"""
    <html>
        <head>
            <title>Business OS</title>
        </head>

        <body style="
            font-family: Arial;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
        ">

            <h1>Business OS</h1>
            <p>Local Business Opportunity Dashboard</p>

            {business_cards}

        </body>
    </html>
    """


if __name__ == "__main__":
    app.run(debug=True)