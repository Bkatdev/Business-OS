from businesses import businesses

for business in businesses:
    print("--------------------")
    print("Website Audit:", business["name"])
    print("Location:", business["city"])

    if business["online_booking"] == False:
        print("⚠ No online booking found")

    if business["website_chat"] == False:
        print("⚠ No website chat found")

    if business["estimate_form"] == False:
        print("⚠ No online estimate/request form found")

    print("Audit complete.")