# import frappe

# @frappe.whitelist()


# def get_suppliers_by_territory(doctype, txt, searchfield, start, page_len, filters):
#     territory = filters.get("territory")

#     if not territory:
#         return []

#     return frappe.db.sql("""
#         SELECT DISTINCT s.name
#         FROM `tabSupplier` s
#         INNER JOIN `tabSupplier Territory Child Table` st
#             ON st.parent = s.name
#         WHERE
#             st.territory = %s
#             AND st.status = 'Active'
#             AND s.name LIKE %s
#         ORDER BY s.name
#         LIMIT %s OFFSET %s
#     """, (
#         territory,
#         f"%{txt}%",
#         page_len,
#         start
#     ))



# --------------------------------------------------------------------------------------------------------



import frappe

@frappe.whitelist()
def get_suppliers_by_territory_and_group(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters
):
    territory = filters.get("territory")
    allowed_groups = filters.get("supplier_groups")

    if not territory or not allowed_groups:
        return []

    return frappe.db.sql("""
        SELECT DISTINCT s.name
        FROM `tabSupplier` s
        INNER JOIN `tabSupplier Territory Child Table` st
            ON st.parent = s.name
        WHERE
            st.territory = %s
            AND st.status = 'Active'
            AND s.supplier_group IN %(groups)s
            AND s.name LIKE %s
        ORDER BY s.name
        LIMIT %s OFFSET %s
    """, {
        "groups": tuple(allowed_groups),
        "territory": territory,
        "txt": f"%{txt}%",
        "page_len": page_len,
        "start": start
    })
