frappe.ui.form.on("ASM Supervision", {
	setup(frm) {
		frm.set_query("territory", function() {
			return { filters: { is_group: 0 } };
		});
		frm.set_query("asm", function() {
			return {
				query: "sales_erp.supervision.sales_role_user_query",
				filters: {
					role: "Clothing Area Sales Manager"
				}
			};
		});

		frm.set_query("rsm", function() {
			return {
				query: "sales_erp.supervision.sales_role_user_query",
				filters: {
					role: "Clothing Regional Sales Manager"
				}
			};
		});
	},

	refresh(frm) {
		frm.page.set_title(__("Sales Territory Assignment"));
		const is_admin = frappe.user_roles.includes("Administrator") ||
			frappe.user_roles.includes("System Manager") ||
			frappe.user_roles.includes("Clothing Business Administrator");

		if (!is_admin) {
			frm.disable_save();
			frm.set_read_only();
			return;
		}

		if (!frm.is_new() && frm.doc.status === "Active") {
			frm.add_custom_button(__("Reassign RSM"), function() {
				const dialog = new frappe.ui.Dialog({
					title: __("Reassign Territory's RSM"),
					fields: [
						{
							fieldname: "territory",
							fieldtype: "Link",
							label: __("Sales Territory"),
							options: "Territory",
							default: frm.doc.territory,
							read_only: 1
						},
						{
							fieldname: "new_rsm",
							fieldtype: "Link",
							label: __("New Regional Sales Manager"),
							options: "User",
							reqd: 1,
							get_query: function() {
								return {
									query: "sales_erp.supervision.sales_role_user_query",
									filters: {
										role: "Clothing Regional Sales Manager"
									}
								};
							}
						},
						{
							fieldname: "effective_from",
							fieldtype: "Date",
							label: __("Effective From"),
							default: frappe.datetime.get_today(),
							reqd: 1
						},
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Reason"),
							reqd: 1
						}
					],
					primary_action_label: __("Reassign"),
					primary_action(values) {
						dialog.hide();
						frappe.call({
							method: "sales_erp.supervision.assign_asm_supervision",
							args: {
								asm: frm.doc.asm,
								rsm: values.new_rsm,
								territory: frm.doc.territory,
								effective_from: values.effective_from,
								reason: values.reason
							},
							freeze: true,
							freeze_message: __("Updating territory assignment..."),
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Supervision reassigned successfully"),
										indicator: "green"
									});
									frappe.set_route("Form", "ASM Supervision", r.message.name);
								}
							}
						});
					}
				});
				dialog.show();
			}, __("Actions"));

			frm.add_custom_button(__("End Supervision"), function() {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Reason for ending assignment"),
							reqd: 1
						},
						{
							fieldname: "end_date",
							fieldtype: "Date",
							label: __("End Date"),
							default: frappe.datetime.get_today(),
							reqd: 1
						}
					],
					function(values) {
						frappe.call({
							method: "sales_erp.supervision.end_asm_supervision",
							args: {
								name: frm.doc.name,
								reason: values.reason,
								end_date: values.end_date
							},
							freeze: true,
							freeze_message: __("Ending territory assignment..."),
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Territory assignment ended"),
										indicator: "orange"
									});
									frm.reload_doc();
								}
							}
						});
					},
					__("End Supervision"),
					__("Confirm End")
				);
			}, __("Actions"));
		}
	}
});
