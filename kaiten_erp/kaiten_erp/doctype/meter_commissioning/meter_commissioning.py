# Copyright (c) 2026, up411@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt
from kaiten_erp.kaiten_erp.api.milestone_invoice_manager import (
    create_milestone_invoice,
    get_milestone_invoice,
    assign_todo_to_accounts_managers,
    is_self_funding_order,
)
from kaiten_erp.kaiten_erp.api.gps import log_workflow_location


class MeterCommissioning(Document):
    def validate(self):
        log_workflow_location(self)

    def on_update(self):
        """
        Called when Meter Commissioning is updated
        Triggers final invoice creation when workflow_state changes to "Approved"
        """
        # Only fire once when the state actually transitions to "Approved"
        if (
            self.has_value_changed("workflow_state")
            and self.workflow_state == "Approved"
        ):
            self.create_final_milestone_invoice()

    def create_final_milestone_invoice(self):
        """
        Create final milestone invoice when Meter Commissioning is approved
        """
        # Get linked Sales Order
        sales_order = self.get_linked_sales_order()

        if not sales_order:
            frappe.msgprint(
                _(
                    "No Sales Order linked to this Meter Commissioning. Final milestone invoice will not be created."
                ),
                alert=True,
                indicator="orange",
            )
            return

        # Only create final invoice for self-funding orders
        if not is_self_funding_order(sales_order):
            return

        # Check if final invoice already exists
        existing_final_invoice = get_milestone_invoice(sales_order, "final")

        if existing_final_invoice:
            frappe.msgprint(
                _("Final invoice already exists: {0}").format(existing_final_invoice),
                alert=True,
                indicator="orange",
            )
            return

        # Get Sales Order document to get grand total and payment terms
        so_doc = frappe.get_doc("Sales Order", sales_order)

        # Calculate final amount from Sales Order payment_schedule (3rd tranche)
        final_amount = so_doc.grand_total  # Default to full amount
        final_percentage = 0

        if so_doc.payment_schedule and len(so_doc.payment_schedule) >= 3:
            # Use the actual scheduled 3rd tranche amount
            third_row = so_doc.payment_schedule[2]
            final_amount = flt(third_row.payment_amount)
            final_percentage = flt(third_row.invoice_portion)
            frappe.logger().info(
                f"Final invoice for SO {sales_order}: {final_percentage}% = {final_amount} (from payment_schedule row 3)"
            )
        elif so_doc.payment_terms_template:
            # Fallback: calculate from Payment Terms Template when schedule has < 3 rows
            payment_terms = frappe.get_all(
                "Payment Terms Template Detail",
                filters={"parent": so_doc.payment_terms_template},
                fields=["invoice_portion", "description"],
                order_by="idx asc",
            )

            if payment_terms and len(payment_terms) >= 3:
                final_percentage = flt(payment_terms[2].invoice_portion)
                final_amount = (so_doc.grand_total * final_percentage) / 100
                frappe.logger().info(
                    f"Final invoice for SO {sales_order}: {final_percentage}% of {so_doc.grand_total} = {final_amount} (from template)"
                )
            elif payment_terms and len(payment_terms) == 2:
                first_percentage = flt(payment_terms[0].invoice_portion)
                second_percentage = flt(payment_terms[1].invoice_portion)
                final_percentage = 100 - first_percentage - second_percentage
                final_amount = (so_doc.grand_total * final_percentage) / 100

        # Create invoice item for final milestone
        items = [
            {
                "item_code": "Final Payment",
                "item_name": "Final Payment",
                "description": _(
                    "Final payment ({0}%) for Sales Order {1} - Meter Commissioning {2} approved"
                ).format(final_percentage or 100, sales_order, self.name),
                "qty": 1,
                "uom": "Nos",
                "rate": final_amount,
                "amount": final_amount,
            }
        ]

        # Create the invoice
        try:
            invoice = create_milestone_invoice(
                so_doc,  # Use Sales Order as source doc
                "Final Payment",
                items,
                description=_(
                    "Payment required before verification and project closure. Amount: {0}% of total"
                ).format(final_percentage or 100),
            )

            # Update Sales Order with final invoice reference
            frappe.db.set_value(
                "Sales Order",
                sales_order,
                "custom_final_invoice",
                invoice.name,
                update_modified=False,
            )

            # Assign To-Do to Accounts Managers
            assign_todo_to_accounts_managers(
                invoice,
                "Final Payment",
                description=_(
                    "Customer: {0}, Sales Order: {1}, Final Amount ({2}%): {3}"
                ).format(
                    so_doc.customer,
                    sales_order,
                    final_percentage or 100,
                    frappe.utils.fmt_money(final_amount, currency=so_doc.currency),
                ),
            )

            frappe.db.commit()

        except Exception as e:
            frappe.log_error(
                frappe.get_traceback(),
                _("Failed to create final invoice for Meter Commissioning {0}").format(
                    self.name
                ),
            )
            frappe.msgprint(
                _("Failed to create final invoice: {0}").format(str(e)),
                alert=True,
                indicator="red",
            )

    def get_linked_sales_order(self):
        """
        Get linked Sales Order from Meter Commissioning
        Tries multiple fallback methods to find the Sales Order.

        Returns:
            str: Sales Order name or None
        """
        # Method 1: Check custom_sales_order field
        if (
            hasattr(self, "custom_sales_order")
            and self.custom_sales_order
        ):
            return self.custom_sales_order

        sales_order = None

        # Method 2: Via job_file -> Job File -> sales_order
        if hasattr(self, "job_file") and self.job_file:
            sales_order = frappe.db.get_value(
                "Job File", self.job_file, "sales_order"
            )

        # Method 3: Via lead -> Job File (by lead) -> sales_order
        if not sales_order and hasattr(self, "lead") and self.lead:
            job_file_name = frappe.db.get_value(
                "Job File", {"lead": self.lead}, "name"
            )
            if job_file_name:
                sales_order = frappe.db.get_value(
                    "Job File", job_file_name, "sales_order"
                )

        # Cache the result so future lookups are instant
        if sales_order and hasattr(self, "custom_sales_order"):
            frappe.db.set_value(
                "Meter Commissioning",
                self.name,
                "custom_sales_order",
                sales_order,
                update_modified=False,
            )

        return sales_order
