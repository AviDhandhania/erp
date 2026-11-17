frappe.pages["clothing-orders"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Clothing Orders"),
		single_column: true,
	});
	new ClothingOrders(page);
};

class ClothingOrders {
	constructor(page) {
		this.page = page;
		this.state = { page: 1, page_size: 20, search: "", status: "all" };
		this.setup_dom();
		this.bind();
		this.refresh();
	}

	setup_dom() {
		this.page.main.html(`<div class="clothing-orders">
			<section class="orders-panel" aria-label="${__("Clothing orders")}">
				<div class="orders-toolbar">
					<input class="form-control orders-search" type="search" placeholder="${__("Search order or retailer")}" aria-label="${__("Search order or retailer")}" autocomplete="off">
					<select class="form-control orders-status" aria-label="${__("Order status")}">
						<option value="all">${__("All statuses")}</option>
						<option value="draft">${__("Draft")}</option>
						<option value="submitted">${__("Submitted")}</option>
						<option value="cancelled">${__("Cancelled")}</option>
					</select>
					<span class="orders-count text-muted"></span>
				</div>
				<div class="orders-table" role="table">
					<div class="orders-table-head orders-grid" role="row">
						<div role="columnheader">${__("Order")}</div>
						<div role="columnheader">${__("Retailer")}</div>
						<div class="orders-date" role="columnheader">${__("Order date")}</div>
						<div class="orders-qty" role="columnheader">${__("Units")}</div>
						<div class="orders-total" role="columnheader">${__("Total")}</div>
						<div class="orders-status-column" role="columnheader">${__("Status")}</div>
					</div>
					<div class="orders-rows" role="rowgroup"></div>
				</div>
				<div class="orders-pagination-wrap"></div>
			</section>
		</div>`);
		this.$root = this.page.main.find(".clothing-orders");
	}

	bind() {
		let search_timer;
		this.$root.find(".orders-search").on("input", (event) => {
			clearTimeout(search_timer);
			search_timer = setTimeout(() => {
				this.state.search = event.target.value;
				this.state.page = 1;
				this.refresh();
			}, 300);
		});
		this.$root.find(".orders-status").on("change", (event) => {
			this.state.status = event.target.value;
			this.state.page = 1;
			this.refresh();
		});
		this.$root.on("click", "[data-orders-page]", (event) => {
			this.state.page = Number(event.currentTarget.dataset.ordersPage);
			this.refresh();
		});
		this.$root.on("click", "[data-orders-page-size]", (event) => {
			this.state.page_size = Number(event.currentTarget.dataset.ordersPageSize);
			this.state.page = 1;
			this.refresh();
		});
		this.$root.on("click", ".orders-row", (event) => this.open_order(event.currentTarget.dataset.order));
		this.$root.on("keydown", ".orders-row", (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				this.open_order(event.currentTarget.dataset.order);
			}
		});
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	async refresh() {
		this.$root.find(".orders-rows").html(`<div class="orders-message text-muted">${__("Loading orders…")}</div>`);
		const { message } = await frappe.call({
			method: "sales_erp.ordering.get_clothing_orders",
			args: {
				search: this.state.search,
				state: this.state.status,
				page: this.state.page,
				page_size: this.state.page_size,
			},
		});
		this.render(message);
	}

	status_indicator(order) {
		if (Number(order.docstatus) === 2) return "red";
		if (Number(order.docstatus) === 0) return "orange";
		if (["Completed", "Closed"].includes(order.status)) return "green";
		return "blue";
	}

	render(data) {
		const orders = data.orders || [];
		this.$root.find(".orders-count").text(orders.length === 1 ? __("1 order") : __("{0} orders", [orders.length]));
		if (!orders.length) {
			this.$root.find(".orders-rows").html(`<div class="orders-message text-muted">${__("No authorized Clothing ERP orders found.")}</div>`);
		} else {
			this.$root.find(".orders-rows").html(orders.map((order) => {
				const retailer = order.customer_name || order.customer;
				return `<div class="orders-row orders-grid" data-order="${this.escape(order.name)}" role="row" tabindex="0">
					<div class="orders-name ellipsis" role="cell" title="${this.escape(order.name)}">${this.escape(order.name)}</div>
					<div class="ellipsis" role="cell" title="${this.escape(retailer)}">${this.escape(retailer)}</div>
					<div class="orders-date" role="cell">${this.escape(frappe.datetime.str_to_user(order.transaction_date))}</div>
					<div class="orders-qty" role="cell">${format_number(order.total_qty || 0)}</div>
					<div class="orders-total" role="cell">${format_currency(order.grand_total || 0, order.currency)}</div>
					<div class="orders-status-column" role="cell"><span class="indicator-pill ${this.status_indicator(order)}">${this.escape(order.status)}</span></div>
				</div>`;
			}).join(""));
		}
		this.render_pagination(data.pagination);
	}

