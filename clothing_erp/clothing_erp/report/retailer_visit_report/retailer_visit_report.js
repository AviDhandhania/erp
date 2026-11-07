frappe.query_reports["Retailer Visit Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.now_date(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
		},
		{
			fieldname: "customer",
			label: __("Retailer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "salesperson",
			label: __("Salesperson User"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "outcome",
			label: __("Outcome"),
			fieldtype: "Select",
			options: "\nOrder Expected\nFollow-up Required\nNo Requirement\nIssue Reported\nClosed",
		},
	],
};
