import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from cecypo_bank_integrations.kcb_m_pesa.api.stk_push import initiate_stk_push, mpesa_callback
from cecypo_bank_integrations.kcb_m_pesa.tests import FakeRequest

_TEST_CHECKOUT_IDS = ["ws_CO_TEST_SUCCESS", "ws_CO_TEST_FAIL", "ws_CO_DOES_NOT_EXIST"]
_TEST_TRANSACTION_IDS = ["NLJ7RT61SV"]


class TestKCBMPesaSTKPush(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Bank Integration Settings")
		self.settings.kcb_mpesa_enabled = 1
		self.settings.environment = "UAT"
		self.settings.uat_base_url = "https://uat.buni.kcbgroup.com"
		self.settings.client_id = "test-client"
		self.settings.client_secret = "test-secret"
		self.settings.org_short_code = "202020"
		self.settings.org_pass_key = "test-passkey"
		self.settings.shared_short_code = 1
		self.settings.route_code = "207"
		self.settings.stk_callback_url = "https://example.com/callback"
		self.settings.save()
		frappe.cache().delete_value("kcb_mpesa_access_token")
		self._cleanup_fixed_test_records()

	def tearDown(self):
		self._cleanup_fixed_test_records()

	def _cleanup_fixed_test_records(self):
		# initiate_stk_push/mpesa_callback call frappe.db.commit() (required for a
		# guest webhook, matching dtb/api/ipn.py's convention), which bypasses
		# FrappeTestCase's automatic per-test rollback — so records created under
		# these fixed literal identifiers must be deleted explicitly on both sides
		# of each test, not just relied on for automatic cleanup.
		frappe.db.delete("KCB M-Pesa IPN Transaction", {"transaction_id": ["in", _TEST_TRANSACTION_IDS]})
		frappe.db.delete("KCB M-Pesa STK Push Request", {"checkout_request_id": ["in", _TEST_CHECKOUT_IDS]})
		frappe.db.commit()

	def _mock_token(self):
		return mock.patch(
			"cecypo_bank_integrations.kcb_m_pesa.utils.requests.get",
			return_value=mock.Mock(
				json=lambda: {"access_token": "tok123", "expires_in": 3600},
				raise_for_status=lambda: None,
			),
		)

	def test_initiate_stk_push_success(self):
		success_response = mock.Mock(
			status_code=200,
			json=lambda: {
				"header": {"statusCode": "0", "statusDescription": "Success"},
				"response": {
					"MerchantRequestID": "16813-1590513-1",
					"CheckoutRequestID": "ws_CO_271020211535314658",
					"CustomerMessage": "Success. Request accepted for processing",
					"ResponseCode": 0,
					"ResponseDescription": "Accept the service request successfully.",
				},
			},
		)
		with self._mock_token(), mock.patch(
			"cecypo_bank_integrations.kcb_m_pesa.api.stk_push.requests.post", return_value=success_response
		):
			result = initiate_stk_push("254711000000", "1000", "INV001", "Invoice Pay")
		self.addCleanup(frappe.delete_doc, "KCB M-Pesa STK Push Request", result["stk_request"], force=True)

		doc = frappe.get_doc("KCB M-Pesa STK Push Request", result["stk_request"])
		self.assertEqual(doc.status, "Pending")
		self.assertEqual(doc.checkout_request_id, "ws_CO_271020211535314658")

	def test_initiate_stk_push_api_error(self):
		error_response = mock.Mock(
			status_code=200,
			json=lambda: {
				"header": {"statusCode": "1", "statusDescription": "Failed"},
				"response": {"ResponseCode": 1, "ResponseDescription": "Invalid request"},
			},
		)
		with self._mock_token(), mock.patch(
			"cecypo_bank_integrations.kcb_m_pesa.api.stk_push.requests.post", return_value=error_response
		):
			result = initiate_stk_push("254711000000", "1000", "INV001", "Invoice Pay")
		self.addCleanup(frappe.delete_doc, "KCB M-Pesa STK Push Request", result["stk_request"], force=True)

		doc = frappe.get_doc("KCB M-Pesa STK Push Request", result["stk_request"])
		self.assertEqual(doc.status, "Failed")

	def test_initiate_stk_push_invalid_phone(self):
		with self.assertRaises(frappe.ValidationError):
			initiate_stk_push("0711000000", "1000", "INV001", "Invoice Pay")

	def test_initiate_stk_push_decimal_amount(self):
		with self.assertRaises(frappe.ValidationError):
			initiate_stk_push("254711000000", "100.50", "INV001", "Invoice Pay")

	def test_mpesa_callback_success_creates_ipn_transaction(self):
		stk_doc = frappe.get_doc({
			"doctype": "KCB M-Pesa STK Push Request",
			"status": "Pending",
			"phone_number": "254711000000",
			"amount": 1000,
			"currency": "KES",
			"invoice_number": "INV002",
			"transaction_description": "Invoice Pay",
			"message_id": frappe.generate_hash(length=20),
			"checkout_request_id": "ws_CO_TEST_SUCCESS",
			"initiated_at": frappe.utils.now_datetime(),
		}).insert(ignore_permissions=True)

		payload = {
			"Body": {
				"stkCallback": {
					"MerchantRequestID": "16813-1590513-1",
					"CheckoutRequestID": "ws_CO_TEST_SUCCESS",
					"ResultCode": 0,
					"ResultDesc": "The service request is processed successfully.",
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": 1000},
							{"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
							{"Name": "TransactionDate", "Value": 20250519133054},
							{"Name": "PhoneNumber", "Value": 254711000000},
						]
					},
				}
			}
		}
		frappe.local.request = FakeRequest(json.dumps(payload).encode())
		frappe.local.request_ip = "127.0.0.1"

		mpesa_callback()

		stk_doc.reload()
		self.assertEqual(stk_doc.status, "Success")
		self.assertTrue(stk_doc.linked_ipn_transaction)

		ipn_doc = frappe.get_doc("KCB M-Pesa IPN Transaction", stk_doc.linked_ipn_transaction)
		self.assertEqual(ipn_doc.transaction_type, "STK Push Callback")
		self.assertEqual(ipn_doc.transaction_id, "NLJ7RT61SV")

	def test_mpesa_callback_failure_no_ipn_transaction(self):
		stk_doc = frappe.get_doc({
			"doctype": "KCB M-Pesa STK Push Request",
			"status": "Pending",
			"phone_number": "254711000000",
			"amount": 1000,
			"currency": "KES",
			"invoice_number": "INV003",
			"transaction_description": "Invoice Pay",
			"message_id": frappe.generate_hash(length=20),
			"checkout_request_id": "ws_CO_TEST_FAIL",
			"initiated_at": frappe.utils.now_datetime(),
		}).insert(ignore_permissions=True)

		payload = {
			"Body": {
				"stkCallback": {
					"MerchantRequestID": "16813-1590513-2",
					"CheckoutRequestID": "ws_CO_TEST_FAIL",
					"ResultCode": 1032,
					"ResultDesc": "Request cancelled by user.",
				}
			}
		}
		frappe.local.request = FakeRequest(json.dumps(payload).encode())
		frappe.local.request_ip = "127.0.0.1"

		mpesa_callback()

		stk_doc.reload()
		self.assertEqual(stk_doc.status, "Failed")
		self.assertFalse(stk_doc.linked_ipn_transaction)

	def test_mpesa_callback_unknown_checkout_id_still_acks(self):
		payload = {
			"Body": {
				"stkCallback": {
					"MerchantRequestID": "unknown",
					"CheckoutRequestID": "ws_CO_DOES_NOT_EXIST",
					"ResultCode": 0,
				}
			}
		}
		frappe.local.request = FakeRequest(json.dumps(payload).encode())
		frappe.local.request_ip = "127.0.0.1"

		mpesa_callback()

		self.assertEqual(frappe.response.get("ResultCode"), 0)
