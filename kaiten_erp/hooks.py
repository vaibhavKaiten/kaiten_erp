app_name = "kaiten_erp"
app_title = "Kaiten Erp"
app_publisher = "Kaiten Software"
app_description = "Kaiten ERP Software"
app_email = "vaibhav@kaitensoftware.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "kaiten_erp",
# 		"logo": "/assets/kaiten_erp/logo.png",
# 		"title": "Kaiten Erp",
# 		"route": "/kaiten_erp",
# 		"has_permission": "kaiten_erp.api.permission.has_app_permission"
# 	}
# ]

# Fixtures
# ------------------
# Export fixtures to be installed during app installation
DOCTYPES = [
    "Supplier Territory Child Table",
    "Technical Survey",
    "Payment Control Child Table",
    "Job Execution Child Table",
    "Job File",
    "Revisist Log Child Table",
    "Photo Log",
    "Material Line Child Table",
    "Structure Mounting",
    "Verification Handover",
    "Meter Commissioning",
    "Meter Installation",
    "Project Installation",
    "Consolidated Procurement Item",
    "Procurement Consolidation",
    "Procurement Shortage Log",
    "Stock Reservation Log",
    "Location Log",
]


fixtures = [
    # -------------------------
    # Custom Fields
    # -------------------------
    {"dt": "Custom Field", "filters": [["module", "=", "Kaiten Erp"]]},
    # -------------------------
    # Property Setters
    # -------------------------
    # Property Setters (IMPORTANT FIX)
    {
        "dt": "Property Setter",
        "filters": [
            [
                "doc_type",
                "in",
                DOCTYPES
                + [
                    "Lead",
                    "Sales Order",
                    "Supplier",
                    "Material Request",
                    "Quotation",
                    "Sales Invoice",
                    "Purchase Order",
                    "Delivery Note",
                    "Purchase Receipt",
                    "Payment Entry",
                ],
            ]
        ],
    },
    # -------------------------
    # Server Scripts
    # -------------------------
    {"dt": "Server Script", "filters": [["module", "=", "Kaiten Erp"]]},
    # -------------------------
    # Client Scripts (if any created from UI)
    # -------------------------
    {"dt": "Client Script", "filters": [["module", "=", "Kaiten Erp"]]},
    # -------------------------
    # Workflows
    # -------------------------
    {"dt": "Workflow" },
    
    # -------------------------
    # Custom Permissions
    # -------------------------
    {"dt": "Custom DocPerm"},
    # -------------------------
    # Custom Roles (Explicit for Safety)
    # -------------------------
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "Vendor Manager",
                    "Vendor Executive",
                    "Vendor Head",
                    "Sales Executive",
                ],
            ]
        ],
    },
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/kaiten_erp/css/quick_hide.css"
# app_include_js = "/assets/kaiten_erp/js/kaiten_erp.js"

# include js, css files in header of web template
# web_include_css = "/assets/kaiten_erp/css/kaiten_erp.css"
# web_include_js = "/assets/kaiten_erp/js/kaiten_erp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "kaiten_erp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Supplier": "public/js/supplier.js",
    "Job File": "public/js/JobFile.js",
    "Sales Order": "public/js/sales_order.js",
    "Lead": "public/js/lead.js",
    "Technical Survey": "public/js/technical_survey.js",
    "Structure Mounting": "public/js/structure_mounting.js",
    "Project Installation": "public/js/project_installation.js",
    "Meter Installation": "public/js/meter_installation.js",
    "Meter Commissioning": "public/js/meter_commissioning.js",
    "Verification Handover": "public/js/verification_handover.js",
    "Quotation": "public/js/quotation.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "kaiten_erp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "kaiten_erp.utils.jinja_methods",
# 	"filters": "kaiten_erp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "kaiten_erp.install.before_install"
# after_install = "kaiten_erp.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "kaiten_erp.uninstall.before_uninstall"
# after_uninstall = "kaiten_erp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "kaiten_erp.utils.before_app_install"
# after_app_install = "kaiten_erp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "kaiten_erp.utils.before_app_uninstall"
# after_app_uninstall = "kaiten_erp.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "kaiten_erp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#     "Technical Survey": "kaiten_erp.kaiten_erp.doctype.technical_survey.technical_survey_list.get_permission_query_conditions"
# }
# has_permission = {
#     "Technical Survey": "kaiten_erp.kaiten_erp.permissions.technical_survey_permissions.has_permission"
# }


# Permissions