	render_pagination(pagination) {
		const sizes = [20, 50].map((size) => `<button type="button" class="btn btn-default btn-sm orders-page-size ${pagination.page_size === size ? "active" : ""}" data-orders-page-size="${size}" aria-pressed="${pagination.page_size === size}">${size}</button>`).join("");
		this.$root.find(".orders-pagination-wrap").html(`<div class="orders-pagination">
			<div class="orders-page-size-control"><span class="text-muted">${__("Rows per page")}</span>${sizes}</div>
			<div class="orders-page-nav">
				<span class="orders-page-label text-muted">${__("Page {0}", [pagination.page])}</span>
				<button type="button" class="btn btn-default btn-sm" data-orders-page="${pagination.page - 1}" ${pagination.page === 1 ? "disabled" : ""}>${__("Previous")}</button>
				<button type="button" class="btn btn-default btn-sm" data-orders-page="${pagination.page + 1}" ${pagination.has_more ? "" : "disabled"}>${__("Next")}</button>
			</div>
		</div>`);
	}

	async open_order(name) {
		const { message: order } = await frappe.call({
			method: "sales_erp.ordering.get_clothing_order",
			args: { name },
			freeze: true,
			freeze_message: __("Loading order…"),
		});
		const dialog = new frappe.ui.Dialog({ title: order.name, size: "extra-large" });
		const items = order.items.map((item) => `<tr>
			<td><strong>${this.escape(item.item_name || item.item_code)}</strong><small>${this.escape(item.item_code)}</small></td>
			<td class="text-right">${format_number(item.qty)} ${this.escape(item.stock_uom)}</td>
			<td class="text-right">${format_currency(item.rate, order.currency)}</td>
			<td class="text-right">${format_currency(item.amount, order.currency)}</td>
		</tr>`).join("");
		dialog.$body.html(`<div class="order-detail-summary">
			<div><span>${__("Retailer")}</span><strong>${this.escape(order.customer_name || order.customer)}</strong></div>
			<div><span>${__("Status")}</span><strong>${this.escape(order.status)}</strong></div>
			<div><span>${__("Order date")}</span><strong>${this.escape(frappe.datetime.str_to_user(order.transaction_date))}</strong></div>
			<div><span>${__("Delivery date")}</span><strong>${this.escape(frappe.datetime.str_to_user(order.delivery_date))}</strong></div>
		</div>
		<div class="order-detail-table"><table class="table table-bordered"><thead><tr><th>${__("Item")}</th><th class="text-right">${__("Quantity")}</th><th class="text-right">${__("Rate")}</th><th class="text-right">${__("Amount")}</th></tr></thead><tbody>${items}</tbody></table></div>
		<div class="order-detail-totals">
			<div><span>${__("Net total")}</span><strong>${format_currency(order.net_total, order.currency)}</strong></div>
			<div><span>${__("Taxes and charges")}</span><strong>${format_currency(order.total_taxes_and_charges, order.currency)}</strong></div>
			<div class="grand-total"><span>${__("Grand total")}</span><strong>${format_currency(order.rounded_total || order.grand_total, order.currency)}</strong></div>
		</div>`);
		if (order.review.workflow) {
			dialog.$body.prepend(`<div class="alert alert-info">${__("This order uses ERPNext Workflow {0}. Clothing ERP will not bypass its configured approval actions.", [this.escape(order.review.workflow)])}</div>`);
		}
		if (order.review.can_submit) {
			dialog.set_primary_action(__("Submit order"), () => this.submit_order(order.name, dialog));
		}
		if (order.review.can_cancel) {
			dialog.set_primary_action(__("Cancel order"), () => this.cancel_order(order.name, dialog));
		}
		if (order.review.can_edit) {
			dialog.set_secondary_action(() => {
				dialog.hide();
				frappe.set_route("Form", "Sales Order", order.name);
			});
			dialog.set_secondary_action_label(__("Edit draft in ERPNext"));
		}
		dialog.show();
	}

	async submit_order(name, dialog) {
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				__("Submit order {0}? ERPNext will apply current credit, authorization, commission and stock-reservation settings.", [this.escape(name)]),
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) return;
		const { message } = await frappe.call({
			method: "sales_erp.ordering.submit_clothing_order",
			type: "POST",
			args: { name },
			freeze: true,
			freeze_message: __("Submitting with ERPNext validations…"),
		});
		dialog.hide();
		frappe.show_alert({ message: __("Order {0} submitted", [message.name]), indicator: "green" });
		this.refresh();
	}

	async cancel_order(name, dialog) {
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				__("Cancel order {0}? ERPNext will validate linked deliveries and release reservations where allowed.", [this.escape(name)]),
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) return;
		const { message } = await frappe.call({
			method: "sales_erp.ordering.cancel_clothing_order",
			type: "POST",
			args: { name },
			freeze: true,
			freeze_message: __("Cancelling with ERPNext validations…"),
		});
		dialog.hide();
		frappe.show_alert({ message: __("Order {0} cancelled", [message.name]), indicator: "orange" });
		this.refresh();
	}
}
