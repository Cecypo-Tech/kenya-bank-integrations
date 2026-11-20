import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestKCBMPesaPaymentEntry(FrappeTestCase):
	def setUp(self):
		self.company = self._get_test_company()
		self.bank_account = frappe.db.get_value(
			"Account", {"account_type": "Bank", "company": self.company, "is_group": 0}, "name"
		)
		self.customer = frappe.db.get_value("Customer", {}, "name") or self._make_customer()
		self.supplier = frappe.db.get_value("Supplier", {}, "name") or self._make_supplier()

	def _get_test_company(self):
		# Some companies on this dev site (e.g. the arbitrary first Company row) have no
		# active Fiscal Year covering today, which breaks Payment Entry submission/GL
		# posting. Prefer a company that has a Bank account and valid Fiscal Year coverage.
		for company in frappe.get_all("Company", pluck="name"):
			has_bank_account = frappe.db.exists(
				"Account", {"account_type": "Bank", "company": company, "is_group": 0}
			)
			if not has_bank_account:
				continue
			if get_fiscal_year(today(), company=company, raise_on_missing=False, verbose=0):
				return company
		return frappe.db.get_value("Company", {}, "name")

	def _make_customer(self):
		doc = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "KCB Test Customer",
			"customer_group": frappe.db.get_value("Customer Group", {}, "name"),
			"territory": frappe.db.get_value("Territory", {}, "name"),
		})
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_supplier(self):
		doc = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": "KCB Test Supplier",
			"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
		})
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_txn(self, **kwargs):
		defaults = {
			"doctype": "KCB M-Pesa IPN Transaction",
			"transaction_id": frappe.generate_hash(length=12),
			"transaction_type": "Till IPN",
			"amount": 500,
			"currency": "KES",
			"company": self.company,
			"paid_to_account": self.bank_account,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": self.customer,
		}
		defaults.update(kwargs)
		doc = frappe.get_doc(defaults)
		doc.insert(ignore_permissions=True)
		return doc

	def test_create_payment_entry_receive(self):
		doc = self._make_txn(payment_type="Receive", party_type="Customer", party=self.customer)
		pe_name = doc.create_payment_entry()
		pe = frappe.get_doc("Payment Entry", pe_name)
		self.assertEqual(pe.payment_type, "Receive")
		self.assertEqual(pe.party_type, "Customer")
		self.assertEqual(pe.paid_to, self.bank_account)

	def test_create_payment_entry_pay(self):
		doc = self._make_txn(payment_type="Pay", party_type="Supplier", party=self.supplier)
		pe_name = doc.create_payment_entry()
		pe = frappe.get_doc("Payment Entry", pe_name)
		self.assertEqual(pe.payment_type, "Pay")
		self.assertEqual(pe.party_type, "Supplier")
		self.assertEqual(pe.paid_from, self.bank_account)

	def test_create_payment_entry_internal_transfer(self):
		other_bank_account = frappe.db.get_value(
			"Account",
			{"account_type": "Bank", "company": self.company, "is_group": 0, "name": ["!=", self.bank_account]},
			"name",
		) or self.bank_account
		doc = self._make_txn(payment_type="Internal Transfer", party=None, paid_from_account=other_bank_account)
		pe_name = doc.create_payment_entry()
		pe = frappe.get_doc("Payment Entry", pe_name)
		self.assertEqual(pe.payment_type, "Internal Transfer")
		self.assertEqual(pe.paid_from, other_bank_account)
		self.assertEqual(pe.paid_to, self.bank_account)

	def test_create_payment_entry_missing_party_raises(self):
		doc = self._make_txn(payment_type="Receive", party=None)
		with self.assertRaises(frappe.ValidationError):
			doc.create_payment_entry()

	def test_create_payment_entry_zero_amount_raises(self):
		doc = self._make_txn(amount=0)
		with self.assertRaises(frappe.ValidationError):
			doc.create_payment_entry()

	def test_paid_to_account_non_bank_raises(self):
		non_bank_account = frappe.db.get_value(
			"Account", {"account_type": ["!=", "Bank"], "company": self.company, "is_group": 0}, "name"
		)
		with self.assertRaises(frappe.ValidationError):
			self._make_txn(paid_to_account=non_bank_account)

	def test_cancel_submitted_transaction_cancels_payment_entry(self):
		doc = self._make_txn(payment_type="Receive", party_type="Customer", party=self.customer, submit_payment=1)
		doc.submit()
		pe_name = doc.payment_entry
		self.assertTrue(pe_name)
		pe = frappe.get_doc("Payment Entry", pe_name)
		self.assertEqual(pe.docstatus, 1)

		doc.cancel()
		pe.reload()
		self.assertEqual(pe.docstatus, 2)
