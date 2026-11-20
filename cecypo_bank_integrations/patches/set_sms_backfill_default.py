import frappe


def execute():
	"""Single DocType defaults don't reach an existing settings record: store the 3-day default once."""
	if not frappe.db.sql(
		"select 1 from tabSingles where doctype=%s and field=%s", ("Bank Integration Settings", "sms_backfill_days")
	):
		frappe.db.set_single_value("Bank Integration Settings", "sms_backfill_days", 3)
