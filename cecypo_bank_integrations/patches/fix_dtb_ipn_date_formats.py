import frappe


def execute():
	"""
	Convert DTB IPN Transaction date columns from 'DD-Mon-YYYY' text format to 'YYYY-MM-DD'
	before schema sync changes them to proper DATE columns.
	"""
	if not frappe.db.table_exists("DTB IPN Transaction"):
		return

	for col in ("transaction_date", "value_date"):
		frappe.db.sql(
			f"""
			UPDATE `tabDTB IPN Transaction`
			SET `{col}` = STR_TO_DATE(`{col}`, '%%d-%%b-%%Y')
			WHERE `{col}` IS NOT NULL
			  AND `{col}` != ''
			  AND `{col}` NOT REGEXP '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
			"""
		)

	frappe.db.commit()
