business = {
    "name": "Example Tree Service",
    "city": "East Brunswick",
    "website": "https://example.com",
    "reviews": 125,
    "online_booking": False,
    "emergency_service": True
}

opportunity_score = 0

if business["online_booking"] == False:
    opportunity_score = opportunity_score + 25

if business["emergency_service"] == True:
    opportunity_score = opportunity_score + 15

if business["online_booking"] == False:
    print("Opportunity found: This business has no online booking.")

print(business)
print("Opportunity Score:", opportunity_score)




