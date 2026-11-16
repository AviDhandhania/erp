frappe.pages["fulfillment-tasks"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Fulfillment Tasks"), single_column: true });
	new FulfillmentTasks(page);
};

class FulfillmentTasks {
	constructor(page) {
		this.page = page;
		this.state = { task_type: "pick", state: "all", search: "", page: 1, page_size: 20 };
		this.setup();
		this.bind();
		this.refresh();
	}

	setup() {
		this.page.main.html(`<div class="fulfillment-tasks"><section class="fulfillment-panel">
			<div class="fulfillment-toolbar">
				<input class="form-control fulfillment-search" type="search" placeholder="${__("Search task or retailer")}" aria-label="${__("Search task or retailer")}">
				<select class="form-control fulfillment-type"><option value="pick">${__("Pick Lists")}</option><option value="delivery">${__("Delivery Notes")}</option></select>
				<select class="form-control fulfillment-state"><option value="all">${__("All statuses")}</option><option value="draft">${__("Draft")}</option><option value="submitted">${__("Submitted")}</option><option value="cancelled">${__("Cancelled")}</option></select>
				<span class="fulfillment-count text-muted"></span>
			</div>
			<div class="fulfillment-table" role="table">
				<div class="fulfillment-grid fulfillment-head" role="row"><div>${__("Task")}</div><div>${__("Retailer / purpose")}</div><div class="fulfillment-warehouse">${__("Warehouse")}</div><div>${__("Status")}</div></div>
				<div class="fulfillment-rows" role="rowgroup"></div>
			</div>
			<div class="fulfillment-pagination-wrap"></div>
		</section></div>`);
		this.$root = this.page.main.find(".fulfillment-tasks");
	}

	bind() {
		let timer;
		this.$root.find(".fulfillment-search").on("input", (event) => {
			clearTimeout(timer);
			timer = setTimeout(() => { this.state.search = event.target.value; this.state.page = 1; this.refresh(); }, 300);
		});
		this.$root.find(".fulfillment-type, .fulfillment-state").on("change", (event) => {
			this.state[event.currentTarget.classList.contains("fulfillment-type") ? "task_type" : "state"] = event.target.value;
			this.state.page = 1;
			this.refresh();
		});
		this.$root.on("click", "[data-task-page]", (event) => { this.state.page = Number(event.currentTarget.dataset.taskPage); this.refresh(); });
		this.$root.on("click", "[data-task-page-size]", (event) => { this.state.page_size = Number(event.currentTarget.dataset.taskPageSize); this.state.page = 1; this.refresh(); });
		this.$root.on("click", ".fulfillment-row", (event) => this.open_task(event.currentTarget.dataset.name));
		this.$root.on("keydown", ".fulfillment-row", (event) => {
			if (event.key === "Enter" || event.key === " ") { event.preventDefault(); this.open_task(event.currentTarget.dataset.name); }
		});
	}

	escape(value) { return frappe.utils.escape_html(String(value ?? "")); }

	async refresh() {
		this.$root.find(".fulfillment-rows").html(`<div class="fulfillment-message text-muted">${__("Loading authorized tasks…")}</div>`);
		const { message } = await frappe.call({ method: "warehouse_erp.fulfillment.get_fulfillment_tasks", args: this.state });
		this.render(message);
	}

	render(data) {
		const tasks = data.tasks || [];
		this.$root.find(".fulfillment-count").text(tasks.length === 1 ? __("1 task") : __("{0} tasks", [tasks.length]));
		this.$root.find(".fulfillment-rows").html(tasks.length ? tasks.map((task) => {
			const detail = task.customer_name || task.customer || task.purpose || __("Internal movement");
			const warehouse = task.parent_warehouse || __("From item rows");
			const indicator = Number(task.docstatus) === 2 ? "red" : Number(task.docstatus) === 0 ? "orange" : ["Completed", "Closed"].includes(task.status) ? "green" : "blue";
			return `<div class="fulfillment-grid fulfillment-row" role="row" tabindex="0" data-name="${this.escape(task.name)}">
				<div class="fulfillment-name ellipsis">${this.escape(task.name)}</div><div class="ellipsis" title="${this.escape(detail)}">${this.escape(detail)}</div><div class="fulfillment-warehouse ellipsis" title="${this.escape(warehouse)}">${this.escape(warehouse)}</div><div><span class="indicator-pill ${indicator}">${this.escape(task.status)}</span></div>
			</div>`;
		}).join("") : `<div class="fulfillment-message text-muted">${__("No authorized fulfillment tasks found.")}</div>`);
		const p = data.pagination;
		const sizes = [20, 50].map((size) => `<button class="btn btn-default btn-sm ${p.page_size === size ? "active" : ""}" data-task-page-size="${size}">${size}</button>`).join("");
		this.$root.find(".fulfillment-pagination-wrap").html(`<div class="fulfillment-pagination"><div class="fulfillment-page-group"><span class="text-muted">${__("Rows per page")}</span>${sizes}</div><div class="fulfillment-page-group"><span class="text-muted">${__("Page {0}", [p.page])}</span><button class="btn btn-default btn-sm" data-task-page="${p.page - 1}" ${p.page === 1 ? "disabled" : ""}>${__("Previous")}</button><button class="btn btn-default btn-sm" data-task-page="${p.page + 1}" ${p.has_more ? "" : "disabled"}>${__("Next")}</button></div></div>`);
	}