permission_query_conditions = {
    "Technical Survey": "kaiten_erp.kaiten_erp.doctype.technical_survey.technical_survey_list.get_permission_query_conditions",
    "Structure Mounting": "kaiten_erp.kaiten_erp.doctype.structure_mounting.structure_mounting_list.get_permission_query_conditions",
    "Project Installation": "kaiten_erp.kaiten_erp.doctype.project_installation.project_installation_list.get_permission_query_conditions",
    "Meter Installation": "kaiten_erp.kaiten_erp.doctype.meter_installation.meter_installation_list.get_permission_query_conditions",
    "Meter Commissioning": "kaiten_erp.kaiten_erp.doctype.meter_commissioning.meter_commissioning_list.get_permission_query_conditions",
    "Verification Handover": "kaiten_erp.kaiten_erp.doctype.verification_handover.verification_handover_list.get_permission_query_conditions",
    "ToDo": "kaiten_erp.permissions.todo_permissions.todo_permission_query",
}

has_permission = {
    "Technical Survey": "kaiten_erp.kaiten_erp.permissions.technical_survey_permissions.has_permission",
    "Structure Mounting": "kaiten_erp.kaiten_erp.permissions.structure_mounting_permissions.has_permission",
    "Project Installation": "kaiten_erp.kaiten_erp.permissions.project_installation_permissions.has_permission",
    "Meter Installation": "kaiten_erp.kaiten_erp.permissions.meter_installation_permissions.has_permission",
    "Meter Commissioning": "kaiten_erp.kaiten_erp.permissions.meter_commissioning_permissions.has_permission",
    "Verification Handover": "kaiten_erp.kaiten_erp.permissions.verification_handover_permissions.has_permission",
    "ToDo": "kaiten_erp.permissions.todo_permissions.todo_has_permission",
}


# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Lead": {"on_update": "kaiten_erp.kaiten_erp.doc_events.lead_events.on_update"},
    "Job File": {
        "on_update": "kaiten_erp.kaiten_erp.doc_events.JobFile_events.on_update"
    },
    "Sales Order": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.sales_order_events.validate",
        "on_submit": [
            "kaiten_erp.kaiten_erp.doc_events.sales_order_events.on_submit",
            "kaiten_erp.kaiten_erp.api.bom_stock_reservation.on_sales_order_submit",
            "kaiten_erp.kaiten_erp.api.milestone_invoice_manager.create_advance_invoice",
        ],
        "on_cancel": "kaiten_erp.kaiten_erp.api.bom_stock_reservation.on_sales_order_cancel",
    },
    "Quotation": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.quotation_events.validate",
    },
    "Delivery Note": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.delivery_note_events.validate",
        "on_submit": "kaiten_erp.kaiten_erp.doc_events.delivery_note_events.on_submit",
    },
    "Material Request": {
        "validate": "kaiten_erp.kaiten_erp.api.milestone_invoice_manager.validate_advance_payment",
    },
    "Payment Entry": {
        "on_submit": "kaiten_erp.kaiten_erp.api.milestone_invoice_manager.update_payment_status",
    },
    "Stock Entry": {
        "validate": "kaiten_erp.kaiten_erp.api.milestone_invoice_manager.validate_advance_payment",
    },
    # Execution DocTypes (Technical Survey , Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover) - Workflow Validation & Vendor Continuity
    "Technical Survey": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
    "Structure Mounting": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
    "Project Installation": {
        "validate": [
            "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
            "kaiten_erp.kaiten_erp.api.execution_payment_validation.validate_installation_payment",
        ],
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
    "Meter Installation": {
        "validate": [
            "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
            "kaiten_erp.kaiten_erp.api.execution_payment_validation.validate_installation_payment",
        ],
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
    "Meter Commissioning": {
        "validate": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
    "Verification Handover": {
        "validate": [
            "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.validate",
            "kaiten_erp.kaiten_erp.api.execution_payment_validation.validate_verification_payment",
        ],
        "on_update": "kaiten_erp.kaiten_erp.doc_events.technical_survey_events.on_update",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "kaiten_erp.kaiten_erp.api.milestone_invoice_manager.check_advance_payments_daily"
    ],
    "hourly": [
        "kaiten_erp.kaiten_erp.cron_job.hourly_backup.take_full_backup"
    ]
}


# Testing
# -------

# before_tests = "kaiten_erp.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "kaiten_erp.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "kaiten_erp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "kaiten_erp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["kaiten_erp.utils.before_request"]
# after_request = ["kaiten_erp.utils.after_request"]

# Job Events
# ----------
# before_job = ["kaiten_erp.utils.before_job"]
# after_job = ["kaiten_erp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"kaiten_erp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
