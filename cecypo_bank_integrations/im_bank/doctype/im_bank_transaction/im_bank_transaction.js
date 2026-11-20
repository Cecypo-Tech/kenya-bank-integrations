// Copyright (c) 2026, Cecypo.Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("IM Bank Transaction", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("View Payment Entry"), () => {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}).addClass("btn-success");
			return;
		}

		// Check required fields for Payment Entry creation
		const missing = [];
		if (!frm.doc.company) missing.push(__("Company"));
		if (!frm.doc.account) missing.push(__("Bank Account"));
		if (!frm.doc.customer) missing.push(__("Customer"));

		if (missing.length) {
			frm.set_intro(
				__("Cannot create Payment Entry — missing: {0}. Configure Account Mappings in Bank Integration Settings.", [missing.join(", ")]),
				"red"
			);
			return;
		}

		if (!frm.doc.mode_of_payment) {
			const paymentType = frm.doc.payment_type || frm.doc.source;
			frm.set_intro(
				__("Mode of Payment is not set. Configure a Payment Type Mapping in Bank Integration Settings for \"{0}\".", [paymentType || "?"]),
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
});
