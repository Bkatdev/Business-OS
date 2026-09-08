from businesses import businesses

business = businesses[0]

print("Website Audit:", business["name"])
if business["online_booking"] == False:
    print("⚠ No online booking found")
if business["website_chat"] == False:
    print("⚠ No website chat found")
if business["estimate_form"] == False:
    print("⚠ No online estimate/request form found")
    print("--------------------")
print("Audit complete.")