"""
I&M Bank Mpesa Push

Endpoint (called by I&M Bank):
  POST /api/method/cecypo_bank_integrations.im_bank.api.mpesa_push.process
"""

import frappe


@frappe.whitelist(allow_guest=False)
def process():
	"""Receive and record an incoming M-Pesa push notification from I&M Bank."""
	data = frappe.form_dict

	# Validate required fields
	required = ["transRef", "mpesaRef", "amount"]
	missing = [f for f in required if not data.get(f)]
	if missing:
		frappe.response["http_status_code"] = 400
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = f"Missing required fields: {', '.join(missing)}"
		frappe.response["mpesaRef"] = data.get("mpesaRef", "")
		return

	# Validate amount
	try:
		amount = float(data["amount"])
		if amount <= 0:
			raise ValueError
	except (ValueError, TypeError):
		frappe.response["http_status_code"] = 400
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = f"Invalid amount: {data.get('amount')}"
		frappe.response["mpesaRef"] = data.get("mpesaRef", "")
		return

	# Duplicate mpesaRef check
	if frappe.db.exists("IM Bank Transaction", {"mpesa_ref": data["mpesaRef"], "source": "Mpesa Push"}):
		frappe.response["http_status_code"] = 400
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = f"Duplicate mpesaRef: {data['mpesaRef']}"
		frappe.response["mpesaRef"] = data["mpesaRef"]
		return

	# Duplicate transRef check
	if frappe.db.exists("IM Bank Transaction", {"trans_ref": data["transRef"], "source": "Mpesa Push"}):
		frappe.response["http_status_code"] = 400
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = f"Duplicate transRef: {data['transRef']}"
		frappe.response["mpesaRef"] = data.get("mpesaRef", "")
		return

	# Split accountRef on "#": left = account ref, right = external reference
	raw_account_ref = data.get("accountRef", "")
	if "#" in raw_account_ref:
		account_ref, external_ref = raw_account_ref.split("#", 1)
	else:
		account_ref, external_ref = raw_account_ref, ""
	mapping = frappe.db.get_value(
		"IM Bank Account Mapping",
		{"short_code": account_ref, "parent": "Bank Integration Settings"},
		["company", "bank_account"],
		as_dict=True,
	)
	if not mapping:
		frappe.response["http_status_code"] = 400
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = f"No account mapping found for accountRef: {account_ref}"
		frappe.response["mpesaRef"] = data.get("mpesaRef", "")
		return

	try:
		doc = frappe.get_doc({
			"doctype": "IM Bank Transaction",
			"source": "Mpesa Push",
			"amount": amount,
			"company": mapping.company,
			"account": mapping.bank_account,
			"trans_ref": data.get("transRef"),
			"mpesa_ref": data.get("mpesaRef"),
			"msisdn": data.get("MSISDN"),
			"narration": data.get("narration"),
			"account_ref": account_ref,
			"external_ref_number": external_ref or None,
			"sort_code": data.get("sortCode"),
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.response["http_status_code"] = 200
		frappe.response["statusCode"] = "0"
		frappe.response["statusDescription"] = "Success"
		frappe.response["mpesaRef"] = data["mpesaRef"]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "IM Bank Mpesa Push – process error")
		frappe.response["http_status_code"] = 500
		frappe.response["statusCode"] = "1"
		frappe.response["statusDescription"] = "Internal server error, please try again later"
		frappe.response["mpesaRef"] = data.get("mpesaRef", "")
