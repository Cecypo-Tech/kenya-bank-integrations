"""
KCB M-Pesa (BUNI) — outbound STK Push (Lipa Na M-Pesa Online).

Desk endpoint:
  POST /api/method/cecypo_bank_integrations.kcb_m_pesa.api.stk_push.initiate_stk_push

Callback endpoint (called by M-Pesa):
  POST /api/method/cecypo_bank_integrations.kcb_m_pesa.api.stk_push.mpesa_callback
"""

import re
import uuid
from datetime import datetime

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit

from cecypo_bank_integrations.kcb_m_pesa.utils import get_access_token, get_base_url, get_settings

_PHONE_RE = re.compile(r"^2547\d{8}$")


def _validate_stk_inputs(phone_number, amount, invoice_number, transaction_description):
	if not _PHONE_RE.match(phone_number or ""):
		frappe.throw(_("Phone number must be in the format 2547XXXXXXXX."))
	if not re.match(r"^\d+$", str(amount or "")):
		frappe.throw(_("Amount must be a whole number with no decimals."))
	if int(amount) <= 0:
		frappe.throw(_("Amount must be greater than zero."))
	if len(invoice_number or "") > 12:
		frappe.throw(_("Invoice number must be 12 characters or fewer."))
	if len(transaction_description or "") > 13:
		frappe.throw(_("Transaction description must be 13 characters or fewer."))


@frappe.whitelist()
def initiate_stk_push(
	phone_number, amount, invoice_number, transaction_description, party_type=None, party=None, company=None
):
	"""Send an STK Push (Lipa Na M-Pesa Online) request via KCB BUNI. Desk-only."""
	settings = get_settings()
	_validate_stk_inputs(phone_number, amount, invoice_number, transaction_description)

	message_id = uuid.uuid4().hex

	body = {
		"phoneNumber": phone_number,
		"amount": amount,
		"invoiceNumber": invoice_number,
		"sharedShortCode": bool(settings.shared_short_code),
		"orgShortCode": settings.org_short_code or "",
		"orgPassKey": settings.get_password("org_pass_key") or "",
		"callbackUrl": settings.stk_callback_url,
		"transactionDescription": transaction_description,
	}

	doc = frappe.get_doc({
		"doctype": "KCB M-Pesa STK Push Request",
		"status": "Initiated",
		"phone_number": phone_number,
		"amount": amount,
		"invoice_number": invoice_number,
		"transaction_description": transaction_description,
		"message_id": message_id,
		"raw_request": frappe.as_json({**body, "orgPassKey": "***"}),
		"initiated_at": frappe.utils.now_datetime(),
		"party_type": party_type,
		"party": party,
		"company": company,
	})
	doc.insert(ignore_permissions=True)

	try:
		token = get_access_token(settings)
		headers = {
			"Access-Control-Allow-Origin": "*",
			"messageId": message_id,
			"operation": "STKPush",
			"routeCode": settings.route_code,
			"Authorization": f"Bearer {token}",
			"Content-Type": "application/json",
		}
		response = requests.post(
			f"{get_base_url(settings)}/mm/api/request/1.0.0/stkpush", json=body, headers=headers, timeout=15
		)
		response_json = response.json()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: STK Push request error")
		doc.db_set("status", "Failed")
		frappe.throw(_("Failed to reach KCB M-Pesa. See the error log for details."))

	doc.db_set("raw_response", frappe.as_json(response_json))
	resp = response_json.get("response", {}) or {}

	if (
		response.status_code == 200
		and (response_json.get("header") or {}).get("statusCode") == "0"
		and resp.get("ResponseCode") == 0
	):
		doc.db_set("status", "Pending")
		doc.db_set("merchant_request_id", resp.get("MerchantRequestID"))
		doc.db_set("checkout_request_id", resp.get("CheckoutRequestID"))
		doc.db_set("customer_message", resp.get("CustomerMessage"))
		doc.db_set("response_code", resp.get("ResponseCode"))
		doc.db_set("response_description", resp.get("ResponseDescription"))
	else:
		doc.db_set("status", "Failed")
		doc.db_set("response_code", resp.get("ResponseCode"))
		doc.db_set(
			"response_description",
			resp.get("ResponseDescription") or (response_json.get("header") or {}).get("statusDescription"),
		)
		frappe.log_error(frappe.as_json(response_json), "KCB BUNI: STK Push failed")

	return {"stk_request": doc.name, "message": _("STK Push sent to {0}").format(phone_number)}


def _parse_mpesa_timestamp(value):
	"""M-Pesa TransactionDate callback item is YYYYMMDDHHMMSS, e.g. 20250519133054."""
	if not value:
		return None
	try:
		return datetime.strptime(str(value), "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
	except ValueError:
		return None


@frappe.whitelist(allow_guest=True)
@rate_limit(key="kcb_mpesa_callback", limit=60, seconds=60)
def mpesa_callback():
	"""Receive the M-Pesa STK Push result callback. Always acks HTTP 200 (M-Pesa retries otherwise)."""
	try:
		raw_body = frappe.request.get_data(as_text=True)
		body = frappe.parse_json(raw_body) or {}
		callback = ((body.get("Body") or {}).get("stkCallback")) or {}
		checkout_request_id = callback.get("CheckoutRequestID")

		stk_name = frappe.db.get_value(
			"KCB M-Pesa STK Push Request", {"checkout_request_id": checkout_request_id}
		)
		if not stk_name:
			frappe.logger("kcb_buni").warning(
				f"KCB BUNI: STK callback for unknown CheckoutRequestID {checkout_request_id}"
			)
		else:
			stk_doc = frappe.get_doc("KCB M-Pesa STK Push Request", stk_name)
			stk_doc.db_set("callback_payload", raw_body)
			stk_doc.db_set("completed_at", frappe.utils.now_datetime())

			if callback.get("ResultCode") == 0:
				items = {
					item.get("Name"): item.get("Value")
					for item in ((callback.get("CallbackMetadata") or {}).get("Item") or [])
				}
				stk_doc.db_set("status", "Success")

				ipn_doc = frappe.get_doc({
					"doctype": "KCB M-Pesa IPN Transaction",
					"transaction_id": items.get("MpesaReceiptNumber") or checkout_request_id,
					"transaction_type": "STK Push Callback",
					"status": "Received",
					"signature_verified": 1,
					"received_at": frappe.utils.now_datetime(),
					"raw_payload": raw_body,
					"amount": items.get("Amount"),
					"currency": stk_doc.currency,
					"transaction_date": _parse_mpesa_timestamp(items.get("TransactionDate")),
					"customer_mobile": items.get("PhoneNumber"),
					"stk_push_request": stk_doc.name,
					"checkout_request_id": checkout_request_id,
					"party_type": stk_doc.party_type,
					"party": stk_doc.party,
					"company": stk_doc.company,
				})
				ipn_doc.insert(ignore_permissions=True)
				stk_doc.db_set("linked_ipn_transaction", ipn_doc.name)
			else:
				stk_doc.db_set("status", "Failed")

			frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: STK callback error")

	frappe.response["http_status_code"] = 200
	frappe.response["ResultCode"] = 0
	frappe.response["ResultDesc"] = "Accepted"
