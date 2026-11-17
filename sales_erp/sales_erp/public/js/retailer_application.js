function sales_erp_is_asm_only() {
	const roles = new Set(frappe.user_roles || []);
	return roles.has("Clothing Area Sales Manager")
		&& !["Administrator", "System Manager", "Clothing Regional Sales Manager", "Clothing Business Administrator"]
			.some((role) => roles.has(role));
}

function sales_erp_disable_link_navigation(frm, fieldname) {
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

function sales_erp_inject_security_styles() {
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
	`, "sales_erp_retailer_application_salesperson_style");
}

frappe.ui.form.on("Retailer Application", {
	setup(frm) {
		sales_erp_inject_security_styles();
		sales_erp_scope_retailer_application(frm);
	},
	refresh(frm) {
		sales_erp_inject_security_styles();
		sales_erp_scope_retailer_application(frm);

		if (frm.is_new()) return;

		const user_roles = new Set(frappe.user_roles || []);
		const is_rsm = user_roles.has("Clothing Regional Sales Manager");
		const is_admin = ["Clothing Business Administrator", "System Manager", "Administrator"].some((r) => user_roles.has(r));
		const is_asm = user_roles.has("Clothing Area Sales Manager") && frm.doc.salesperson === frappe.session.user;

		if (frm.doc.status === "More Information Requested") {
			frm.dashboard.set_headline_alert(
				__("<b>Information Requested by {0}:</b> {1}", [frm.doc.info_requested_by || "RSM", frm.doc.requested_information || ""]),
				"orange"
			);
		} else if (frm.doc.status === "Resubmitted") {
			frm.dashboard.set_headline_alert(
				__("Application resubmitted by {0} on {1}. Ready for RSM decision.", [frm.doc.salesperson, frm.doc.resubmitted_on || ""]),
				"blue"
			);
		} else if (frm.doc.status === "Approved") {
			const limit_info = frm.doc.initial_credit_limit ? ` (Initial Limit: ₹${frm.doc.initial_credit_limit})` : "";
			frm.dashboard.set_headline_alert(
				__("Application approved by {0}. Retailer account created: {1}{2}", [frm.doc.reviewed_by, frm.doc.customer, limit_info]),
				"green"
			);
		} else if (frm.doc.status === "Rejected") {
			frm.dashboard.set_headline_alert(
				__("Application rejected by {0}. Reason: {1}", [frm.doc.reviewed_by, frm.doc.rejection_reason || ""]),
				"red"
			);
		}

		if (["Pending", "Resubmitted"].includes(frm.doc.status) && (is_rsm || is_admin)) {
			frm.add_custom_button(__("Approve"), () => {
				frappe.prompt(
					[
						{
							fieldname: "initial_credit_limit",
							fieldtype: "Currency",
							label: __("Initial Credit / Exposure Limit (₹)"),
							default: frm.doc.initial_credit_limit || 0,
							description: __("Set the initial approved credit limit for this retailer.")
						}
					],
					async ({ initial_credit_limit }) => {
						await frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.approve",
							type: "POST",
							args: {
								name: frm.doc.name,
								initial_credit_limit: initial_credit_limit || 0,
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Approve Retailer Application"),
					__("Approve & Create Retailer")
				);
			}, __("Review")).addClass("btn-primary");

			frm.add_custom_button(__("Request Info"), () => {
				frappe.prompt(
					[{ fieldname: "comments", fieldtype: "Small Text", label: __("Information Required from ASM"), reqd: 1 }],
					async ({ comments }) => {
						await frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.request_more_info",
							type: "POST",
							args: { name: frm.doc.name, comments },
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Request More Information"),
					__("Send Request")
				);
			}, __("Review"));

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Rejection Reason"), reqd: 1 }],
					async ({ reason }) => {
						await frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.reject",
							type: "POST",
							args: { name: frm.doc.name, reason },
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Reject Retailer Application"),
					__("Reject")
				);
			}, __("Review"));
		}

		if (frm.doc.status === "More Information Requested" && (is_asm || is_admin)) {
			frm.add_custom_button(__("Resubmit Application"), () => {
				frappe.prompt(
					[{ fieldname: "notes", fieldtype: "Small Text", label: __("Resubmission Notes (optional)") }],
					async ({ notes }) => {
						await frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.resubmit",
							type: "POST",
							args: { name: frm.doc.name, notes },
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Resubmit Retailer Application"),
					__("Resubmit")
				);
			}).addClass("btn-primary");
		}
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

function sales_erp_scope_retailer_application(frm) {
	frm.set_query("customer_group", () => ({
		filters: { parent_customer_group: "Clothing ERP Retailer Types", is_group: 0 },
	}));

	frm.set_df_property("salesperson", "read_only", 1);
	frm.set_df_property("rsm", "read_only", 1);
	sales_erp_disable_link_navigation(frm, "salesperson");
	sales_erp_disable_link_navigation(frm, "rsm");
	sales_erp_disable_link_navigation(frm, "reviewed_by");

	setTimeout(() => {
		sales_erp_disable_link_navigation(frm, "salesperson");
		sales_erp_disable_link_navigation(frm, "rsm");
		sales_erp_disable_link_navigation(frm, "reviewed_by");
	}, 100);

	if (sales_erp_is_asm_only()) {
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
