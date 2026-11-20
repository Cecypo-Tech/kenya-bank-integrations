app_name = "cecypo_bank_integrations"
app_title = "Cecypo Bank Integrations"
app_publisher = "Cecypo.Tech"
app_description = "Various bank integrations for Kenya"
app_email = "support@cecypo.tech"
app_license = "gpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "cecypo_bank_integrations",
# 		"logo": "/assets/cecypo_bank_integrations/logo.png",
# 		"title": "Cecypo Bank Integrations",
# 		"route": "/cecypo_bank_integrations",
# 		"has_permission": "cecypo_bank_integrations.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/cecypo_bank_integrations/css/cecypo_bank_integrations.css"
# app_include_js = "/assets/cecypo_bank_integrations/js/cecypo_bank_integrations.js"

# include js, css files in header of web template
# web_include_css = "/assets/cecypo_bank_integrations/css/cecypo_bank_integrations.css"
# web_include_js = "/assets/cecypo_bank_integrations/js/cecypo_bank_integrations.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "cecypo_bank_integrations/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "cecypo_bank_integrations/public/icons.svg"

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
# 	"methods": "cecypo_bank_integrations.utils.jinja_methods",
# 	"filters": "cecypo_bank_integrations.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "cecypo_bank_integrations.install.before_install"
# after_install = "cecypo_bank_integrations.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "cecypo_bank_integrations.uninstall.before_uninstall"
# after_uninstall = "cecypo_bank_integrations.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "cecypo_bank_integrations.utils.before_app_install"
# after_app_install = "cecypo_bank_integrations.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "cecypo_bank_integrations.utils.before_app_uninstall"
# after_app_uninstall = "cecypo_bank_integrations.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "cecypo_bank_integrations.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"cecypo_bank_integrations.tasks.all"
# 	],
# 	"daily": [
# 		"cecypo_bank_integrations.tasks.daily"
# 	],
# 	"hourly": [
# 		"cecypo_bank_integrations.tasks.hourly"
# 	],
# 	"weekly": [
# 		"cecypo_bank_integrations.tasks.weekly"
# 	],
# 	"monthly": [
# 		"cecypo_bank_integrations.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "cecypo_bank_integrations.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "cecypo_bank_integrations.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "cecypo_bank_integrations.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "cecypo_bank_integrations.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["cecypo_bank_integrations.utils.before_request"]
after_request = ["cecypo_bank_integrations.utils.request_hooks.after_request"]

# Job Events
# ----------
# before_job = ["cecypo_bank_integrations.utils.before_job"]
# after_job = ["cecypo_bank_integrations.utils.after_job"]

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
# 	"cecypo_bank_integrations.auth.validate"
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


after_install = "cecypo_bank_integrations.sms_payments.ensure_role"
after_migrate = ["cecypo_bank_integrations.sms_payments.ensure_role"]
