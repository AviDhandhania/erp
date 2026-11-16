frappe.ui.form.on("ASM Supervision", {
	setup(frm) {
		frm.set_query("asm", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					enabled: 1,
					user_type: "System User"
				}
			};
		});

		frm.set_query("rsm", function() {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: {
					enabled: 1,
					user_type: "System User"
				}
			};
		});
	},

	refresh(frm) {
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
					title: __("Reassign Area Sales Manager"),
					fields: [
						{
							fieldname: "new_rsm",
							fieldtype: "Link",
							label: __("New Regional Sales Manager"),
							options: "User",
							reqd: 1,
							get_query: function() {
								return {
									filters: {
										enabled: 1,
										user_type: "System User"
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
							method: "clothing_erp.supervision.assign_asm_supervision",
							args: {
								asm: frm.doc.asm,
								rsm: values.new_rsm,
								effective_from: values.effective_from,
								reason: values.reason
							},
							freeze: true,
							freeze_message: __("Reassigning supervision..."),
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
							label: __("Reason for ending supervision"),
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
							method: "clothing_erp.supervision.end_asm_supervision",
							args: {
								name: frm.doc.name,
								reason: values.reason,
								end_date: values.end_date
							},
							freeze: true,
							freeze_message: __("Ending supervision..."),
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Supervision ended"),
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
