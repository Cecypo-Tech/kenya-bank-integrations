import frappe


def execute():
	if frappe.db.exists("Mode of Payment", "KCB M-Pesa"):
		return

	frappe.get_doc({
		"doctype": "Mode of Payment",
		"mode_of_payment": "KCB M-Pesa",
		"enabled": 1,
		"type": "Phone",
	}).insert(ignore_permissions=True)

	frappe.db.commit()
