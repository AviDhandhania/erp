frappe.ui.form.on("Retailer Credit Limit Request", {
	refresh(frm) {
		const is_admin = frappe.user_roles.includes("System Manager") ||
			frappe.user_roles.includes("Clothing Business Administrator");

		// Status alert banners
		if (frm.doc.status === "Pending Approval") {
			frm.dashboard.set_headline_alert(
				__("Pending Administrator Approval. Live retailer limit remains unchanged."),
				"orange"
			);
		} else if (frm.doc.status === "Approved") {
			frm.dashboard.set_headline_alert(
				__("Approved by {0} on {1}. Live retailer credit limit updated.", [
					frm.doc.approver || __("Administrator"),
					frm.doc.decided_on ? frappe.datetime.str_to_user(frm.doc.decided_on) : ""
				]),
				"green"
			);
		} else if (frm.doc.status === "Rejected") {
			frm.dashboard.set_headline_alert(
				__("Rejected by {0} on {1}. Reason: {2}", [
					frm.doc.approver || __("Administrator"),
					frm.doc.decided_on ? frappe.datetime.str_to_user(frm.doc.decided_on) : "",
					frm.doc.rejection_reason || __("None")
				]),
				"red"
			);
		}

		// Action buttons for administrators
		if (frm.doc.status === "Pending Approval" && is_admin && !frm.is_new()) {
			frm.add_custom_button(__("Approve Limit Change"), () => {
				frappe.confirm(
					__("Approve credit limit change to ₹{0} for {1}?", [
						format_currency(frm.doc.proposed_credit_limit),
						frm.doc.customer_name || frm.doc.customer
					]),
					() => {
						frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request.approve_credit_limit_request",
							args: { name: frm.doc.name },
							freeze: true,
							freeze_message: __("Updating credit limit..."),
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Credit limit change approved"),
										indicator: "green"
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			}).addClass("btn-primary");

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Rejection Reason"),
							reqd: 1
						}
					],
					(values) => {
						frappe.call({
							method: "sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request.reject_credit_limit_request",
							args: {
								name: frm.doc.name,
								reason: values.reason
							},
							freeze: true,
							freeze_message: __("Rejecting request..."),
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Credit limit request rejected"),
										indicator: "orange"
									});
									frm.reload_doc();
								}
							}
						});
					},
					__("Reject Credit Limit Request"),
					__("Confirm Rejection")
				);
			}).addClass("btn-danger");
		}
	}
});
