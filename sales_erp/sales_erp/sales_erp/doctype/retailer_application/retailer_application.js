frappe.ui.form.on("Retailer Application", {
	refresh(frm) {
		if (frm.is_new()) return;

		const user_roles = new Set(frappe.user_roles || []);
		const is_rsm = user_roles.has("Clothing Regional Sales Manager");
		const is_admin = ["Clothing Business Administrator", "System Manager", "Administrator"].some((r) => user_roles.has(r));
		const is_asm = user_roles.has("Clothing Area Sales Manager") && frm.doc.salesperson === frappe.session.user;

		// 1. Alert indicators for current state
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
			frm.dashboard.set_headline_alert(
				__("Application approved by {0}. Retailer account created: {1}", [frm.doc.reviewed_by, frm.doc.customer]),
				"green"
			);
		} else if (frm.doc.status === "Rejected") {
			frm.dashboard.set_headline_alert(
				__("Application rejected by {0}. Reason: {1}", [frm.doc.reviewed_by, frm.doc.rejection_reason || ""]),
				"red"
			);
		}

		// 2. RSM & Admin review actions (Approve, Request Info, Reject)
		if (["Pending", "Resubmitted"].includes(frm.doc.status) && (is_rsm || is_admin)) {
			frm.add_custom_button(__("Approve"), async () => {
				await frappe.call({
					method: "sales_erp.sales_erp.doctype.retailer_application.retailer_application.approve",
					type: "POST",
					args: { name: frm.doc.name },
					freeze: true,
				});
				await frm.reload_doc();
			}, __("Review"));

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

		// 3. ASM Resubmission action
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
