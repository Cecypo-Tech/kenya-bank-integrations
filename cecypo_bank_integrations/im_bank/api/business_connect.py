"""
I&M Bank Business Connect – Collections API v2.0

Endpoints (called by I&M Bank):
  POST /api/method/cecypo_bank_integrations.im_bank.api.business_connect.validate
  POST /api/method/cecypo_bank_integrations.im_bank.api.business_connect.payment
  POST /api/method/cecypo_bank_integrations.im_bank.api.business_connect.ipn
"""

import json
from datetime import timezone

from dateutil import parser as _dateutil_parser

import frappe


def _parse_datetime(dt_str):
	"""Convert an ISO 8601 datetime string (with or without timezone) to a naive UTC datetime string for MariaDB."""
	if not dt_str:
		return None
	dt = _dateutil_parser.parse(str(dt_str))
	if dt.tzinfo is not None:
		dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
	return dt.strftime("%Y-%m-%d %H:%M:%S")


def _resolve_account_mapping(short_code, payment_type):
	"""Look up IM Bank mappings from Bank Integration Settings.

	Account Mapping (short_code → company + bank_account) and
	Payment Type Mapping (payment_type → mode_of_payment) are resolved independently.

	Returns (company, bank_account, mode_of_payment) — any may be None if not configured.
	"""
	try:
		settings = frappe.get_single("Bank Integration Settings")
		account_map = next(
			(r for r in settings.im_bank_account_mappings if short_code.startswith(r.short_code)),
			None,
		)
		payment_type_map = next(
			(r for r in settings.im_bank_payment_type_mappings if r.payment_type == payment_type),
			None,
		)
		return (
			account_map.company if account_map else None,
			account_map.bank_account if account_map else None,
			payment_type_map.mode_of_payment if payment_type_map else None,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "IM Bank Business Connect – _resolve_account_mapping error")
	return None, None, None


@frappe.whitelist(allow_guest=False)
def validate():
	"""Validate a customer reference before a payment is initiated."""
	data = frappe.form_dict
	customer_ref = data.get("customerRef")

	if not customer_ref:
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["message"] = "Missing required field: customerRef"
		frappe.response["customerName"] = ""
		frappe.response["customerRef"] = ""
		return

	try:
		customer_name = frappe.db.get_value("Customer", customer_ref, "customer_name")
		if customer_name:
			frappe.response["http_status_code"] = 200
			frappe.response["resultCode"] = 0
			frappe.response["message"] = "Customer found"
			frappe.response["customerName"] = customer_name
			frappe.response["customerRef"] = customer_ref
		else:
			frappe.response["http_status_code"] = 404
			frappe.response["resultCode"] = 1
			frappe.response["message"] = "Customer not found"
			frappe.response["customerName"] = ""
			frappe.response["customerRef"] = ""
	except Exception:
		frappe.log_error(frappe.get_traceback(), "IM Bank Business Connect – validate error")
		frappe.response["http_status_code"] = 500
		frappe.response["resultCode"] = 1
		frappe.response["message"] = "An unexpected error occurred while processing the request. Please try again later."
		frappe.response["customerName"] = ""
		frappe.response["customerRef"] = ""


