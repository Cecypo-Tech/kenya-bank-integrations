import frappe
from frappe import _
from frappe.model.document import Document


class IMBankTransaction(Document):
	def before_insert(self):
		self.status = "Pending"

	def before_submit(self):
		if not self.customer:
			frappe.throw(_("Customer is required before submission."))
		if not self.account:
			frappe.throw(_("Bank Account is required before submission."))

	def on_submit(self):
		if not self.payment_entry:
			self.create_payment_entry()

	@frappe.whitelist()
	def create_payment_entry(self):
		if self.payment_entry:
			frappe.throw(_("Payment Entry {0} already exists for this transaction.").format(self.payment_entry))

		customer = self.customer
		if not customer and self.source == "Business Connect" and self.customer_ref:
			customer = frappe.db.get_value("Customer", self.customer_ref, "name")

		if not customer:
			frappe.throw(_("No customer linked. Set the Customer field before creating a Payment Entry."))

		company = self.company
		if not company:
			frappe.throw(_(
				"Company is not set on this transaction. "
				"Configure an Account Mapping in Bank Integration Settings."
			))

		if self.source == "Business Connect":
			ref_no = self.transaction_reference or self.external_ref_number
			ref_date = self.transaction_date or frappe.utils.nowdate()
		else:
			ref_no = self.mpesa_ref or self.trans_ref
			ref_date = self.posting_date or frappe.utils.nowdate()

		account = self.account
		if not account:
			frappe.throw(_(
				"Bank Account is required. "
				"Configure an Account Mapping in Bank Integration Settings."
			))

		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": customer,
			"company": company,
			"paid_amount": self.amount,
			"received_amount": self.amount,
			"paid_to": account,
			"mode_of_payment": self.mode_of_payment or None,
			"paid_from_account_currency": self.currency or "KES",
			"reference_no": ref_no,
			"reference_date": ref_date,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
		})
		pe.insert(ignore_permissions=True)

		if self.submit_payment:
			pe.submit()

		self.db_set("payment_entry", pe.name)
		self.db_set("status", "Processed")

		return pe.name
