from businesses import businesses

for business in businesses:
    opportunity_score = 0
    findings = []

    if business["online_booking"] == False:
        opportunity_score += 25
        findings.append("No online booking")

    if business["emergency_service"] == True:
        opportunity_score += 20
        findings.append("Offers emergency/high-intent service")

    if business["website_chat"] == False:
        opportunity_score += 15
        findings.append("No website chat")

    if business["estimate_form"] == False:
        opportunity_score += 20
        findings.append("No online estimate/request form")

    if business["reviews"] >= 100:
        opportunity_score += 20
        findings.append("Established business with 100+ reviews")

    print("==============================")
    print("BUSINESS:", business["name"])
    print("LOCATION:", business["city"])
    print("OPPORTUNITY SCORE:", opportunity_score, "/ 100")
    print("FINDINGS:")

    for finding in findings:
        print("-", finding)