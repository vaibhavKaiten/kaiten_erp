import frappe
import requests


@frappe.whitelist()
def get_pincode_details(pincode):
    """Fetch city (district) and state from India Post API for the given 6-digit pincode."""
    pincode = str(pincode or "").strip()
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        return None

    try:
        response = requests.get(
            f"https://api.postalpincode.in/pincode/{pincode}",
            timeout=5,
        )
        data = response.json()
        if data and data[0].get("Status") == "Success":
            post_office = data[0]["PostOffice"][0]
            return {
                "city": post_office.get("District"),
                "state": post_office.get("State"),
            }
    except Exception:
        frappe.log_error(f"Pincode lookup failed for {pincode}", "Pincode API")

    return None
