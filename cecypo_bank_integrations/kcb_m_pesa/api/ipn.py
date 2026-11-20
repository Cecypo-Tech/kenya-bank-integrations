"""
KCB M-Pesa (BUNI) — Instant Payment Notification (IPN) endpoints.

Endpoints (called by KCB):
  POST /api/method/cecypo_bank_integrations.kcb_m_pesa.api.ipn.till_notification
  POST /api/method/cecypo_bank_integrations.kcb_m_pesa.api.ipn.account_notification
  POST /api/method/cecypo_bank_integrations.kcb_m_pesa.api.ipn.validate_payment

All guest, rate-limited to 60 requests/60s, and never return HTTP 5xx to KCB.
"""

import json
from datetime import datetime

import frappe
from dateutil import parser as date_parser
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from cecypo_bank_integrations.kcb_m_pesa.utils import get_settings, resolve_account_mapping, verify_signature


def _parse_till_timestamp(value):
	"""KCB sends till IPN dates like 'Mon May 19 13:30:54 EAT 2025'."""
	if not value:
		return None
	try:
		return date_parser.parse(value, fuzzy=True).strftime("%Y-%m-%d %H:%M:%S")
	except (ValueError, OverflowError):
		return None


def _parse_account_timestamp(value):
	"""KCB sends account IPN timestamps like '202111110305' (YYYYMMDDHHMM)."""
	if not value:
		return None
	try:
		return datetime.strptime(str(value), "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M:00")
	except ValueError:
		return None


def _till_ack(header, transaction_ref):
	frappe.response["http_status_code"] = 200
	frappe.response["header"] = {
		"messageID": header.get("messageID"),
		"originatorConversationID": header.get("originatorConversationID"),
		"statusCode": "0",
		"statusMessage": "Notification received successfully",
	}
	frappe.response["responsePayload"] = {"transactionInfo": {"transactionId": transaction_ref}}


def _account_ack(transaction_ref):
	frappe.response["http_status_code"] = 200
	frappe.response["transactionID"] = transaction_ref
	frappe.response["statusCode"] = "0"
	frappe.response["statusMessage"] = "Notification received successfully"