@frappe.whitelist(allow_guest=False)
def payment():
	"""Receive and record an incoming payment from I&M Bank Business Connect."""
	data = frappe.form_dict
	additions = data.get("additions", {})
	if isinstance(additions, str):
		additions = json.loads(additions)

	# Validate required top-level fields
	required = ["paymentType", "transactionReference", "transactionDate", "amount", "currency", "shortCode"]
	missing = [f for f in required if not data.get(f)]
	if not additions.get("externalRefNumber"):
		missing.append("additions.externalRefNumber")

	if missing:
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Missing required fields: {', '.join(missing)}"
		frappe.response["erpRefId"] = None
		return

	# Validate amount
	try:
		amount = float(data["amount"])
		if amount <= 0:
			raise ValueError
	except (ValueError, TypeError):
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Invalid amount: {data.get('amount')}"
		frappe.response["erpRefId"] = None
		return

	# Duplicate transaction reference check
	if frappe.db.exists("IM Bank Transaction", {"transaction_reference": data["transactionReference"]}):
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Duplicate transactionReference: {data['transactionReference']}"
		frappe.response["erpRefId"] = None
		return

	# Resolve customer, enforcing strict/non-strict validation mode
	customer_ref = additions.get("customerRef", "")
	customer = None
	if customer_ref:
		customer = frappe.db.get_value("Customer", customer_ref, "name")

	validation_mode = frappe.db.get_single_value("Bank Integration Settings", "validation_mode") or "Non-strict"
	if validation_mode == "Strict" and customer_ref and not customer:
		frappe.response["http_status_code"] = 404
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Customer not found for ref: {customer_ref}"
		frappe.response["erpRefId"] = None
		return

	# Resolve company/account/mode_of_payment from Bank Integration Settings
	company, bank_account, mode_of_payment = _resolve_account_mapping(
		data.get("shortCode"), data.get("paymentType")
	)

	try:
		doc = frappe.get_doc({
			"doctype": "IM Bank Transaction",
			"source": "Business Connect",
			"payment_type": data.get("paymentType"),
			"transaction_reference": data.get("transactionReference"),
			"transaction_date": data.get("transactionDate"),
			"amount": amount,
			"currency": data.get("currency"),
			"short_code": data.get("shortCode"),
			"customer_ref": customer_ref,
			"customer": customer,
			"company": company,
			"account": bank_account,
			"mode_of_payment": mode_of_payment,
			"external_ref_number": additions.get("externalRefNumber"),
			"payer_name": additions.get("payerName"),
			"payer_mobile_number": additions.get("payerMobileNumber"),
			"sender_bank_code": additions.get("senderBankCode"),
			"sender_account_number": additions.get("senderAccountNumber"),
			"sender_account_name": additions.get("senderAccountName"),
			"sender_address": additions.get("senderAddress"),
			"cheque_number": additions.get("chequeNumber"),
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.response["http_status_code"] = 200
		frappe.response["resultCode"] = 0
		frappe.response["resultDesc"] = "Payment received successfully"
		frappe.response["erpRefId"] = doc.name
	except Exception:
		frappe.log_error(frappe.get_traceback(), "IM Bank Business Connect – payment error")
		frappe.response["http_status_code"] = 500
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = "Internal server error, please try again later"
		frappe.response["erpRefId"] = None


@frappe.whitelist(allow_guest=False)
def ipn():
	"""Receive and record an I&M Bank Instant Payment Notification."""
	data = frappe.request.get_json(force=True) or {}

	# Validate required fields
	required = ["transactionReference", "transactionDate", "channel", "currency", "amount", "accountNumber", "transactionType"]
	missing = [f for f in required if not str(data.get(f, "")).strip()]
	if missing:
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Missing required fields: {', '.join(missing)}"
		frappe.response["erpRefId"] = None
		return

	# Validate amount
	try:
		amount = float(data["amount"])
		if amount <= 0:
			raise ValueError
	except (ValueError, TypeError):
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Invalid amount: {data.get('amount')}"
		frappe.response["erpRefId"] = None
		return

	# Validate transactionType
	transaction_type = str(data.get("transactionType", "")).upper()
	if transaction_type not in ("D", "C"):
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = "transactionType must be 'D' or 'C'"
		frappe.response["erpRefId"] = None
		return

	# Duplicate transaction reference check
	if frappe.db.exists("IM Bank Transaction", {"transaction_reference": data["transactionReference"]}):
		frappe.response["http_status_code"] = 400
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = f"Duplicate transactionReference: {data['transactionReference']}"
		frappe.response["erpRefId"] = None
		return

	# Resolve company/account/mode_of_payment — accountNumber serves as the short_code lookup key
	company, bank_account, mode_of_payment = _resolve_account_mapping(
		data.get("accountNumber"), data.get("channel")
	)

	try:
		doc = frappe.get_doc({
			"doctype": "IM Bank Transaction",
			"source": "IPN",
			"payment_type": data.get("channel"),
			"transaction_reference": data.get("transactionReference"),
			"transaction_date": _parse_datetime(data.get("transactionDate")),
			"amount": amount,
			"currency": data.get("currency"),
			"short_code": data.get("accountNumber"),
			"transaction_type": transaction_type,
			"transaction_particular": data.get("transactionParticular"),
			"company": company,
			"account": bank_account,
			"mode_of_payment": mode_of_payment,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.response["http_status_code"] = 200
		frappe.response["resultCode"] = 0
		frappe.response["resultDesc"] = "Successful"
		frappe.response["erpRefId"] = doc.name
	except Exception:
		frappe.log_error(frappe.get_traceback(), "IM Bank Business Connect – ipn error")
		frappe.response["http_status_code"] = 500
		frappe.response["resultCode"] = 1
		frappe.response["resultDesc"] = "Internal server error, please try again later"
		frappe.response["erpRefId"] = None
