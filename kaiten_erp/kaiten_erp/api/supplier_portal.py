"""
Supplier Portal User Management
API for creating vendor portal users with automatic Contact-Supplier linking
"""

import frappe
from frappe import _
from frappe.utils import random_string


@frappe.whitelist()
def create_vendor_portal_user(
    supplier_name,
    first_name,
    email,
    user_type,
    last_name=None,
    mobile_no=None,
    send_welcome_email=1,
):
    """
    Create a vendor portal user (Vendor Manager or Vendor Executive)
    and automatically link them to the Supplier

    Args:
        supplier_name: Name of the Supplier
        first_name: First name of the user
        email: Email address (will be the username)
        user_type: "Vendor Manager" or "Vendor Executive"
        last_name: Last name (optional)
        mobile_no: Mobile number (optional)
        send_welcome_email: Whether to send welcome email (default: 1)

    Returns:
        dict: Success/error response with user and contact details
    """
    try:
        # Validate supplier exists
        if not frappe.db.exists("Supplier", supplier_name):
            return {
                "success": False,
                "error": _("Supplier {0} does not exist").format(supplier_name),
            }

        # Check if user already exists
        if frappe.db.exists("User", email):
            return {
                "success": False,
                "error": _("User with email {0} already exists").format(email),
            }

        # Validate user_type
        if user_type not in ["Vendor Manager", "Vendor Executive"]:
            return {
                "success": False,
                "error": _(
                    "Invalid user type. Must be 'Vendor Manager' or 'Vendor Executive'"
                ),
            }

        # Create User first
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = first_name
        if last_name:
            user.last_name = last_name

        user.user_type = "Website User"  # Portal user
        user.send_welcome_email = int(send_welcome_email)

        # Set a random password (user will reset via email)
        user.new_password = random_string(12)

        # Insert user first without role to avoid permission issues
        user.insert(ignore_permissions=True)
        
        # Add role using add_roles method which properly creates Has Role records
        user.add_roles(user_type)
        
        # Save to persist the role
        user.save(ignore_permissions=True)

        frappe.logger().info(f"Created User {user.name} with role {user_type}")

        # Create Contact
        contact = frappe.new_doc("Contact")
        contact.first_name = first_name
        if last_name:
            contact.last_name = last_name

        # Link to user
        contact.user = user.name

        # Add email
        contact.append("email_ids", {"email_id": email, "is_primary": 1})

        # Add mobile
        if mobile_no:
            contact.append("phone_nos", {"phone": mobile_no, "is_primary_mobile_no": 1})

        # Add dynamic link to Supplier
        contact.append(
            "links", {"link_doctype": "Supplier", "link_name": supplier_name}
        )

        contact.insert(ignore_permissions=True)

        frappe.logger().info(f"Created Contact {contact.name} for {email}")

        # Add user to Supplier's portal users table
        supplier = frappe.get_doc("Supplier", supplier_name)

        # Check if portal_users field exists
        if hasattr(supplier, "portal_users"):
            supplier.append("portal_users", {"user": user.name})
            supplier.save(ignore_permissions=True)
            frappe.logger().info(
                f"Added {user.name} to Supplier {supplier_name} portal users"
            )

        frappe.db.commit()

        return {
            "success": True,
            "user_email": user.name,
            "contact_name": contact.name,
            "supplier_name": supplier_name,
            "message": _("Portal user {0} created and linked to Supplier {1}").format(
                user.name, supplier_name
            ),
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Error creating portal user for Supplier {supplier_name}",
        )
        return {
            "success": False,
            "error": _("Error creating portal user: {0}").format(str(e)),
        }


