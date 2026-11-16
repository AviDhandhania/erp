function clothing_erp_is_asm_only() {
	const roles = new Set(frappe.user_roles || []);
	return roles.has("Clothing Area Sales Manager")
		&& !["Administrator", "System Manager", "Clothing Regional Sales Manager", "Clothing Business Administrator"]
			.some((role) => roles.has(role));
}

function clothing_erp_disable_link_navigation(frm, fieldname) {
	const field = frm.get_field(fieldname);
	if (!field || !field.$wrapper) return;
	field.$wrapper.find("a").removeAttr("href").attr("href", "javascript:void(0)").css({
		"pointer-events": "none",
		"cursor": "default",
		"text-decoration": "none",
		"color": "inherit",
	});
	field.$wrapper.find(".btn-open, .link-btn, .octicon-link-external, [data-action='open-link']").hide();
	field.$wrapper.off("click.block_framework").on("click.block_framework", "a, .btn-open, .link-btn", (e) => {
		e.preventDefault();
		e.stopPropagation();
		return false;
	});
}

function clothing_erp_inject_security_styles() {
	frappe.dom.set_style(`
		[data-fieldname="salesperson"] a,
		[data-fieldname="reviewed_by"] a {
			pointer-events: none !important;
			cursor: default !important;
			text-decoration: none !important;
			color: inherit !important;
		}
		[data-fieldname="salesperson"] .btn-open,
		[data-fieldname="salesperson"] .link-btn,
		[data-fieldname="salesperson"] .octicon-link-external,
		[data-fieldname="reviewed_by"] .btn-open,
		[data-fieldname="reviewed_by"] .link-btn,
		[data-fieldname="reviewed_by"] .octicon-link-external {
			display: none !important;
		}
	`, "clothing_erp_retailer_application_salesperson_style");
}

frappe.ui.form.on("Retailer Application", {
	setup(frm) {
		clothing_erp_inject_security_styles();
		clothing_erp_scope_retailer_application(frm);
	},
	refresh(frm) {
		clothing_erp_inject_security_styles();
		clothing_erp_scope_retailer_application(frm);
	},
});

function clothing_erp_scope_retailer_application(frm) {
	frm.set_query("customer_group", () => ({
		filters: { parent_customer_group: "Clothing ERP Retailer Types", is_group: 0 },
	}));
	if (!clothing_erp_is_asm_only()) return;

	frm.set_df_property("salesperson", "read_only", 1);
	frm.toggle_display("territory", false);
	frm.set_df_property("territory", "reqd", 0);
	clothing_erp_disable_link_navigation(frm, "salesperson");
	clothing_erp_disable_link_navigation(frm, "reviewed_by");

	setTimeout(() => {
		clothing_erp_disable_link_navigation(frm, "salesperson");
		clothing_erp_disable_link_navigation(frm, "reviewed_by");
	}, 100);

	if (!frm.is_new()) return;

	// On new intake, hide the ASM field and auto-assign the current ASM.
	frm.toggle_display("salesperson", false);
	frm.set_df_property("salesperson", "hidden", 1);

	if (!frm.doc.salesperson) {
		frm.set_value("salesperson", frappe.session.user);
	}
}
