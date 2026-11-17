frappe.query_reports["Retailer Cadence and Exposure Report"] = {
	filters: [
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname: "customer_group",
			label: __("Operating Type"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		{
			fieldname: "exposure_status",
			label: __("Exposure Status"),
			fieldtype: "Select",
			options: "\nAll\nNormal\nExceeded Limit",
			default: "All",
		},
		{
			fieldname: "cadence_status",
			label: __("Cadence Status"),
			fieldtype: "Select",
			options: "\nAll\nOK\nUpcoming\nGrace\nOverdue",
			default: "All",
		},
	],
};