@frappe.whitelist()
def link_existing_user_to_supplier(supplier_name, user_email, user_type=None):
    """
    Link an existing vendor user to a Supplier

    This creates/updates the Contact's Dynamic Link to the Supplier
    and adds the user to the Supplier's portal users table.
    Also ensures the user has the correct Vendor role.

    Args:
        supplier_name: Name of the Supplier
        user_email: Email of the existing user
        user_type: Optional role to assign ("Vendor Manager" or "Vendor Executive")

    Returns:
        dict: Success/error response
    """
    try:
        # Validate supplier exists
        if not frappe.db.exists("Supplier", supplier_name):
            return {
                "success": False,
                "error": _("Supplier {0} does not exist").format(supplier_name),
            }

        # Validate user exists
        if not frappe.db.exists("User", user_email):
            return {
                "success": False,
                "error": _("User {0} does not exist").format(user_email),
            }

        # Check roles and assign if needed
        user_roles = frappe.get_roles(user_email)
        vendor_roles = ["Vendor Manager", "Vendor Executive"]
        has_vendor_role = any(role in user_roles for role in vendor_roles)

        # If user_type is provided, ensure user has that role
        if user_type and user_type in vendor_roles:
            if user_type not in user_roles:
                user = frappe.get_doc("User", user_email)
                # Use add_roles method instead of append to properly create Has Role records
                user.add_roles(user_type)
                user.save(ignore_permissions=True)
                frappe.logger().info(f"Added role {user_type} to User {user_email}")

        # If no user_type provided, check if they already have a vendor role
        elif not has_vendor_role:
            return {
                "success": False,
                "error": _(
                    "User {0} does not have a Vendor role, and no role was specified."
                ).format(user_email),
            }

        # Get or create Contact for this user
        contact_name = frappe.db.get_value("Contact", {"user": user_email}, "name")

        if not contact_name:
            # Create a new contact for this user
            user = frappe.get_doc("User", user_email)

            contact = frappe.new_doc("Contact")
            contact.first_name = user.first_name
            contact.last_name = user.last_name
            contact.user = user_email

            # Add email
            contact.append("email_ids", {"email_id": user_email, "is_primary": 1})

            # Add dynamic link to Supplier
            contact.append(
                "links", {"link_doctype": "Supplier", "link_name": supplier_name}
            )

            contact.insert(ignore_permissions=True)
            contact_name = contact.name

            frappe.logger().info(
                f"Created Contact {contact_name} for existing user {user_email}"
            )
        else:
            # Contact exists - check if already linked to this supplier
            contact = frappe.get_doc("Contact", contact_name)

            already_linked = False
            for link in contact.links:
                if link.link_doctype == "Supplier" and link.link_name == supplier_name:
                    already_linked = True
                    break

            if not already_linked:
                # Add the dynamic link
                contact.append(
                    "links", {"link_doctype": "Supplier", "link_name": supplier_name}
                )
                contact.save(ignore_permissions=True)

                frappe.logger().info(
                    f"Linked Contact {contact_name} to Supplier {supplier_name}"
                )
            else:
                frappe.logger().info(
                    f"Contact {contact_name} already linked to Supplier {supplier_name}"
                )

        # Add user to Supplier's portal users table
        supplier = frappe.get_doc("Supplier", supplier_name)

        # Check if user already in portal_users table
        user_exists = False
        if hasattr(supplier, "portal_users"):
            for portal_user in supplier.portal_users:
                if portal_user.user == user_email:
                    user_exists = True
                    break

            if not user_exists:
                supplier.append("portal_users", {"user": user_email})
                supplier.save(ignore_permissions=True)
                frappe.logger().info(
                    f"Added {user_email} to Supplier {supplier_name} portal users"
                )

        frappe.db.commit()

        return {
            "success": True,
            "user_email": user_email,
            "contact_name": contact_name,
            "supplier_name": supplier_name,
            "message": _("User {0} successfully linked to Supplier {1}").format(
                user_email, supplier_name
            ),
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Error linking user {user_email} to Supplier {supplier_name}",
        )
        return {"success": False, "error": _("Error linking user: {0}").format(str(e))}


@frappe.whitelist()
def get_supplier_portal_users(supplier_name):
    """
    Get all portal users linked to a specific Supplier

    Args:
        supplier_name: Name of the Supplier

    Returns:
        list: List of users with their details
    """

    users = frappe.db.sql(
        """
        SELECT DISTINCT
            u.name as email,
            u.full_name,
            u.enabled,
            c.name as contact_name,
            GROUP_CONCAT(hr.role) as roles
        FROM `tabUser` u
        INNER JOIN `tabContact` c ON c.user = u.name
        INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE dl.link_doctype = 'Supplier'
            AND dl.link_name = %(supplier)s
            AND hr.role IN ('Vendor Manager', 'Vendor Executive')
        GROUP BY u.name, u.full_name, u.enabled, c.name
        ORDER BY u.full_name
    """,
        {"supplier": supplier_name},
        as_dict=True,
    )

    return users
