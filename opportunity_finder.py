business = {
    "name": "Example Tree Service",
    "city": "East Brunswick",
    "website": "https://example.com",
    "reviews": 125,
    "online_booking": False,
    "emergency_service": True,
    "website_chat": False,
    "estimate_form": False
}

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

print("Business:", business["name"])
print("Location:", business["city"])
print("Opportunity Score:", opportunity_score, "/ 100")