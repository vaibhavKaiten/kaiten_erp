import frappe
from frappe import _


@frappe.whitelist()
def manual_assign_to_execution_managers(job_file_name):
    """
    Manually trigger ToDo assignment for testing
    Can be called from browser console:
    frappe.call({
        method: 'kaiten_erp.kaiten_erp.api.job_file_workflow.manual_assign_to_execution_managers',
        args: { job_file_name: 'JOB-2026-00036' },
        callback: function(r) { console.log(r); }
    });
    """
    job_file = frappe.get_doc("Job File", job_file_name)

    # Import the function from JobFile_events
    from kaiten_erp.kaiten_erp.doc_events.JobFile_events import (
        assign_to_execution_managers,
    )

    assign_to_execution_managers(job_file)

    return {"status": "success", "message": "Assignment triggered"}


@frappe.whitelist()
def test_execution_manager_assignment(job_file_name):
    """
    Test function to manually trigger ToDo assignment for a Job File
    Usage: From console, call kaiten_erp.kaiten_erp.api.job_file_workflow.test_execution_manager_assignment("JOB-2026-00036")
    """
    job_file = frappe.get_doc("Job File", job_file_name)

    # Get all users with Execution Manager role
    execution_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Execution Manager", "parenttype": "User"},
        fields=["parent"],
    )

    print(f"\n=== Testing ToDo Assignment for {job_file_name} ===")
    print(f"Found {len(execution_managers)} Execution Managers:")

    for manager in execution_managers:
        user = manager.parent
        user_enabled = frappe.db.get_value("User", user, "enabled")
        print(f"  - {user} (enabled: {user_enabled})")

        # Check existing ToDos
        existing_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Job File",
                "reference_name": job_file.name,
                "allocated_to": user,
                "status": "Open",
            },
        )
        print(f"    Existing ToDo: {existing_todo}")

        if not existing_todo and user_enabled:
            try:
                todo = frappe.get_doc(
                    {
                        "doctype": "ToDo",
                        "allocated_to": user,
                        "reference_type": "Job File",
                        "reference_name": job_file.name,
                        "description": f"Job File {job_file.name} requires approval. Negotiated Amount (₹{job_file.negotiated_amount or 0:,.2f}) is less than MRP (₹{job_file.mrp or 0:,.2f}).",
                        "priority": "High",
                        "status": "Open",
                    }
                )
                todo.flags.ignore_permissions = True
                todo.insert()
                frappe.db.commit()
                print(f"    ✓ Created ToDo: {todo.name}")
            except Exception as e:
                print(f"    ✗ Error creating ToDo: {str(e)}")
                import traceback

                traceback.print_exc()

    return "Test completed. Check console output."
