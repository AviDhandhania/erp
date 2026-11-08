frappe.pages["clothing-catalogue"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Clothing Catalogue"), single_column: true });
	new ClothingCatalogue(page);
};

class ClothingCatalogue {
	constructor(page) {
		this.page = page;
		this.state = { page: 1, search: "", item_group: "", brand: "", customer: "", collection: "", fabric: "", fit: "", season: "" };
		this.selection = new Map();
		this.order_request_id = null;
		this.products = new Map();
		this.page.main.html(`<div class="clothing-catalogue">
			<div class="catalogue-toolbar">
				<input class="form-control catalogue-search" type="search" placeholder="${__("Search style or SKU")}">
				<select class="form-control catalogue-customer"><option value="">${__("Generic prices — select retailer")}</option></select>
				<select class="form-control catalogue-group"><option value="">${__("All categories")}</option></select>
				<select class="form-control catalogue-brand"><option value="">${__("All brands")}</option></select>
			</div>
			<details class="catalogue-more-filters">
				<summary>${__("More clothing filters")}</summary>
				<div class="catalogue-metadata-filters">
					<select class="form-control" data-catalogue-filter="collection"><option value="">${__("All collections")}</option></select>
					<select class="form-control" data-catalogue-filter="fabric"><option value="">${__("All fabrics")}</option></select>
					<select class="form-control" data-catalogue-filter="fit"><option value="">${__("All fits")}</option></select>
					<select class="form-control" data-catalogue-filter="season"><option value="">${__("All seasons")}</option></select>
				</div>
			</details>
			<div class="catalogue-status text-muted" role="status"></div>
			<div class="catalogue-grid"></div>
			<div class="catalogue-pagination"></div>
			<div class="catalogue-selection" aria-live="polite"></div>
		</div>`);
		this.$root = this.page.main.find(".clothing-catalogue");
		this.bind();
		this.load_filters();
		this.refresh();
	}

	bind() {
		let timer;
		this.$root.find(".catalogue-search").on("input", (event) => {
			clearTimeout(timer);
			timer = setTimeout(() => { this.state.search = event.target.value; this.state.page = 1; this.refresh(); }, 300);
		});
		this.$root.find(".catalogue-group, .catalogue-brand, .catalogue-customer").on("change", (event) => {
			const field = event.target.classList.contains("catalogue-group")
				? "item_group"
				: event.target.classList.contains("catalogue-brand") ? "brand" : "customer";
			this.state[field] = event.target.value;
			if (field === "customer") {
				this.selection.clear();
				this.order_request_id = null;
				this.render_selection();
			}
			this.state.page = 1;
			this.refresh();
		});
		this.$root.find("[data-catalogue-filter]").on("change", (event) => {
			this.state[event.currentTarget.dataset.catalogueFilter] = event.currentTarget.value;
			this.state.page = 1;
			this.refresh();
		});
		this.$root.on("click", "[data-page]", (event) => {
			this.state.page = Number(event.currentTarget.dataset.page);
			this.refresh();
			window.scrollTo({ top: 0, behavior: "smooth" });
		});
		this.$root.on("input", ".variant-qty", (event) => {
			const input = event.currentTarget;
			const quantity = Math.max(0, Number(input.value) || 0);
			if (quantity) {
				this.selection.set(input.dataset.itemCode, {
					quantity,
					rate: Number(input.dataset.rate) || 0,
					currency: input.dataset.currency,
				});
			} else {
				this.selection.delete(input.dataset.itemCode);
			}
			this.order_request_id = null;
			this.render_selection();
		});
		this.$root.on("click", ".clear-selection", () => {
			this.selection.clear();
			this.order_request_id = null;
			this.$root.find(".variant-qty").val("");
			this.render_selection();
		});
		this.$root.on("click", ".create-sales-order", () => this.create_sales_order());
		this.$root.on("click", ".catalogue-photo-trigger", (event) => {
			this.open_gallery(this.products.get(event.currentTarget.dataset.itemCode));
		});
	}

