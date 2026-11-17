frappe.pages["product-pricing"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Product Pricing"), single_column: true });
	new ProductPricing(page);
};

class ProductPricing {
	constructor(page) {
		this.page = page;
		this.state = { search: "", price_list: "", page: 1, page_size: 12 };
		this.setup();
		this.bind();
		this.refresh();
	}

	setup() {
		this.page.main.html(`<div class="product-pricing"><section class="pricing-panel">
			<div class="pricing-toolbar"><input class="form-control pricing-search" type="search" placeholder="${__("Search product, style or SKU")}"><select class="form-control pricing-price-list" aria-label="${__("Selling Price List")}"></select><span class="pricing-currency text-muted"></span></div>
			<div class="pricing-help text-muted">${__("Enter one rate to update every enabled Size variant. Prices remain native ERPNext Item Price records.")}</div>
			<div class="pricing-products"></div><div class="pricing-pagination"></div>
		</section></div>`);
		this.$root = this.page.main.find(".product-pricing");
	}

	bind() {
		let timer;
		this.$root.find(".pricing-search").on("input", (event) => {
			clearTimeout(timer);
			timer = setTimeout(() => { this.state.search = event.target.value; this.state.page = 1; this.refresh(); }, 300);
		});
		this.$root.find(".pricing-price-list").on("change", (event) => { this.state.price_list = event.target.value; this.state.page = 1; this.refresh(); });
		this.$root.on("click", "[data-pricing-page]", (event) => { this.state.page = Number(event.currentTarget.dataset.pricingPage); this.refresh(); });
		this.$root.on("click", ".apply-template-price", (event) => this.apply_price(event.currentTarget.dataset.template));
	}

	escape(value) { return frappe.utils.escape_html(String(value ?? "")); }

	async refresh() {
		this.$root.find(".pricing-products").html(`<div class="pricing-message text-muted">${__("Loading products…")}</div>`);
		const { message } = await frappe.call({ method: "sales_erp.pricing.get_product_pricing", args: this.state });
		this.state.price_list = message.price_list;
		const $list = this.$root.find(".pricing-price-list").empty();
		message.price_lists.forEach((name) => $list.append($("<option>", { value: name, text: name, selected: name === message.price_list })));
		this.$root.find(".pricing-currency").text(message.currency);
		this.render(message);
	}

	render(data) {
		const products = data.products || [];
		this.$root.find(".pricing-products").html(products.length ? products.map((product) => {
			const image = product.image ? `<img src="${this.escape(product.image)}" alt="">` : `<span class="pricing-image-placeholder">${frappe.utils.icon("image", "lg")}</span>`;
			const rows = product.variants.map((variant) => `<tr><td><strong>${this.escape(variant.size)}</strong><small>${this.escape(variant.item_code)}</small></td><td>${this.escape(variant.uom)}</td><td>${variant.ambiguous ? `<span class="text-danger">${__("Overlapping prices")}</span>` : variant.rate == null ? `<span class="text-muted">${__("Not priced")}</span>` : format_currency(variant.rate, data.currency)}</td></tr>`).join("");
			const blocked = !product.variants.length || product.variants.some((row) => row.ambiguous);
			return `<article class="pricing-card"><header>${image}<div><h3>${this.escape(product.item_name)}</h3><p>${this.escape(product.name)}</p></div></header><div class="pricing-table-wrap"><table class="table"><thead><tr><th>${__("Size / SKU")}</th><th>${__("UOM")}</th><th>${__("Current price")}</th></tr></thead><tbody>${rows || `<tr><td colspan="3" class="text-muted">${__("No enabled Size variants")}</td></tr>`}</tbody></table></div><footer><div class="input-group"><span class="input-group-addon">${this.escape(data.currency)}</span><input class="form-control template-rate" type="number" min="0.01" step="0.01" placeholder="${__("Price for all sizes")}" aria-label="${__("Price for all sizes")}"></div><button class="btn btn-primary btn-sm apply-template-price" data-template="${this.escape(product.name)}" ${blocked ? "disabled" : ""}>${__("Apply to all sizes")}</button></footer></article>`;
		}).join("") : `<div class="pricing-message text-muted">${__("No matching clothing products found.")}</div>`);
		const p = data.pagination;
		this.$root.find(".pricing-pagination").html(`<button class="btn btn-default" data-pricing-page="${p.page - 1}" ${p.page === 1 ? "disabled" : ""}>${__("Previous")}</button><span>${__("Page {0}", [p.page])}</span><button class="btn btn-default" data-pricing-page="${p.page + 1}" ${p.has_more ? "" : "disabled"}>${__("Next")}</button>`);
	}

	apply_price(template) {
		const $card = this.$root.find(`.apply-template-price[data-template="${CSS.escape(template)}"]`).closest(".pricing-card");
		const rate = Number($card.find(".template-rate").val());
		if (!Number.isFinite(rate) || rate <= 0) { frappe.msgprint(__("Enter a positive price.")); return; }
		frappe.confirm(
			__("Set {0} for every enabled size of {1} in {2}?", [format_currency(rate, this.$root.find(".pricing-currency").text()), this.escape(template), this.escape(this.state.price_list)]),
			async () => {
				const { message } = await frappe.call({ method: "sales_erp.pricing.set_template_price", type: "POST", args: { template, price_list: this.state.price_list, rate }, freeze: true, freeze_message: __("Updating native Item Prices…") });
				frappe.show_alert({ message: __("Updated {0} size prices", [message.changed.length]), indicator: "green" });
				this.refresh();
			}
		);
	}
}
