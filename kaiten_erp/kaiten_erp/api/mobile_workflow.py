# Copyright (c) 2025, Kaiten Software
# Mobile Workflow API
# Exposes workflow actions for the mobile app, filtered by role via Frappe's native engine.
#
# Endpoints (no hooks.py registration needed — auto-discovered via @frappe.whitelist):
#   GET  /api/method/kaiten_erp.kaiten_erp.api.mobile_workflow.get_actions
#   POST /api/method/kaiten_erp.kaiten_erp.api.mobile_workflow.apply_action

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions


@frappe.whitelist()
def get_actions(doc_type, doc_name):
	"""
	Return workflow actions available to the current user for a document.

	Frappe's get_transitions() natively handles:
	  - Role filtering (transition.allowed in user roles)
	  - Condition script evaluation (frappe.safe_eval)
	  - Docstatus constraints
	  - Current workflow state matching

	Args:
	    doc_type (str): DocType name e.g. "Technical Survey"
	    doc_name (str): Document name e.g. "TS-2026-00001"

	Returns:
	    {
	        "success": True,
	        "doc_type": "Technical Survey",
	        "doc_name": "TS-2026-00001",
	        "workflow_state": "In Progress",
	        "actions": [
	            {
	                "action": "Submit For Review",
	                "next_state": "Submitted",
	                "allowed": "Vendor Executive"
	            }
	        ]
	    }

	Raises:
	    frappe.PermissionError: if user cannot read the document
	    frappe.DoesNotExistError: if document does not exist
	"""
	if not doc_type or not doc_name:
		frappe.throw(_("doc_type and doc_name are required"), frappe.ValidationError)

	# Raises PermissionError automatically if user cannot read this doc
	doc = frappe.get_doc(doc_type, doc_name)

	# get_transitions filters by: current state + user roles + condition scripts
	transitions = get_transitions(doc)

	return {
		"success": True,
		"doc_type": doc_type,
		"doc_name": doc_name,
		"workflow_state": doc.get("workflow_state"),
		"actions": [
			{
				"action": t["action"],
				"next_state": t["next_state"],
				"allowed": t["allowed"],
			}
			for t in transitions
		],
	}


@frappe.whitelist()
def apply_action(doc_type, doc_name, action):
	"""
	Apply a workflow action to a document.

	Delegates entirely to Frappe's apply_workflow() which internally:
	  - Reloads the doc from DB — handles stale/concurrent state (race condition safe)
	  - Re-runs get_transitions() to validate role + conditions at apply time
	  - Throws WorkflowTransitionError if action is invalid or user lacks permission
	  - Throws "Self approval is not allowed" if self-approval is disabled
	  - Updates workflow_state + any configured update_field on the target state
	  - Runs transition_tasks (Webhooks, Server Scripts) if configured
	  - Saves the document

	Args:
	    doc_type (str): DocType name e.g. "Technical Survey"
	    doc_name (str): Document name e.g. "TS-2026-00001"
	    action   (str): Workflow action label e.g. "Submit For Review"

	Returns:
	    {
	        "success": True,
	        "doc_type": "Technical Survey",
	        "doc_name": "TS-2026-00001",
	        "action_applied": "Submit For Review",
	        "workflow_state": "Submitted"
	    }

	Raises:
	    frappe.PermissionError:        if user cannot read the document
	    WorkflowTransitionError:       if action is invalid or user lacks the required role
	    frappe.ValidationError:        if self-approval is blocked or doc validation fails
	    frappe.DoesNotExistError:      if document does not exist
	"""
	if not doc_type or not doc_name or not action:
		frappe.throw(_("doc_type, doc_name, and action are all required"), frappe.ValidationError)

	# Permission check — apply_workflow reloads from DB internally,
	# but we do an explicit get_doc here to surface PermissionError early
	# with a clear message before any workflow logic runs.
	doc = frappe.get_doc(doc_type, doc_name)

	# Apply — Frappe validates role, conditions, self-approval, then saves
	apply_workflow(doc, action)

	# Re-fetch state from DB (apply_workflow mutates the in-memory doc,
	# but reading from DB confirms the persisted state)
	updated_state = frappe.db.get_value(doc_type, doc_name, "workflow_state")

	return {
		"success": True,
		"doc_type": doc_type,
		"doc_name": doc_name,
		"action_applied": action,
		"workflow_state": updated_state,
	}
