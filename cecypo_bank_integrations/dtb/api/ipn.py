"""
DTB (Diamond Trust Bank) – Instant Payment Notification (IPN)

Endpoint (called by DTB):
  POST /api/method/cecypo_bank_integrations.dtb.api.ipn.handle_ipn

No authentication required; DTB whitelists source IPs at the firewall level for production.

Response format (all codes):
  {"xref": "...", "user_reference": "...", "ack_code": "00", "ack_description": "..."}
"""

from datetime import datetime

import frappe


def _parse_date(value):
	"""Normalise YYYYMMDD, DD-Mon-YYYY, or YYYY-MM-DD to the YYYY-MM-DD format Frappe expects."""
	if not value:
		return value
	s = str(value).strip()
	if len(s) == 8 and s.isdigit():
		return f"{s[:4]}-{s[4:6]}-{s[6:]}"
	try:
		return datetime.strptime(s, "%d-%b-%Y").strftime("%Y-%m-%d")
	except ValueError:
		return s


# Required fields as per the DTB IPN spec
_REQUIRED_FIELDS = [
	"xref",
	"cbs_reference",
	"cbs_module",
	"account_number",
	"branch_code",
	"currency",
	"transaction_date",
	"value_date",
	"amount",
	"reversal_indicator",
	"debit_credit_indicator",
	"exchange_rate",
	"financial_year",
	"transaction_code",
	"transaction_description",
	"available_balance",
	"serial_number",
	"narration",
]


def _ack(xref, user_reference, ack_code, ack_description, http_status):
	frappe.response["http_status_code"] = http_status
	frappe.response["xref"] = xref or ""
	frappe.response["user_reference"] = user_reference
	frappe.response["ack_code"] = ack_code
	frappe.response["ack_description"] = ack_description


def _resolve_mappings(account_number, cbs_module):
	"""Look up DTB Account Mapping and CBS Module Mapping from Bank Integration Settings.

	Returns (company, bank_account, mode_of_payment) — any may be None if not configured.
	"""
	try:
		settings = frappe.get_single("Bank Integration Settings")
		account_map = next(
			(r for r in settings.dtb_account_mappings if r.account_number == account_number),
			None,
		)
		cbs_map = next(
			(r for r in settings.dtb_cbs_module_mappings if r.cbs_module == cbs_module),
			None,
		)
		return (
			account_map.company if account_map else None,
			account_map.bank_account if account_map else None,
			cbs_map.mode_of_payment if cbs_map else None,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "DTB IPN – _resolve_mappings error")
		return None, None, None


@frappe.whitelist(allow_guest=True)
def handle_ipn():
	"""Receive and record a DTB Instant Payment Notification."""
	# Parse JSON body (DTB sends Content-Type: application/json)
	data = frappe.request.get_json(force=True) or {}
	xref = data.get("xref") or ""
	user_ref = ""  # generated after successful insert

	# --- Validate required fields ---
	missing = [f for f in _REQUIRED_FIELDS if not str(data.get(f, "")).strip()]
	if missing:
		_ack(xref, user_ref, "11", f"Missing fields: {', '.join(missing)}", 400)
		return

	# Normalise _indicator fields to their canonical case before validation
	data["reversal_indicator"] = str(data["reversal_indicator"]).lower()
	data["debit_credit_indicator"] = str(data["debit_credit_indicator"]).upper()

	# --- Validate enum values ---
	if data["reversal_indicator"] not in ("y", "n"):
		_ack(xref, user_ref, "11", "reversal_indicator must be 'y' or 'n'", 400)
		return

	if data["debit_credit_indicator"] not in ("D", "C"):
		_ack(xref, user_ref, "11", "debit_credit_indicator must be 'D' or 'C'", 400)
		return

	# --- Duplicate xref check ---
	if frappe.db.exists("DTB IPN Transaction", {"xref": xref}):
		existing = frappe.db.get_value("DTB IPN Transaction", {"xref": xref}, "user_reference")
		_ack(xref, existing or user_ref, "12", "Duplicate XREF", 409)
		return

	# --- Resolve company/account/mode_of_payment from Bank Integration Settings ---
	company, bank_account, mode_of_payment = _resolve_mappings(
		data.get("account_number"), data.get("cbs_module")
	)

	# --- Persist the notification ---
	try:
		doc = frappe.get_doc({
			"doctype": "DTB IPN Transaction",
			"xref": xref,
			"cbs_reference": data.get("cbs_reference"),
			"cbs_module": data.get("cbs_module"),
			"account_number": data.get("account_number"),
			"branch_code": data.get("branch_code"),
			"currency": data.get("currency"),
			"transaction_date": _parse_date(data.get("transaction_date")),
			"value_date": _parse_date(data.get("value_date")),
			"amount": data.get("amount"),
			"reversal_indicator": data.get("reversal_indicator"),
			"debit_credit_indicator": data.get("debit_credit_indicator"),
			"exchange_rate": data.get("exchange_rate"),
			"financial_year": data.get("financial_year"),
			"transaction_code": data.get("transaction_code"),
			"transaction_description": data.get("transaction_description"),
			"virtual_pan": data.get("virtual_pan"),
			"rrn": data.get("rrn"),
			"customer_name": data.get("customer_name"),
			"customer_mobile": data.get("customer_mobile"),
			"available_balance": data.get("available_balance"),
			"serial_number": data.get("serial_number"),
			"narration": data.get("narration"),
			"company": company,
			"account": bank_account,
			"mode_of_payment": mode_of_payment,
		})
		doc.insert(ignore_permissions=True)

		# Build user_reference: "ERP" prefix + doc name (e.g. "ERPDTB-IPN-2026-00001")
		user_ref = ("ERP" + doc.name)[:32]
		doc.db_set("user_reference", user_ref)
		frappe.db.commit()

		_ack(xref, user_ref, "00", "Success", 200)

	except Exception:
		frappe.log_error(frappe.get_traceback(), "DTB IPN – handle_ipn error")
		_ack(xref, user_ref, "13", "Internal server error", 500)
