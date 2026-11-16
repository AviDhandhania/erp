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
		[data-fieldname="rsm"] a,
		[data-fieldname="reviewed_by"] a {
			pointer-events: none !important;
			cursor: default !important;
			text-decoration: none !important;
			color: inherit !important;
		}
		[data-fieldname="salesperson"] .btn-open,
		[data-fieldname="salesperson"] .link-btn,
		[data-fieldname="salesperson"] .octicon-link-external,
		[data-fieldname="rsm"] .btn-open,
		[data-fieldname="rsm"] .link-btn,
		[data-fieldname="rsm"] .octicon-link-external,
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
	territory(frm) {
		if (!frm.doc.territory) {
			frm.set_value("salesperson", "");
			frm.set_value("rsm", "");
			return;
		}
		frappe.call({
			method: "clothing_erp.clothing_erp.doctype.retailer_application.retailer_application.get_territory_assignment",
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

function clothing_erp_scope_retailer_application(frm) {
	frm.set_query("customer_group", () => ({
		filters: { parent_customer_group: "Clothing ERP Retailer Types", is_group: 0 },
	}));

	frm.set_df_property("salesperson", "read_only", 1);
	frm.set_df_property("rsm", "read_only", 1);
	clothing_erp_disable_link_navigation(frm, "salesperson");
	clothing_erp_disable_link_navigation(frm, "rsm");
	clothing_erp_disable_link_navigation(frm, "reviewed_by");

	setTimeout(() => {
		clothing_erp_disable_link_navigation(frm, "salesperson");
		clothing_erp_disable_link_navigation(frm, "rsm");
		clothing_erp_disable_link_navigation(frm, "reviewed_by");
	}, 100);

	if (clothing_erp_is_asm_only()) {
		if (frm.is_new() && !frm.doc.territory) {
			frappe.db.get_value("User Permission", {
				user: frappe.session.user,
				allow: "Territory",
			}, "for_value").then((r) => {
				if (r && r.message && r.message.for_value) {
					frm.set_value("territory", r.message.for_value);
				}
			});
		}
	}
}
