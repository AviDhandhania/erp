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

			frm.add_custom_button(__("Mark as Scrapped"), () => {
				frappe.prompt(
					[
						{
							fieldname: "notes",
							fieldtype: "Small Text",
							label: __("Scrap Reason / Defect Details"),
							reqd: 1,
						}
					],
					async ({ notes }) => {
						await frappe.call({
							method: "quality_erp.quality.inspect_return_quarantine",
							type: "POST",
							args: {
								quarantine_name: frm.doc.name,
								decision: "Scrapped",
								notes: notes || "",
							},
							freeze: true,
							freeze_message: __("Updating inspection status…"),
						});
						await frm.reload_doc();
					},
					__("Confirm Scrap"),
					__("Mark Scrapped")
				);
			}, __("Inspection Actions")).addClass("btn-danger");
		}
	}
});