	async load_filters() {
		const { message } = await frappe.call("clothing_erp.catalogue.get_catalogue_filters");
		this.fill_select(".catalogue-group", message.item_groups);
		this.fill_select(".catalogue-brand", message.brands);
		["collection", "fabric", "fit", "season"].forEach((field) => {
			this.fill_select(`[data-catalogue-filter="${field}"]`, message[field]);
		});
		const $retailers = this.$root.find(".catalogue-customer");
		message.retailers.forEach((retailer) => $retailers.append($("<option>", {
			value: retailer.name,
			text: retailer.customer_name === retailer.name ? retailer.name : `${retailer.customer_name} (${retailer.name})`,
		})));
	}

	fill_select(selector, values) {
		const $select = this.$root.find(selector);
		values.forEach((value) => $select.append($("<option>", { value, text: value })));
	}

	async refresh() {
		this.$root.find(".catalogue-status").text(__("Loading catalogue…"));
		this.$root.find(".catalogue-grid").attr("aria-busy", "true");
		try {
			const { message } = await frappe.call({ method: "clothing_erp.catalogue.get_catalogue", args: this.state });
			this.render(message);
		} finally {
			this.$root.find(".catalogue-grid").removeAttr("aria-busy");
		}
	}

	escape(value) { return frappe.utils.escape_html(value || ""); }

	attribute(variant, candidates) {
		const row = variant.attributes.find((entry) => {
			const attribute = entry.attribute.toLowerCase();
			return candidates.some((candidate) => attribute === candidate || attribute.endsWith(` ${candidate}`));
		});
		return row ? row.value : "—";
	}

	render(data) {
		this.products = new Map(data.products.map((product) => [product.item_code, product]));
		const $grid = this.$root.find(".catalogue-grid").empty();
		const price_context = data.customer ? __("Retailer pricing: {0}", [data.customer]) : __("Generic prices");
		this.$root.find(".catalogue-status").text(data.products.length ? `${price_context} · ${__("Price List: {0}", [data.price_list])}` : __("No matching clothing products"));
		data.products.forEach((product) => $grid.append(this.product_card(product)));
		const page = data.pagination.page;
		this.$root.find(".catalogue-pagination").html(`
			<button class="btn btn-default" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>${__("Previous")}</button>
			<span>${__("Page {0}", [page])}</span>
			<button class="btn btn-default" data-page="${page + 1}" ${data.pagination.has_more ? "" : "disabled"}>${__("Next")}</button>`);
		this.render_selection();
	}

	open_gallery(product) {
		if (!product || !product.images?.length) return;
		const dialog = new frappe.ui.Dialog({ title: product.item_name, size: "extra-large" });
		const slides = product.images.map((row, index) => `<figure class="catalogue-gallery-slide ${index ? "hidden" : ""}" data-gallery-index="${index}">
			<img src="${this.escape(row.image)}" alt="${this.escape(row.caption || product.item_name)}">
			${row.caption ? `<figcaption>${this.escape(row.caption)}</figcaption>` : ""}
		</figure>`).join("");
		dialog.$body.html(`<div class="catalogue-gallery">${slides}</div><div class="catalogue-gallery-controls">
			<button class="btn btn-default gallery-prev">${__("Previous")}</button><span class="gallery-count">1 / ${product.images.length}</span><button class="btn btn-default gallery-next">${__("Next")}</button>
		</div>`);
		let index = 0;
		const show = (next) => {
			index = (next + product.images.length) % product.images.length;
			dialog.$body.find(".catalogue-gallery-slide").addClass("hidden").filter(`[data-gallery-index="${index}"]`).removeClass("hidden");
			dialog.$body.find(".gallery-count").text(`${index + 1} / ${product.images.length}`);
		};
		dialog.$body.on("click", ".gallery-prev", () => show(index - 1));
		dialog.$body.on("click", ".gallery-next", () => show(index + 1));
		dialog.show();
	}

	render_selection() {
		const rows = [...this.selection.values()];
		const units = rows.reduce((total, row) => total + row.quantity, 0);
		const totals = rows.reduce((result, row) => {
			result[row.currency] = (result[row.currency] || 0) + row.quantity * row.rate;
			return result;
		}, {});
		const money = Object.entries(totals).map(([currency, total]) => format_currency(total, currency)).join(" · ");
		this.$root.find(".catalogue-selection").html(rows.length ? `
			<div><strong>${__("Draft selection")}</strong><span>${__("{0} variants · {1} units", [rows.length, units])}${money ? ` · ${money}` : ""}</span></div>
			<div class="catalogue-selection-actions">
				<button class="btn btn-default btn-sm clear-selection">${__("Clear")}</button>
				<button class="btn btn-primary btn-sm create-sales-order" ${this.state.customer ? "" : "disabled"}>${this.state.customer ? __("Create draft order") : __("Select retailer first")}</button>
			</div>` : "");
	}

