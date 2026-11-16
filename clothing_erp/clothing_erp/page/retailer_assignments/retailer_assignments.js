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
		this.state = { page: 1, page_size: 20, search: "", match_type: "like" };
		this.salespeople = [];
		this.setup_dom();
		this.bind();
		this.refresh();
	}

	setup_dom() {
		this.page.main.html(`<div class="retailer-assignments">
			<section class="assignment-panel" aria-label="${__("Retailer assignments")}">
				<div class="assignment-toolbar">
					<div class="assignment-search-box">
						<div class="input-group">
							<input class="form-control assignment-search" type="search" placeholder="${__("Search retailer ID or shop name")}" aria-label="${__("Search retailer ID or shop name")}" autocomplete="off">
							<div class="input-group-btn">
								<button type="button" class="btn btn-default match-type-dropdown-btn" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" title="${__("Match Type")}">
									<span class="match-type-icon">≈</span>
								</button>
								<ul class="dropdown-menu match-type-dropdown-menu dropdown-menu-right">
									<li class="dropdown-item" data-match-type="like">${__("Like (≈)")}</li>
									<li class="dropdown-item" data-match-type="=">${__("Equals (=)")}</li>
								</ul>
							</div>
						</div>
					</div>
					<div class="assignment-toolbar-meta">
						<span class="assignment-scope-info text-muted"></span>
						<span class="assignment-item-count text-muted"></span>
					</div>
				</div>
				<div class="assignment-table" role="table">
					<div class="assignment-table-head assignment-grid" role="row">
						<div role="columnheader">${__("ID")}</div>
						<div role="columnheader">${__("Shop Name")}</div>
						<div class="assignment-territory" role="columnheader">${__("Territory")}</div>
						<div role="columnheader">${__("Responsible ASM")}</div>
						<div class="assignment-action-heading" role="columnheader">${__("Action")}</div>
					</div>
					<div class="assignment-rows" role="rowgroup">
						<div class="assignment-loading text-muted">${__("Loading authorized retailers…")}</div>
					</div>
				</div>
				<div class="assignment-pagination-wrap"></div>
			</section>
		</div>`);
		this.$root = this.page.main.find(".retailer-assignments");
	}

	bind() {
		let timer;
		const $search = this.$root.find(".assignment-search");
		$search.on("input", (event) => {
			clearTimeout(timer);
			timer = setTimeout(() => {
				this.state.search = event.target.value.trim();
				this.state.page = 1;
				this.refresh();
			}, 300);
		});

		this.$root.find(".match-type-dropdown-menu .dropdown-item").on("click", (event) => {
			event.preventDefault();
			const matchType = $(event.currentTarget).data("match-type");
			this.state.match_type = matchType;
			this.$root.find(".match-type-icon").text(matchType === "=" ? "=" : "≈");
			if (this.state.search) {
				this.state.page = 1;
				this.refresh();
			}
		});

		this.$root.on("click", "[data-assignment-page]", (event) => {
			this.state.page = Number(event.currentTarget.dataset.assignmentPage);
			this.refresh();
		});

		this.$root.on("click", "[data-assignment-page-size]", (event) => {
			this.state.page_size = Number(event.currentTarget.dataset.assignmentPageSize);
			this.state.page = 1;
			this.refresh();
		});

		this.$root.on("click", ".reassign-retailer", (event) => {
			event.stopPropagation();
			this.open_reassignment(event.currentTarget.dataset.customer);
		});

		this.$root.on("click", ".assignment-row", (event) => {
			if ($(event.target).is("input, button, a")) {
				return;
			}
			const customer = $(event.currentTarget).data("customer");
			if (customer) {
				this.open_reassignment(customer);
			}
		});

		this.$root.on("keydown", ".assignment-row", (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				this.open_reassignment(event.currentTarget.dataset.customer);
			}
		});
	}

	escape(value) {
		return frappe.utils.escape_html(value || "");
	}

	async refresh() {
		this.$root.find(".assignment-rows").html(
			`<div class="assignment-loading text-muted">${__("Loading authorized retailers…")}</div>`
		);
		const { message } = await frappe.call({
			method: "clothing_erp.retailer_assignment.get_reassignment_directory",
			args: {
				page: this.state.page,
				page_size: this.state.page_size,
				search: this.state.search,
				match_type: this.state.match_type,
			},
		});
		this.salespeople = message.salespeople || [];
		this.render(message);
	}

	render(data) {
		if (data.scope_required) {
			this.$root.find(".assignment-scope-info").text("");
			this.$root.find(".assignment-item-count").text("");
			this.$root.find(".assignment-rows").html(
				`<div class="assignment-empty text-muted">${__("No Territory is assigned to your manager account. Ask an administrator to add a Territory User Permission.")}</div>`
			);
			this.$root.find(".assignment-pagination-wrap").empty();
			return;
		}

		const scopeText = data.territories == null
			? __("Administrator scope — all retailers")
			: __("Authorized territories: {0}", [data.territories.join(", ")]);
		this.$root.find(".assignment-scope-info").text(scopeText);

		if (!data.retailers || !data.retailers.length) {
			this.$root.find(".assignment-rows").html(
				`<div class="assignment-empty text-muted">${__("No authorized retailers found.")}</div>`
			);
			this.$root.find(".assignment-item-count").text(__("0 items"));
			this.render_pagination(data.pagination);
			return;
		}

		this.$root.find(".assignment-item-count").text(
			data.retailers.length === 1 ? __("1 item") : __("{0} items", [data.retailers.length])
		);

		const rowsHtml = data.retailers.map((row) => {
			const id = this.escape(row.name);
			const shopName = this.escape(row.customer_name || row.name);
			const territory = this.escape(row.territory || "");
			const salesperson = this.escape(row.current_salesperson || __("Unassigned"));
			const salespersonClass = row.current_salesperson ? "" : "text-muted";

			return `<div class="assignment-row assignment-grid" data-customer="${id}" role="row" tabindex="0">
				<div class="assignment-id ellipsis" role="cell">
					<button type="button" class="assignment-id-button reassign-retailer ellipsis" data-customer="${id}" title="${id}">${id}</button>
				</div>
				<div class="ellipsis" role="cell" title="${shopName}">${shopName}</div>
				<div class="assignment-territory ellipsis text-muted" role="cell" title="${territory}">${territory}</div>
				<div class="ellipsis ${salespersonClass}" role="cell" title="${salesperson}">${salesperson}</div>
				<div class="assignment-action" role="cell">
					<button type="button" class="btn btn-default btn-xs reassign-retailer" data-customer="${id}">${__("Reassign")}</button>
				</div>
			</div>`;
		}).join("");

		this.$root.find(".assignment-rows").html(rowsHtml);
		this.render_pagination(data.pagination);
	}

	render_pagination(pagination) {
		const page = pagination.page;
		const pageSizes = [20, 50].map((size) => `
			<button type="button" class="btn btn-default btn-xs assignment-page-size ${this.state.page_size === size ? "active" : ""}"
				data-assignment-page-size="${size}" aria-pressed="${this.state.page_size === size}">${size}</button>`).join("");
		this.$root.find(".assignment-pagination-wrap").html(`
			<div class="assignment-pagination">
				<div class="assignment-page-size-control">
					<span class="text-muted">${__("Rows per page")}</span>
					<div class="btn-group">${pageSizes}</div>
				</div>
				<div class="assignment-page-nav">
					<span class="assignment-page-label text-muted">${__("Page {0}", [page])}</span>
					<div class="btn-group">
						<button type="button" class="btn btn-default btn-sm" data-assignment-page="${page - 1}" ${page === 1 ? "disabled" : ""}>${__("Previous")}</button>
						<button type="button" class="btn btn-default btn-sm" data-assignment-page="${page + 1}" ${pagination.has_more ? "" : "disabled"}>${__("Next")}</button>
					</div>
				</div>
			</div>
		`);
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
				{ fieldtype: "Data", fieldname: "current_salesperson", label: __("Current Responsible ASM"), default: message.current_salesperson || __("Unassigned"), read_only: 1 },
				{ fieldtype: "Select", fieldname: "new_salesperson", label: __("New Responsible ASM"), options: salespeople, reqd: 1 },
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
