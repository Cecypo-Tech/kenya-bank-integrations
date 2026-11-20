import json

import frappe
from frappe.tests.utils import FrappeTestCase

from cecypo_bank_integrations.dtb.api.ipn import handle_ipn
from cecypo_bank_integrations.dtb.tests import FakeRequest

# 30-char masked-PAN-style value DTB can send in place of a real MSISDN
LONG_CUSTOMER_MOBILE = "001100632026071313113913703343"

IPN_PAYLOAD = {
	"xref": "TESTXREF-CUSTMOBILE-30",
	"cbs_reference": "FT26195TEST01",
	"cbs_module": "FT",
	"account_number": "0000000000000",
	"branch_code": "001",
	"currency": "KES",
	"transaction_date": "20260714",
	"value_date": "20260714",
	"amount": "1000.00",
	"reversal_indicator": "n",
	"debit_credit_indicator": "C",
	"exchange_rate": "1",
	"financial_year": "2026",
	"transaction_code": "990",
	"transaction_description": "Funds Transfer",
	"available_balance": "1000.00",
	"serial_number": "1",
	"narration": "Test IPN with long customer mobile",
	"customer_name": "Test Customer",
	"customer_mobile": LONG_CUSTOMER_MOBILE,
}


class TestDTBIPN(FrappeTestCase):
	def setUp(self):
		self._cleanup_fixed_test_records()

	def tearDown(self):
		self._cleanup_fixed_test_records()

	def _cleanup_fixed_test_records(self):
		# handle_ipn calls frappe.db.commit() (required for a guest webhook), which
		# can make an insert permanent mid-test. A delete without a following commit
		# here can be silently undone by FrappeTestCase's own end-of-test rollback,
		# resurrecting the already-committed row — so this cleanup must commit its
		# own delete, not just issue it.
		frappe.db.delete("DTB IPN Transaction", {"xref": IPN_PAYLOAD["xref"]})
		frappe.db.commit()

	def _post(self, payload):
		frappe.local.request = FakeRequest(json.dumps(payload).encode())
		handle_ipn()

	def test_accepts_30_char_customer_mobile(self):
		self._post(IPN_PAYLOAD)

		self.assertEqual(frappe.response.get("ack_code"), "00")
		doc = frappe.get_doc("DTB IPN Transaction", {"xref": IPN_PAYLOAD["xref"]})
		self.assertEqual(doc.customer_mobile, LONG_CUSTOMER_MOBILE)
		self.assertEqual(len(doc.customer_mobile), 30)
