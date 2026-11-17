// Copyright (c) 2026, Clothing ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("ASM Visit Obligation", {
	refresh(frm) {
		if (frm.doc.status === "Open" && frm.doc.customer) {
			frm.add_custom_button(__("Record Retailer Visit"), () => {
				frappe.new_doc("Retailer Visit", {
					customer: frm.doc.customer,
					visit_type: frm.doc.obligation_type === "Quarterly Stock Review"
						? "Stock Review"
						: (frm.doc.obligation_type === "Monthly Sample & Order" ? "Sample & Order Taking" : "General Visit"),
				});
			});
		}
	},
});
