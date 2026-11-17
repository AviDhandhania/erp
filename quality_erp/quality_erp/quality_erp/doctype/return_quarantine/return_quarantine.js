// Form scripts for Return Quarantine

frappe.ui.form.on("Return Quarantine", {
	refresh(frm) {
		if (frm.is_new()) return;

		const user_roles = new Set(frappe.user_roles || []);
		const is_admin = ["Clothing Business Administrator", "System Manager", "Administrator"].some((r) => user_roles.has(r));
		const is_inspector = user_roles.has("Clothing Quality Inspector") || user_roles.has("Clothing Quality Manager") || is_admin;

		// 1. Dashboard Status Alerts
		if (frm.doc.inspection_status === "Quarantined") {
			frm.dashboard.set_headline_alert(
				__("Item is currently <b>Quarantined</b> in {0} awaiting quality inspection.", [frm.doc.quarantine_warehouse || "Warehouse"]),
				"orange"
			);
		} else if (frm.doc.inspection_status === "Inspected - Passed Refurbishment") {
			frm.dashboard.set_headline_alert(
				__("Inspection complete: <b>Passed Refurbishment</b> by {0} on {1}.", [frm.doc.inspected_by || "Inspector", frm.doc.inspected_on || ""]),
				"green"
			);
		} else if (frm.doc.inspection_status === "Inspected - Scrapped") {
			frm.dashboard.set_headline_alert(
				__("Inspection complete: <b>Item Scrapped</b> by {0} on {1}.", [frm.doc.inspected_by || "Inspector", frm.doc.inspected_on || ""]),
				"red"
			);
		} else if (frm.doc.inspection_status === "Restocked") {
			frm.dashboard.set_headline_alert(
				__("Item has been successfully restocked into active inventory.", []),
				"blue"
			);
		}

		// 2. Action buttons for Quarantined status
		if (frm.doc.inspection_status === "Quarantined" && is_inspector) {
			frm.add_custom_button(__("Pass Refurbishment"), async () => {
				frappe.confirm(
					__("Mark this returned item as passed after refurbishment inspection?"),
					async () => {
						await frappe.call({
							method: "quality_erp.quality.inspect_return_quarantine",
							type: "POST",
							args: {
								quarantine_name: frm.doc.name,
								decision: "Passed Refurbishment",
							},
							freeze: true,
							freeze_message: __("Updating inspection status…"),
						});
						await frm.reload_doc();
					}
				);
			}, __("Inspection Actions")).addClass("btn-primary");

			frm.add_custom_button(__("Recommend Disposition"), () => {
				frappe.prompt(
					[
						{
							fieldname: "disposition",
							fieldtype: "Select",
							label: __("Recommended Disposition"),
							options: "Restock (A-Grade)\nRefurbish\nSeconds Sale (B-Grade)\nScrap\nSupplier Claim\nOn Hold",
							reqd: 1,
						},
						{
							fieldname: "notes",
							fieldtype: "Small Text",
							label: __("Recommendation Rationale"),
						}
					],
					async ({ disposition, notes }) => {
						await frappe.call({
							method: "quality_erp.quality.recommend_return_disposition",
							type: "POST",
							args: {
								quarantine_name: frm.doc.name,
								disposition: disposition,
								notes: notes || "",
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Recommend Return Disposition"),
					__("Submit Recommendation")
				);
			}, __("Inspection Actions"));
		}

		// 3. Disposition approval for Business Administrator
		if (is_admin && frm.doc.disposition_status === "Awaiting Business Approval") {
			frm.add_custom_button(__("Approve Disposition"), () => {
				frappe.prompt(
					[
						{
							fieldname: "decision",
							fieldtype: "Select",
							label: __("Business Disposition Decision"),
							options: "Scrap\nSeconds Sale\nSupplier Claim\nOn Hold\nReject Disposition",
							default: frm.doc.disposition ? (frm.doc.disposition.includes("Seconds") ? "Seconds Sale" : (frm.doc.disposition.includes("Supplier") ? "Supplier Claim" : frm.doc.disposition)) : "Scrap",
							reqd: 1,
						},
						{
							fieldname: "approval_notes",
							fieldtype: "Small Text",
							label: __("Business Approval Notes"),
						},
						{
							fieldname: "claim_amount",
							fieldtype: "Currency",
							label: __("Supplier Claim Amount (if Supplier Claim)"),
							depends_on: 'eval:doc.decision=="Supplier Claim"',
						}
					],
					async ({ decision, approval_notes, claim_amount }) => {
						await frappe.call({
							method: "quality_erp.quality.approve_return_disposition",
							type: "POST",
							args: {
								quarantine_name: frm.doc.name,
								decision: decision,
								approval_notes: approval_notes || "",
								supplier_claim_amount: claim_amount || 0.0,
							},
							freeze: true,
						});
						await frm.reload_doc();
					},
					__("Approve Return Disposition"),
					__("Authorize Disposition")
				);
			}, __("Business Authorization")).addClass("btn-primary");
		}
	}
});
