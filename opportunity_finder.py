from businesses import businesses

for business in businesses:
    opportunity_score = 0

    if business["online_booking"] == False:
        opportunity_score += 25

    if business["emergency_service"] == True:
        opportunity_score += 20

    if business["website_chat"] == False:
        opportunity_score += 15

    if business["estimate_form"] == False:
        opportunity_score += 20

    if business["reviews"] >= 100:
        opportunity_score += 20

    print("--------------------")
    print("Business:", business["name"])
    print("Location:", business["city"])
    print("Opportunity Score:", opportunity_score, "/ 100")