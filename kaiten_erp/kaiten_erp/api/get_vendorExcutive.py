import frappe


@frappe.whitelist()
def get_vendor_executive_users(doctype, txt, searchfield, start, page_len, filters):
    """
    Query function to filter Vendor Executive users linked to a specific supplier

    The relationship is: User -> Contact (via 'user' field) -> Supplier (via Dynamic Link)
    """
    # Debug logging
    frappe.logger().debug(f"Query called with filters: {filters}")
    frappe.logger().debug(f"Search text: {txt}, Start: {start}, Page len: {page_len}")

    supplier = filters.get("supplier")
    frappe.logger().debug(f"Supplier extracted: {supplier}")

    if not supplier:
        frappe.logger().debug("No supplier provided, returning empty list")
        return []

    # Query to get users who:
    # 1. Have Vendor Executive role
    # 2. Are linked to a Contact
    # 3. That Contact is linked to the specified Supplier via Dynamic Link
    result = frappe.db.sql(
        """
        SELECT DISTINCT
            u.name,
            u.full_name
        FROM
            `tabUser` u
        JOIN
            `tabHas Role` r ON r.parent = u.name
        JOIN
            `tabContact` c ON c.user = u.name
        JOIN
            `tabDynamic Link` dl ON dl.parent = c.name
        WHERE
            r.role = 'Vendor Executive'
            AND u.enabled = 1
            AND dl.link_doctype = 'Supplier'
            AND dl.link_name = %s
            AND dl.parenttype = 'Contact'
            AND (u.name LIKE %s OR u.full_name LIKE %s)
        LIMIT %s, %s
    """,
        (supplier, f"%{txt}%", f"%{txt}%", start, page_len),
    )

    frappe.logger().debug(f"Final result: {result}")
    return result
