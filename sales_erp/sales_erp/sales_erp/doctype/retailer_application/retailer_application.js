frappe.ui.form.on("Retailer Application", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status !== "Pending") return;
		const can_review = frappe.user_roles.some((role) => ["Clothing Regional Sales Manager", "Clothing Business Administrator", "System Manager"].includes(role));
		if (!can_review) return;
		frm.add_custom_button(__("Approve"), async () => {
			await frappe.call({ method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.approve", type: "POST", args: { name: frm.doc.name }, freeze: true });
			await frm.reload_doc();
		}, __("Review"));
		frm.add_custom_button(__("Reject"), () => {
			frappe.prompt([{ fieldname: "reason", fieldtype: "Small Text", label: __("Rejection Reason"), reqd: 1 }], async ({ reason }) => {
				await frappe.call({ method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.reject", type: "POST", args: { name: frm.doc.name, reason }, freeze: true });
				await frm.reload_doc();
			}, __("Reject Retailer Application"), __("Reject"));
		}, __("Review"));
	},

	territory(frm) {
		if (!frm.doc.territory) {
			frm.set_value("salesperson", "");
			frm.set_value("rsm", "");
			return;
		}
		frappe.call({
			method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.get_territory_assignment",
			args: { territory: frm.doc.territory },
			callback(r) {
				if (r && r.message) {
					if (r.message.asm) {
						frm.set_value("salesperson", r.message.asm);
					}
					if (r.message.rsm) {
						frm.set_value("rsm", r.message.rsm);
					}
				}
			}
		});
	}
});
