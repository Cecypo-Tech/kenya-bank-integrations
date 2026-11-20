import base64
import json

import frappe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from frappe.tests.utils import FrappeTestCase

from cecypo_bank_integrations.kcb_m_pesa.api.ipn import (
	account_notification,
	till_notification,
	validate_payment,
)
from cecypo_bank_integrations.kcb_m_pesa.tests import FakeRequest

TILL_PAYLOAD = {
	"header": {
		"messageID": "12345",
		"originatorConversationID": "TEJ6CQQPBQ",
		"channelCode": "202",
		"timeStamp": "20250519133100",
	},
	"requestPayload": {
		"primaryData": {"businessKey": "1234567", "businessKeyType": "notifyBiller"},
		"additionalData": {
			"notificationData": {
				"businessKey": "1234567",
				"businessKeyType": "BillReferenceNumber",
				"debitMSISDN": "254711000000",
				"transactionAmt": "1000",
				"transactionDate": "Mon May 19 13:30:54 EAT 2025",
				"transactionID": "FT25139M3RM6",
				"firstName": "PETER BOR",
				"middleName": "",
				"lastName": "",
				"currency": "KES",
				"narration": "School Fees",
				"transactionType": "MPESA",
				"balance": "0",
			}
		},
	},
}

ACCOUNT_PAYLOAD = {
	"transactionReference": "FT000262556",
	"requestId": "12345",
	"channelCode": "202",
	"timestamp": "202111110305",
	"transactionAmount": "1000",
	"currency": "KES",
	"customerReference": "REF001",
	"customerName": "Peter Bor",
	"customerMobileNumber": "254711000000",
	"balance": "0",
	"narration": "School Fees",
	"creditAccountIdentifier": "1234567890",
	"organizationShortCode": "202",
	"tillNumber": "202",
}


def _keypair():
	private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	public_pem = private_key.public_key().public_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PublicFormat.SubjectPublicKeyInfo,
	).decode()
	return private_key, public_pem


def _sign(private_key, body_bytes):
	signature = private_key.sign(body_bytes, padding.PKCS1v15(), hashes.SHA256())
	return base64.b64encode(signature).decode()


class TestKCBMPesaIPN(FrappeTestCase):
	def setUp(self):
		self.private_key, public_pem = _keypair()
		self.settings = frappe.get_single("Bank Integration Settings")
		self.settings.kcb_mpesa_enabled = 1
		self.settings.kcb_public_key = public_pem
		self.settings.save()
		self._cleanup_fixed_test_records()
		self._orig_get_request_header = frappe.get_request_header

	def tearDown(self):
		frappe.get_request_header = self._orig_get_request_header
		self._cleanup_fixed_test_records()

	def _cleanup_fixed_test_records(self):
		# till_notification/account_notification call frappe.db.commit() (required
		# for a guest webhook, matching dtb/api/ipn.py's convention), which can
		# make an insert permanent mid-test. A delete without a following commit
		# here can be silently undone by FrappeTestCase's own end-of-test
		# rollback, resurrecting the already-committed row — so this cleanup
		# must commit its own delete, not just issue it.
		frappe.db.delete("KCB M-Pesa IPN Transaction", {"transaction_id": ["in", ["FT25139M3RM6", "FT000262556"]]})
		frappe.db.commit()

	def _post(self, payload, signed=True):
		body_bytes = json.dumps(payload).encode()
		frappe.local.request = FakeRequest(body_bytes)
		# used by frappe.rate_limiter.rate_limit (see frappe/core/doctype/user/test_user.py)
		frappe.local.request_ip = "127.0.0.1"
		signature = _sign(self.private_key, body_bytes) if signed else None
		headers = {"Signature": signature} if signature else {}
		frappe.get_request_header = lambda key, default=None: headers.get(key, default)

	def test_till_notification_creates_doc(self):
		self._post(TILL_PAYLOAD)
		till_notification()

		doc = frappe.get_doc("KCB M-Pesa IPN Transaction", {"transaction_id": "FT25139M3RM6"})
		self.assertEqual(doc.transaction_type, "Till IPN")
		self.assertEqual(doc.status, "Received")
		self.assertEqual(doc.signature_verified, 1)
		self.assertEqual(doc.amount, 1000)
		self.assertEqual(doc.customer_name, "PETER BOR")

	def test_till_notification_duplicate_returns_existing(self):
		self._post(TILL_PAYLOAD)
		till_notification()
		count_after_first = frappe.db.count("KCB M-Pesa IPN Transaction", {"transaction_id": "FT25139M3RM6"})

		self._post(TILL_PAYLOAD)
		till_notification()
		count_after_second = frappe.db.count("KCB M-Pesa IPN Transaction", {"transaction_id": "FT25139M3RM6"})

		self.assertEqual(count_after_first, 1)
		self.assertEqual(count_after_second, 1)

	def test_account_notification_creates_doc(self):
		self._post(ACCOUNT_PAYLOAD)
		account_notification()

		doc = frappe.get_doc("KCB M-Pesa IPN Transaction", {"transaction_id": "FT000262556"})
		self.assertEqual(doc.transaction_type, "Account IPN")
		self.assertEqual(doc.amount, 1000)
		self.assertEqual(doc.customer_mobile, "254711000000")

	def test_account_notification_duplicate_returns_existing(self):
		self._post(ACCOUNT_PAYLOAD)
		account_notification()
		count_after_first = frappe.db.count("KCB M-Pesa IPN Transaction", {"transaction_id": "FT000262556"})

		self._post(ACCOUNT_PAYLOAD)
		account_notification()
		count_after_second = frappe.db.count("KCB M-Pesa IPN Transaction", {"transaction_id": "FT000262556"})

		self.assertEqual(count_after_first, 1)
		self.assertEqual(count_after_second, 1)

	def test_validate_payment_stub(self):
		validate_payment()
		self.assertEqual(frappe.response.get("statusCode"), "1")
		self.assertEqual(frappe.response.get("statusMessage"), "Validation not yet implemented")
