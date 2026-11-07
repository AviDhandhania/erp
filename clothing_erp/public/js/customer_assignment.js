frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new() || !clothing_erp_can_reassign_retailer()) return;
		frm.add_custom_button(__("Reassign Salesperson"), async () => {
			const { message } = await frappe.call({
				method: "clothing_erp.retailer_assignment.get_retailer_assignment",
				args: { customer: frm.doc.name },
			});
			const dialog = new frappe.ui.Dialog({
				title: __("Reassign Retailer"),
				fields: [
					{
						fieldtype: "Data",
						fieldname: "current_salesperson",
						label: __("Current Salesperson"),
						default: message.current_salesperson || __("Unassigned"),
						read_only: 1,
					},
					{
						fieldtype: "Link",
						fieldname: "new_salesperson",
						label: __("New Salesperson"),
						options: "User",
						reqd: 1,
					},
					{
						fieldtype: "Small Text",
						fieldname: "reason",
						label: __("Reason"),
						reqd: 1,
					},
				],
				primary_action_label: __("Reassign"),
				primary_action: async (values) => {
					await frappe.call({
						method: "clothing_erp.retailer_assignment.reassign_retailer",
						type: "POST",
						args: {
							customer: frm.doc.name,
							new_salesperson: values.new_salesperson,
							reason: values.reason,
							expected_current_salesperson: message.current_salesperson || "",
						},
						freeze: true,
						freeze_message: __("Reassigning retailer…"),
					});
					dialog.hide();
					frappe.show_alert({ message: __("Retailer reassigned"), indicator: "green" });
					frm.reload_doc();
				},
			});
			dialog.show();
		}, __("Clothing ERP"));
	},
});

function clothing_erp_can_reassign_retailer() {
	return ["System Manager", "Clothing Sales Manager", "Clothing Business Administrator"]
		.some((role) => frappe.user_roles.includes(role));
}
