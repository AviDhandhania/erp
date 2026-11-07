const clothing_erp_customer_list_settings = frappe.listview_settings["Customer"] || {};

frappe.listview_settings["Customer"] = {
	...clothing_erp_customer_list_settings,
	onload(listview) {
		clothing_erp_customer_list_settings.onload?.(listview);
		if (!["System Manager", "Clothing Sales Manager", "Clothing Business Administrator"]
			.some((role) => frappe.user_roles.includes(role))) return;
		listview.page.add_actions_menu_item(__("Reassign Clothing Salesperson"), () => {
			const customers = listview.get_checked_items().map((row) => row.name);
			if (!customers.length) {
				frappe.msgprint(__("Select at least one retailer first."));
				return;
			}
			if (customers.length > 100) {
				frappe.msgprint(__("Select no more than 100 retailers at once."));
				return;
			}
			const dialog = new frappe.ui.Dialog({
				title: __("Bulk Reassign Retailers"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p>${__("{0} retailers selected", [customers.length])}</p>`,
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
				primary_action_label: __("Reassign Selected"),
				primary_action: async (values) => {
					const { message } = await frappe.call({
						method: "clothing_erp.retailer_assignment.bulk_reassign_retailers",
						type: "POST",
						args: {
							customers: JSON.stringify(customers),
							new_salesperson: values.new_salesperson,
							reason: values.reason,
						},
						freeze: true,
						freeze_message: __("Reassigning retailers…"),
					});
					dialog.hide();
					frappe.show_alert({
						message: __("{0} retailers reassigned; {1} unchanged", [message.changed, message.unchanged]),
						indicator: "green",
					});
					listview.refresh();
				},
			});
			dialog.show();
		});
	},
};
