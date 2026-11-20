import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class KCBMPesaIPNTransaction(Document):
	def validate(self):
		self._validate_bank_account("paid_to_account")
		self._validate_bank_account("paid_from_account")

	def _validate_bank_account(self, fieldname):
		account = self.get(fieldname)
		if not account:
			return
		account_type = frappe.db.get_value("Account", account, "account_type")
		if account_type != "Bank":
			frappe.throw(_("{0} must be a Bank type account.").format(self.meta.get_label(fieldname)))

	def on_submit(self):
		if not self.payment_entry:
			self.create_payment_entry()

	def on_cancel(self):
		if not self.payment_entry:
			return
		pe = frappe.get_doc("Payment Entry", self.payment_entry)
		if pe.docstatus == 1:
			pe.cancel()
		elif pe.docstatus == 0:
			pe.delete()

	@frappe.whitelist()
	def create_payment_entry(self):
		if self.payment_entry:
			frappe.throw(_("Payment Entry {0} already exists for this transaction.").format(self.payment_entry))

		try:
			amount = float(self.amount)
		except (ValueError, TypeError):
			amount = 0

		if amount <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if not self.paid_to_account:
			frappe.throw(_("Paid To Account (Bank) is required before creating a Payment Entry."))
		if self.payment_type != "Internal Transfer" and not self.party:
			frappe.throw(_("Party is required before creating a Payment Entry."))
		if self.payment_type == "Internal Transfer" and not self.paid_from_account:
			frappe.throw(_("Paid From Account is required for an Internal Transfer."))

		remarks = "\n".join(
			filter(None, [self.remarks, f"KCB Transaction ID: {self.transaction_id}", f"KCB IPN Doc: {self.name}"])
		)

		common = {
			"doctype": "Payment Entry",
			"company": self.company,
			"paid_amount": amount,
			"received_amount": amount,
			"mode_of_payment": "KCB M-Pesa",
			"paid_from_account_currency": self.currency or "KES",
			"paid_to_account_currency": self.currency or "KES",
			"reference_no": self.transaction_id,
			"reference_date": today(),
			"posting_date": today(),
			"cost_center": self.cost_center,
			"project": self.project,
			"remarks": remarks,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
		}

		if self.payment_type == "Internal Transfer":
			pe = frappe.get_doc({
				**common,
				"payment_type": "Internal Transfer",
				"paid_from": self.paid_from_account,
				"paid_to": self.paid_to_account,
			})
		elif self.payment_type == "Pay":
			pe = frappe.get_doc({
				**common,
				"payment_type": "Pay",
				"party_type": "Supplier",
				"party": self.party,
				"paid_from": self.paid_to_account,
			})
		else:
			pe = frappe.get_doc({
				**common,
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": self.party,
				"paid_to": self.paid_to_account,
			})

		pe.insert(ignore_permissions=True)

		if self.submit_payment:
			pe.submit()

		self.db_set("payment_entry", pe.name)
		self.db_set("status", "Payment Created")
		self.add_comment("Info", _("Payment Entry {0} created.").format(pe.name))

		return pe.name
