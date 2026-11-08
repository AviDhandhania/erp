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
	frm.toggle_display(["territory", "customer_group"], false);
	if (!frm.is_new()) return;

	frm.set_value("salesperson", frappe.session.user);
}
