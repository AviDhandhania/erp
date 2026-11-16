// Form scripts for Supplier Quality Inspection

frappe.ui.form.on("Supplier Quality Inspection", {
	refresh(frm) {
		if (frm.is_new()) return;

		const user_roles = new Set(frappe.user_roles || []);
		const is_admin = ["Clothing Business Administrator", "System Manager", "Administrator"].some((r) => user_roles.has(r));
		const is_inspector = user_roles.has("Clothing Quality Inspector") || user_roles.has("Clothing Quality Manager") || is_admin;
		const is_critical = frm.doc.stage && (frm.doc.stage.includes("Production Go Ahead") || frm.doc.stage.includes("Final Inspection"));

		// 1. Dashboard Status Alerts
		if (frm.doc.status === "Approved") {
			frm.dashboard.set_headline_alert(
				__("<b>Quality Gate Approved</b> by {0} on {1}.", [frm.doc.approved_by || "Admin", frm.doc.approval_date || ""]),
				"green"
			);
		} else if (frm.doc.status === "Rejected") {
			frm.dashboard.set_headline_alert(
				__("<b>Quality Gate Rejected</b> by {0}. Reason: {1}", [frm.doc.approved_by || "Inspector", frm.doc.comments || ""]),
				"red"
			);
		} else if (frm.doc.status === "Pending Review") {
			if (is_critical) {
				frm.dashboard.set_headline_alert(
					__("<b>CRITICAL GATE ({0}):</b> Requires Administrator approval for production or customer release.", [frm.doc.stage]),
					"orange"
				);
			} else {
				frm.dashboard.set_headline_alert(
					__("Quality inspection pending decision for stage: <b>{0}</b>", [frm.doc.stage]),
					"blue"
				);
			}
		}

		// 2. Action Buttons for Pending Review
		if (frm.doc.status === "Pending Review" && is_inspector) {
			frm.add_custom_button(__("Approve Gate"), () => {
				if (is_critical && !is_admin) {
					frappe.msgprint({
						title: __("Administrator Approval Required"),
						message: __("Critical gate '{0}' requires Administrator approval. Quality Inspectors cannot approve release gates.", [frm.doc.stage]),
						indicator: "red"
					});
					return;
				}

				frappe.prompt(
					[
						{
							fieldname: "notes",
							fieldtype: "Small Text",
							label: __("Approval Notes (Optional)"),
						}
					],
					async ({ notes }) => {
						await frappe.call({
							method: "quality_erp.quality.approve_quality_gate",
							type: "POST",
							args: {
								inspection_name: frm.doc.name,
								notes: notes || "",
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Approve Quality Gate"),
					__("Approve")
				);
			}, __("Actions")).addClass("btn-primary");

			frm.add_custom_button(__("Reject Gate"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Rejection Reason"),
							reqd: 1,
						}
					],
					async ({ reason }) => {
						await frappe.call({
							method: "quality_erp.quality.reject_quality_gate",
							type: "POST",
							args: {
								inspection_name: frm.doc.name,
								reason: reason,
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Reject Quality Gate"),
					__("Reject")
				);
			}, __("Actions")).addClass("btn-danger");
		}
	}
});
