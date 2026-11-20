// Copyright (c) 2026, Cecypo.Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("DTB IPN Transaction", {
	refresh(frm) {
		frm.trigger("toggle_party_fields");

		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("View Payment Entry"), () => {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}).addClass("btn-success");
			return;
		}

		const missing = [];
		if (!frm.doc.company) missing.push(__("Company"));
		if (!frm.doc.account) missing.push(__("CoA Account"));

		if (frm.doc.is_internal_transfer) {
			if (!frm.doc.paid_from) missing.push(__("Paid From"));
			if (!frm.doc.paid_to) missing.push(__("Paid To"));
		} else if (frm.doc.debit_credit_indicator === "D") {
			if (!frm.doc.supplier) missing.push(__("Supplier"));
		} else {
			if (!frm.doc.customer) missing.push(__("Customer"));
		}

		if (missing.length) {
			frm.set_intro(
				__("Cannot create Payment Entry — missing: {0}. Configure DTB Account Mappings in Bank Integration Settings.", [missing.join(", ")]),
				"red"
			);
			return;
		}

		if (!frm.doc.mode_of_payment) {
			frm.set_intro(
				__("Mode of Payment is not set. Configure a CBS Module Mapping in Bank Integration Settings for CBS Module \"{0}\".", [frm.doc.cbs_module || "?"]),
				"yellow"
			);
		}

		frm.add_custom_button(__("Create Payment Entry"), () => {
			frappe.confirm(
				__("Create a Payment Entry for {0} {1}?", [frm.doc.currency || "KES", frm.doc.amount]),
				() => {
					frappe.call({
						method: "create_payment_entry",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Creating Payment Entry..."),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Payment Entry {0} created.", [
										`<a href="/app/payment-entry/${r.message}">${r.message}</a>`,
									]),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				}
			);
		}).addClass("btn-primary");
	},

	debit_credit_indicator(frm) {
		frm.trigger("toggle_party_fields");
	},

	is_internal_transfer(frm) {
		frm.trigger("toggle_party_fields");
	},

	toggle_party_fields(frm) {
		const is_internal = !!frm.doc.is_internal_transfer;
		const is_debit = frm.doc.debit_credit_indicator === "D";

		frm.toggle_display("customer", !is_internal && !is_debit);
		frm.toggle_display("supplier", !is_internal && is_debit);
		frm.toggle_display("paid_from", is_internal);
		frm.toggle_display("paid_to", is_internal);
	},
});