	async open_task(name) {
		const { message: task } = await frappe.call({ method: "warehouse_erp.fulfillment.get_fulfillment_task", args: { task_type: this.state.task_type, name }, freeze: true, freeze_message: __("Loading task…") });
		const dialog = new frappe.ui.Dialog({ title: task.name, size: "extra-large" });
		const rows = task.rows.map((row) => {
			const action = task.can_verify_items ? `<button type="button" class="btn btn-default btn-xs verify-pick-item" data-location="${this.escape(row.location)}" data-item-code="${this.escape(row.item_code)}">${__("Verify item")}</button>` : "";
			return `<tr><td><strong>${this.escape(row.item_name || row.item_code)}</strong><small>${this.escape(row.item_code)}</small></td><td>${this.escape(row.warehouse)}</td><td class="text-right">${format_number(row.stock_qty)} ${this.escape(row.stock_uom)}</td><td class="text-right">${row.picked_qty == null ? "0" : format_number(row.picked_qty)}</td><td>${this.escape(row.batch_no || row.serial_no || "—")}</td>${task.can_verify_items ? `<td class="text-right">${action}</td>` : ""}</tr>`;
		}).join("");
		const workflowNotice = task.workflow ? `<div class="alert alert-warning">${__("Pick List workflow {0} is active. Its configured approval actions must be completed before submission.", [this.escape(task.workflow)])}</div>` : "";
		const shortageAction = task.can_resolve_shortage ? `<button type="button" class="btn btn-default resolve-pick-shortage">${__("Resolve shortage")}</button>` : "";
		const completeAction = task.can_complete_pick ? `<button type="button" class="btn btn-primary complete-pick-list">${__("Complete picking")}</button>` : "";
		const footerActions = shortageAction || completeAction ? `<div class="text-right">${shortageAction} ${completeAction}</div>` : "";
		dialog.$body.html(`<div class="fulfillment-detail-summary"><div><span>${__("Status")}</span><strong>${this.escape(task.status)}</strong></div><div><span>${__("Retailer")}</span><strong>${this.escape(task.customer_name || task.customer || "—")}</strong></div><div><span>${__("Company")}</span><strong>${this.escape(task.company)}</strong></div><div><span>${__("Purpose")}</span><strong>${this.escape(task.purpose || __("Delivery"))}</strong></div></div>${task.can_verify_items ? `<div class="alert alert-info">${__("Scan the SKU/item barcode, Batch No, or Serial No required by the exact Pick List row. ERPNext validates tracked stock when each scan is saved.")}</div>` : ""}${workflowNotice}<div class="fulfillment-detail-table"><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th>${__("Warehouse")}</th><th class="text-right">${__("Required")}</th><th class="text-right">${__("Picked")}</th><th>${__("Batch / serial")}</th>${task.can_verify_items ? `<th class="text-right">${__("Action")}</th>` : ""}</tr></thead><tbody>${rows}</tbody></table></div>${task.rows_truncated ? `<p class="text-muted">${__("Only the first 200 rows are shown.")}</p>` : ""}${footerActions}`);
		dialog.$body.on("click", ".verify-pick-item", (event) => this.verify_item(task, event.currentTarget, dialog));
		dialog.$body.on("click", ".resolve-pick-shortage", () => this.resolve_shortage(task, dialog));
		dialog.$body.on("click", ".complete-pick-list", () => this.complete_pick(task, dialog));
		dialog.show();
	}

	async verify_item(task, button, dialog) {
		const values = await new Promise((resolve) => {
			frappe.prompt([
				{ fieldname: "barcode", fieldtype: "Data", label: __("SKU, item barcode, Batch No, or Serial No"), reqd: 1 },
				{ fieldname: "quantity", fieldtype: "Int", label: __("Quantity"), default: 1, reqd: 1 },
			], resolve, __("Verify {0}", [button.dataset.itemCode]), __("Verify item"));
		});
		const { message } = await frappe.call({
			method: "warehouse_erp.fulfillment.verify_pick_item",
			type: "POST",
			args: { pick_list: task.name, location: button.dataset.location, barcode: values.barcode, quantity: values.quantity },
			freeze: true,
			freeze_message: __("Verifying item with ERPNext…"),
		});
		dialog.hide();
		const scanned = message.serial_no || message.batch_no || message.item_code;
		frappe.show_alert({ message: __("{0} verified — {1}: {2} of {3} picked", [scanned, message.item_code, message.picked_qty, message.required_qty]), indicator: message.complete ? "green" : "blue" });
		this.open_task(task.name);
	}

	async complete_pick(task, dialog) {
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(__("Submit Pick List {0}? ERPNext will run its stock and serial/batch validations.", [task.name]), () => resolve(true), () => resolve(false));
		});
		if (!confirmed) return;
		const { message } = await frappe.call({
			method: "warehouse_erp.fulfillment.complete_pick_list",
			type: "POST",
			args: { pick_list: task.name },
			freeze: true,
			freeze_message: __("Completing Pick List with ERPNext…"),
		});
		dialog.hide();
		frappe.show_alert({ message: __("{0} completed: {1}", [message.pick_list, message.status]), indicator: "green" });
		this.refresh();
	}

	async resolve_shortage(task, dialog) {
		const values = await new Promise((resolve) => {
			frappe.prompt([{ fieldname: "reason", fieldtype: "Small Text", label: __("Shortage reason and resolution note"), reqd: 1 }], resolve, __("Resolve shortage"), __("Reallocate unpicked rows"));
		});
		const { message } = await frappe.call({
			method: "warehouse_erp.fulfillment.resolve_pick_shortage",
			type: "POST",
			args: { pick_list: task.name, reason: values.reason },
			freeze: true,
			freeze_message: __("Reallocating available stock with ERPNext…"),
		});
		dialog.hide();
		frappe.show_alert({
			message: message.unallocated_qty ? __("Stock refreshed; {0} units remain unallocated.", [message.unallocated_qty]) : __("All unpicked quantities were reallocated."),
			indicator: message.unallocated_qty ? "orange" : "green",
		});
		await this.refresh();
		this.open_task(task.name);
	}
}