@frappe.whitelist(allow_guest=True)
@rate_limit(key="kcb_till_ipn", limit=60, seconds=60)
def till_notification():
	"""Receive a Till IPN (Vooma till / Lipa Na KCB till) from KCB BUNI."""
	raw_body = frappe.request.get_data()
	signature = frappe.get_request_header("Signature")

	try:
		body = json.loads(raw_body or b"{}")
	except ValueError:
		body = {}

	header = body.get("header", {}) or {}
	primary_data = (body.get("requestPayload", {}) or {}).get("primaryData", {}) or {}
	notification_data = (
		(body.get("requestPayload", {}) or {}).get("additionalData", {}) or {}
	).get("notificationData", {}) or {}

	transaction_id = notification_data.get("transactionID")

	try:
		settings = get_settings()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: Till IPN settings error")
		_till_ack(header, transaction_id or "")
		return

	existing = frappe.db.exists("KCB M-Pesa IPN Transaction", {"transaction_id": transaction_id})
	if existing:
		_till_ack(header, existing)
		return

	signature_verified = bool(signature) and verify_signature(raw_body, signature, settings)
	if not signature_verified:
		frappe.logger("kcb_buni").warning(f"KCB BUNI: Till IPN signature invalid for transaction {transaction_id}")

	company, bank_account = resolve_account_mapping(primary_data.get("businessKey"))

	full_name = " ".join(
		filter(
			None,
			[
				notification_data.get("firstName"),
				notification_data.get("middleName"),
				notification_data.get("lastName"),
			],
		)
	)

	try:
		doc = frappe.get_doc({
			"doctype": "KCB M-Pesa IPN Transaction",
			"transaction_id": transaction_id,
			"transaction_type": "Till IPN",
			"status": "Received" if signature_verified else "Failed",
			"signature_verified": 1 if signature_verified else 0,
			"received_at": frappe.utils.now_datetime(),
			"raw_payload": raw_body.decode("utf-8", errors="replace"),
			"amount": flt(notification_data.get("transactionAmt")),
			"currency": notification_data.get("currency") or "KES",
			"transaction_date": _parse_till_timestamp(notification_data.get("transactionDate")),
			"narration": notification_data.get("narration"),
			"customer_name": full_name or None,
			"debit_msisdn": notification_data.get("debitMSISDN"),
			"message_id": header.get("messageID"),
			"originator_conversation_id": header.get("originatorConversationID"),
			"channel_code": header.get("channelCode"),
			"business_key": primary_data.get("businessKey"),
			"business_key_type": primary_data.get("businessKeyType"),
			"organization_short_code": notification_data.get("organizationShortCode"),
			"till_number": primary_data.get("businessKey"),
			"balance": notification_data.get("balance"),
			"company": company,
			"paid_to_account": bank_account,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		_till_ack(header, doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: Till IPN error")
		_till_ack(header, transaction_id or "")


@frappe.whitelist(allow_guest=True)
@rate_limit(key="kcb_account_ipn", limit=60, seconds=60)
def account_notification():
	"""Receive an Account IPN (KCB bank account payment) from KCB BUNI."""
	raw_body = frappe.request.get_data()
	signature = frappe.get_request_header("Signature")

	try:
		body = json.loads(raw_body or b"{}")
	except ValueError:
		body = {}

	transaction_id = body.get("transactionReference")

	try:
		settings = get_settings()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: Account IPN settings error")
		_account_ack(transaction_id or "")
		return

	existing = frappe.db.exists("KCB M-Pesa IPN Transaction", {"transaction_id": transaction_id})
	if existing:
		_account_ack(existing)
		return

	signature_verified = bool(signature) and verify_signature(raw_body, signature, settings)
	if not signature_verified:
		frappe.logger("kcb_buni").warning(f"KCB BUNI: Account IPN signature invalid for transaction {transaction_id}")

	company, bank_account = resolve_account_mapping(body.get("creditAccountIdentifier"))

	try:
		doc = frappe.get_doc({
			"doctype": "KCB M-Pesa IPN Transaction",
			"transaction_id": transaction_id,
			"transaction_type": "Account IPN",
			"status": "Received" if signature_verified else "Failed",
			"signature_verified": 1 if signature_verified else 0,
			"received_at": frappe.utils.now_datetime(),
			"raw_payload": raw_body.decode("utf-8", errors="replace"),
			"amount": flt(body.get("transactionAmount")),
			"currency": body.get("currency") or "KES",
			"transaction_date": _parse_account_timestamp(body.get("timestamp")),
			"narration": body.get("narration"),
			"customer_name": body.get("customerName"),
			"customer_mobile": body.get("customerMobileNumber"),
			"customer_reference": body.get("customerReference"),
			"message_id": body.get("requestId"),
			"channel_code": body.get("channelCode"),
			"credit_account_identifier": body.get("creditAccountIdentifier"),
			"organization_short_code": body.get("organizationShortCode"),
			"till_number": body.get("tillNumber"),
			"balance": body.get("balance"),
			"transaction_reference": body.get("transactionReference"),
			"company": company,
			"paid_to_account": bank_account,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		_account_ack(doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "KCB BUNI: Account IPN error")
		_account_ack(transaction_id or "")


@frappe.whitelist(allow_guest=True)
@rate_limit(key="kcb_validation", limit=60, seconds=60)
def validate_payment():
	"""OTC/Agency validation stub — not yet implemented (pending feature per source spec §2.2.4)."""
	frappe.logger("kcb_buni").info("KCB BUNI: validate_payment stub called")
	frappe.response["http_status_code"] = 200
	frappe.response["statusCode"] = "1"
	frappe.response["statusMessage"] = "Validation not yet implemented"
