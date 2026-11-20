import frappe
from frappe import _
from frappe.model.document import Document


class DTBIPNTransaction(Document):
	def before_insert(self):
		self.status = "Pending"

	def before_submit(self):
		if not self.company or not self.account:
			frappe.throw(
				_(
					"Company and Bank Account are not set on this transaction. "
					"Configure a DTB Account Mapping in Bank Integration Settings for account number {0}."
				).format(self.account_number)
			)
		if self.is_internal_transfer:
			if not self.paid_from or not self.paid_to:
				frappe.throw(_("Paid From and Paid To accounts are required for an internal transfer."))
		elif self.debit_credit_indicator == "D":
			if not self.supplier:
				frappe.throw(_("Supplier is required before submission."))
		else:
			if not self.customer:
				frappe.throw(_("Customer is required before submission."))

	def on_submit(self):
		if not self.payment_entry:
			self.create_payment_entry()

	@frappe.whitelist()
	def create_payment_entry(self):
		if self.payment_entry:
			frappe.throw(
				_("Payment Entry {0} already exists for this transaction.").format(self.payment_entry)
			)

		if not self.company or not self.account:
			frappe.throw(
				_(
					"Company and Bank Account are not set. "
					"Configure a DTB Account Mapping in Bank Integration Settings for account number {0}."
				).format(self.account_number)
			)

		try:
			amount = float(self.amount)
		except (ValueError, TypeError):
			frappe.throw(_("Invalid amount: {0}").format(self.amount))

		common = {
			"doctype": "Payment Entry",
			"company": self.company,
			"paid_amount": amount,
			"received_amount": amount,
			"mode_of_payment": self.mode_of_payment or None,
			"paid_from_account_currency": self.currency or "KES",
			"reference_no": self.xref or self.cbs_reference,
			"reference_date": frappe.utils.nowdate(),
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
		}

		if self.is_internal_transfer:
			if not self.paid_from or not self.paid_to:
				frappe.throw(_("Paid From and Paid To accounts are required for an internal transfer."))
			pe = frappe.get_doc({
				**common,
				"payment_type": "Internal Transfer",
				"paid_from": self.paid_from,
				"paid_to": self.paid_to,
			})
		elif self.debit_credit_indicator == "D":
			if not self.supplier:
				frappe.throw(_("Supplier is required before creating a Payment Entry."))
			pe = frappe.get_doc({
				**common,
				"payment_type": "Pay",
				"party_type": "Supplier",
				"party": self.supplier,
				"paid_from": self.account,
			})
		else:
			if not self.customer:
				frappe.throw(_("Customer is required before creating a Payment Entry."))
			pe = frappe.get_doc({
				**common,
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": self.customer,
				"paid_to": self.account,
			})

		pe.insert(ignore_permissions=True)

		if self.submit_payment:
			pe.submit()

		self.db_set("payment_entry", pe.name)
		self.db_set("status", "Processed")

		return pe.name
