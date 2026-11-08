frappe.pages["retailer-assignments"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Retailer Assignments"),
		single_column: true,
	});
	new RetailerAssignments(page);
};

class RetailerAssignments {
	constructor(page) {
		this.page = page;
		this.state = { page: 1, search: "" };
		this.salespeople = [];
		this.page.main.html(`<div class="retailer-assignments">
			<div class="retailer-assignment-toolbar">
				<input class="form-control assignment-search" type="search" placeholder="${__("Search retailer")}">
			</div>
			<div class="assignment-status text-muted" role="status"></div>
			<div class="assignment-table-wrap"></div>
			<div class="assignment-pagination"></div>
		</div>`);
		this.$root = this.page.main.find(".retailer-assignments");
		this.bind();
		this.refresh();
	}

	bind() {
		let timer;
		this.$root.find(".assignment-search").on("input", (event) => {
			clearTimeout(timer);
			timer = setTimeout(() => {
				this.state.search = event.target.value;
				this.state.page = 1;
				this.refresh();
			}, 300);
		});
		this.$root.on("click", "[data-assignment-page]", (event) => {
			this.state.page = Number(event.currentTarget.dataset.assignmentPage);
			this.refresh();
		});
		this.$root.on("click", ".reassign-retailer", (event) => {
			this.open_reassignment(event.currentTarget.dataset.customer);
		});
	}

	escape(value) {
		return frappe.utils.escape_html(value || "");
	}

	async refresh() {
		this.$root.find(".assignment-status").text(__("Loading authorized retailers…"));
		const { message } = await frappe.call({
			method: "clothing_erp.retailer_assignment.get_reassignment_directory",
			args: this.state,
		});
		this.salespeople = message.salespeople || [];
		this.render(message);
	}

	render(data) {
		if (data.scope_required) {
			this.$root.find(".assignment-status").text(
				__("No Territory is assigned to your manager account. Ask an administrator to add a Territory User Permission."),
			);
			this.$root.find(".assignment-table-wrap, .assignment-pagination").empty();
			return;
		}

		this.$root.find(".assignment-status").text(
			data.territories == null
				? __("Administrator scope — all retailers")
				: __("Authorized territories: {0}", [data.territories.join(", ")]),
		);
		const rows = data.retailers.map((row) => `<tr>
			<td><strong>${this.escape(row.customer_name || row.name)}</strong><small>${this.escape(row.name)}</small></td>
			<td>${this.escape(row.territory)}</td>
			<td>${this.escape(row.current_salesperson || __("Unassigned"))}</td>
			<td><button class="btn btn-primary btn-sm reassign-retailer" data-customer="${this.escape(row.name)}">${__("Reassign")}</button></td>
		</tr>`).join("");
		this.$root.find(".assignment-table-wrap").html(data.retailers.length ? `<table class="table">
			<thead><tr><th>${__("Retailer")}</th><th>${__("Territory")}</th><th>${__("Current Salesperson")}</th><th></th></tr></thead>
			<tbody>${rows}</tbody>
		</table>` : `<div class="assignment-empty">${__("No authorized retailers found.")}</div>`);
		const page = data.pagination.page;
		this.$root.find(".assignment-pagination").html(`<button class="btn btn-default" data-assignment-page="${page - 1}" ${page === 1 ? "disabled" : ""}>${__("Previous")}</button>
			<span>${__("Page {0}", [page])}</span>
			<button class="btn btn-default" data-assignment-page="${page + 1}" ${data.pagination.has_more ? "" : "disabled"}>${__("Next")}</button>`);
	}

	async open_reassignment(customer) {
		const { message } = await frappe.call({
			method: "clothing_erp.retailer_assignment.get_retailer_assignment",
			args: { customer },
		});
		const salespeople = [{ label: "", value: "" }, ...(message.salespeople || this.salespeople).map((user) => ({
			label: user.full_name && user.full_name !== user.name ? `${user.full_name} (${user.name})` : user.name,
			value: user.name,
		}))];
		const dialog = new frappe.ui.Dialog({
			title: __("Reassign {0}", [customer]),
			fields: [
				{ fieldtype: "Data", fieldname: "current_salesperson", label: __("Current Salesperson"), default: message.current_salesperson || __("Unassigned"), read_only: 1 },
				{ fieldtype: "Select", fieldname: "new_salesperson", label: __("New Salesperson"), options: salespeople, reqd: 1 },
				{ fieldtype: "Small Text", fieldname: "reason", label: __("Reason"), reqd: 1 },
			],
			primary_action_label: __("Reassign"),
			primary_action: async (values) => {
				await frappe.call({
					method: "clothing_erp.retailer_assignment.reassign_retailer",
					type: "POST",
					args: {
						customer,
						new_salesperson: values.new_salesperson,
						reason: values.reason,
						expected_current_salesperson: message.current_salesperson || "",
					},
					freeze: true,
					freeze_message: __("Reassigning retailer…"),
				});
				dialog.hide();
				frappe.show_alert({ message: __("Retailer reassigned"), indicator: "green" });
				this.refresh();
			},
		});
		dialog.show();
	}
}
