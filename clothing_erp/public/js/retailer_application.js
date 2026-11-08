function clothing_erp_is_salesperson_only() {
	const roles = new Set(frappe.user_roles || []);
	return roles.has("Clothing Salesperson")
		&& !["Administrator", "System Manager", "Clothing Sales Manager", "Clothing Business Administrator"]
			.some((role) => roles.has(role));
}

frappe.ui.form.on("Retailer Application", {
	setup(frm) {
		clothing_erp_scope_retailer_application(frm);
	},
	refresh(frm) {
		clothing_erp_scope_retailer_application(frm);
	},
});

function clothing_erp_scope_retailer_application(frm) {
	if (!clothing_erp_is_salesperson_only()) return;

	frm.set_df_property("salesperson", "read_only", 1);
	if (!frm.is_new()) return;

	if (!frm.doc.salesperson) {
		frm.set_value("salesperson", frappe.session.user);
	}
	if (!frm.doc.territory || !frm.doc.customer_group) {
		frappe.call({
			method: "clothing_erp.retailer_defaults.get_retailer_defaults",
			callback: (r) => {
				if (r.message) {
					if (!frm.doc.territory && r.message.territory) {
						frm.set_value("territory", r.message.territory);
					}
					if (!frm.doc.customer_group && r.message.customer_group) {
						frm.set_value("customer_group", r.message.customer_group);
					}
				}
			},
		});
	}
}
