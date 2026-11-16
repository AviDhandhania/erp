// Form scripts for Retailer Visit

frappe.ui.form.on("Retailer Visit", {
	refresh(frm) {
		const user_roles = new Set(frappe.user_roles || []);
		const is_admin = ["Clothing Business Administrator", "System Manager", "Administrator"].some((r) => user_roles.has(r));
		const is_rsm = user_roles.has("Clothing Regional Sales Manager") || is_admin;
		const is_asm = user_roles.has("Clothing Area Sales Manager") && !is_rsm;

		// 1. Field Visibility toggles
		const is_rsm_visit = frm.doc.visitor_role === "Regional Sales Manager" || frm.doc.visit_type === "RSM Periodic Review";
		frm.toggle_display("rsm_assessment_section", is_rsm_visit || is_rsm);
		frm.toggle_display("financial_assessment", is_rsm_visit || is_rsm);
		frm.toggle_display("customer_footfall", is_rsm_visit || is_rsm);
		frm.toggle_display("stock_condition", is_rsm_visit || is_rsm);
		frm.toggle_display("recommended_credit_limit", is_rsm_visit || is_rsm);
		frm.toggle_display("dealer_feedback", is_rsm_visit || is_rsm);

		if (is_asm) {
			frm.set_df_property("visit_type", "options", [
				"General Visit",
				"Sample & Order Taking",
				"Stock Review"
			]);
		}

		if (frm.is_new()) {
			if (is_asm) {
				frm.set_value("salesperson", frappe.session.user);
				frm.set_value("visitor_role", "Area Sales Manager");
			} else if (is_rsm) {
				if (!frm.doc.salesperson) {
					frm.set_value("salesperson", frappe.session.user);
				}
				frm.set_value("visitor_role", "Regional Sales Manager");
			}
			return;
		}

		// 2. Status Headline Alerts
		if (frm.doc.review_status === "Submitted") {
			frm.dashboard.set_headline_alert(
				__("Visit report submitted by <b>{0}</b>. Awaiting review by supervising RSM <b>{1}</b>.", [frm.doc.salesperson, frm.doc.rsm || "RSM"]),
				"blue"
			);
		} else if (frm.doc.review_status === "Reviewed by RSM") {
			const notes = frm.doc.review_notes ? ` | Notes: ${frm.doc.review_notes}` : "";
			frm.dashboard.set_headline_alert(
				__("Visit report reviewed by <b>{0}</b> on {1}.{2}", [frm.doc.reviewed_by, frm.doc.reviewed_on || "", notes]),
				"green"
			);
		} else if (frm.doc.review_status === "Action Required") {
			frm.dashboard.set_headline_alert(
				__("Action requested by supervising RSM <b>{0}</b>: {1}", [frm.doc.reviewed_by, frm.doc.review_notes || "Please check details"]),
				"orange"
			);
		}

		// 3. RSM / Administrator Review Action Button
		if (frm.doc.review_status === "Submitted" && is_rsm) {
			frm.add_custom_button(__("Review Visit"), () => {
				frappe.prompt(
					[
						{
							fieldname: "status",
							fieldtype: "Select",
							label: __("Review Decision"),
							options: ["Reviewed by RSM", "Action Required"],
							default: "Reviewed by RSM",
							reqd: 1,
						},
						{
							fieldname: "notes",
							fieldtype: "Small Text",
							label: __("Review Notes / Feedback for ASM"),
						}
					],
					async ({ status, notes }) => {
						await frappe.call({
							method: "clothing_erp.clothing_erp.doctype.retailer_visit.retailer_visit.review_visit",
							type: "POST",
							args: {
								name: frm.doc.name,
								status: status,
								notes: notes || "",
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("RSM Visit Review"),
					__("Submit Review")
				);
			}, __("Review")).addClass("btn-primary");
		}
	},

	customer(frm) {
		if (frm.doc.customer && frappe.user_roles.includes("Clothing Area Sales Manager")) {
			frappe.db.get_value("Customer", frm.doc.customer, "territory").then((r) => {
				if (r && r.message && r.message.territory) {
					frappe.call({
						method: "clothing_erp.supervision.get_territory_supervision",
						args: { territory: r.message.territory },
						callback(res) {
							if (res && res.message && res.message.rsm) {
								frm.set_value("rsm", res.message.rsm);
							}
						}
					});
				}
			});
		}
	}
});