	async create_sales_order() {
		if (!this.state.customer || !this.selection.size) return;
		const delivery_date = await new Promise((resolve) => {
			frappe.prompt([{
				fieldname: "delivery_date",
				fieldtype: "Date",
				label: __("Delivery Date"),
				default: frappe.datetime.now_date(),
				reqd: 1,
			}], ({ delivery_date: value }) => resolve(value), __("Create Draft Sales Order"), __("Create Draft"));
		});
		this.order_request_id ||= frappe.utils.get_random(40);
		const items = [...this.selection.entries()].map(([item_code, row]) => ({
			item_code,
			qty: row.quantity,
		}));
		const { message } = await frappe.call({
			method: "clothing_erp.ordering.create_draft_sales_order",
			type: "POST",
			args: {
				customer: this.state.customer,
				items: JSON.stringify(items),
				request_id: this.order_request_id,
				delivery_date,
			},
			freeze: true,
			freeze_message: __("Creating Sales Order with current ERPNext pricing…"),
		});
		this.selection.clear();
		this.order_request_id = null;
		frappe.show_alert({ message: __("Draft Sales Order {0} created", [message.name]), indicator: "green" });
		frappe.set_route("Form", "Sales Order", message.name);
	}

	product_card(product) {
		const image = product.image
			? `<button type="button" class="catalogue-photo-trigger catalogue-image-trigger" data-item-code="${this.escape(product.item_code)}" aria-label="${__("View photos for {0}", [this.escape(product.item_name)])}"><img src="${this.escape(product.image)}" alt=""></button>`
			: `<div class="catalogue-image-placeholder">${frappe.utils.icon("image", "lg")}</div>`;
		const gallery_action = product.images?.length
			? `<button type="button" class="btn btn-primary btn-sm catalogue-photo-trigger catalogue-gallery-action" data-item-code="${this.escape(product.item_code)}" title="${__("Open product gallery")}">${frappe.utils.icon("image", "sm")}<strong>${__("View photos ({0})", [product.images.length])}</strong></button>`
			: "";
		const rows = product.variants.map((variant) => `<tr>
			<td><strong>${this.escape(this.attribute(variant, ["size"]))}</strong><small>${this.escape(variant.item_code)}</small></td>
			<td>${variant.price == null ? `<span class="text-muted">${__("Not priced")}</span>` : format_currency(variant.price, variant.currency)}</td>
			<td><span class="stock-pill ${variant.available ? "in-stock" : "out-of-stock"}">${format_number(variant.actual_qty)} ${this.escape(variant.uom)}</span></td>
			<td><input class="form-control variant-qty" type="number" inputmode="numeric" min="0" step="1" aria-label="${__("Quantity for {0}", [this.escape(variant.item_code)])}" data-item-code="${this.escape(variant.item_code)}" data-rate="${variant.price || 0}" data-currency="${this.escape(variant.currency)}" value="${this.selection.get(variant.item_code)?.quantity || ""}" ${variant.price == null ? "disabled" : ""}></td>
		</tr>`).join("");
		const metadata = [product.style_code, product.collection, product.fabric, product.fit, product.season]
			.filter(Boolean)
			.map((value) => `<span>${this.escape(value)}</span>`)
			.join("");
		return `<article class="catalogue-card">
			<div class="catalogue-product-head">${image}<div><h3>${this.escape(product.item_name)}</h3><p>${this.escape(product.item_code)}</p><span class="catalogue-product-meta">${this.escape(product.brand || product.item_group)}</span><div class="catalogue-metadata">${metadata}</div>${gallery_action}</div></div>
			<div class="catalogue-table-wrap"><table class="table"><thead><tr><th>${__("Size / SKU")}</th><th>${__("Price")}</th><th>${__("On hand")}</th><th>${__("Qty")}</th></tr></thead><tbody>${rows || `<tr><td colspan="4">${__("No enabled variants")}</td></tr>`}</tbody></table></div>
		</article>`;
	}
}
