businesses = [
    {
        "name": "Example Tree Service",
        "city": "East Brunswick",
        "reviews": 125,
        "online_booking": False,
        "emergency_service": True,
        "website_chat": False,
        "estimate_form": False
    },
    {
        "name": "Example Landscaping",
        "city": "Old Bridge",
        "reviews": 65,
        "online_booking": True,
        "emergency_service": False,
        "website_chat": False,
        "estimate_form": True
    },
    {
        "name": "Example Auto Repair",
        "city": "Marlboro",
        "reviews": 210,
        "online_booking": False,
        "emergency_service": False,
        "website_chat": True,
        "estimate_form": True
    }
]

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