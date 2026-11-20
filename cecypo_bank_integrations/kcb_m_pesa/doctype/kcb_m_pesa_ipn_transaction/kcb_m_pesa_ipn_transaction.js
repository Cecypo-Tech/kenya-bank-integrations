// Copyright (c) 2026, Cecypo.Tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("KCB M-Pesa IPN Transaction", {
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
		if (!frm.doc.paid_to_account) missing.push(__("Paid To Account"));

		if (frm.doc.payment_type === "Internal Transfer") {
			if (!frm.doc.paid_from_account) missing.push(__("Paid From Account"));
		} else if (!frm.doc.party) {
			missing.push(__("Party"));
		}

		if (missing.length) {
			frm.set_intro(
				__("Cannot create Payment Entry — missing: {0}. Configure KCB M-Pesa Account Mappings in Bank Integration Settings.", [missing.join(", ")]),
				"red"
			);
			return;
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

	payment_type(frm) {
		frm.trigger("toggle_party_fields");
	},

	toggle_party_fields(frm) {
		const is_internal = frm.doc.payment_type === "Internal Transfer";
		frm.toggle_display("party_type", !is_internal);
		frm.toggle_display("party", !is_internal);
		frm.toggle_display("paid_from_account", is_internal);
	},
});
