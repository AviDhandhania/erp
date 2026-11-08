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
		this.state = { page: 1, search: "", match_type: "like" };
		this.salespeople = [];
		this.setup_dom();
		this.bind();
		this.refresh();
	}

	setup_dom() {
		this.page.main.html(`<div class="retailer-assignments">
			<div class="assignment-filter-area">
				<div class="assignment-search-box">
					<div class="input-group">
						<input class="form-control assignment-search" type="text" placeholder="${__("ID")}" autocomplete="off">
						<div class="input-group-btn">
							<button type="button" class="btn btn-default match-type-dropdown-btn" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" title="${__("Match Type")}">
								<span class="match-type-icon">≈</span>
							</button>
							<ul class="dropdown-menu match-type-dropdown-menu dropdown-menu-right">
								<li class="dropdown-item" data-match-type="=">${__("Equals")}</li>
								<li class="dropdown-item" data-match-type="like">${__("Like")}</li>
							</ul>
						</div>
					</div>
				</div>
				<div class="assignment-scope-info text-muted"></div>
			</div>
			<div class="frappe-list">
				<div class="result-container">
					<div class="result">
						<div class="list-row-container">
							<header class="level list-row-head text-muted">
								<div class="level-left list-header-subject">
									<div class="list-row-col list-col-id list-subject level">
										<span class="level-item select-like">
											<input class="list-header-checkbox list-check-all" type="checkbox" title="${__("Select All")}">
										</span>
										<span class="level-item list-header-title">${__("ID")}</span>
										<div class="list-col-resize-handle"></div>
									</div>
									<div class="list-row-col list-col-shop ellipsis">
										<span>${__("Shop Name")}</span>
										<div class="list-col-resize-handle"></div>
									</div>
									<div class="list-row-col list-col-territory ellipsis hidden-xs">
										<span>${__("Territory")}</span>
										<div class="list-col-resize-handle"></div>
									</div>
									<div class="list-row-col list-col-salesperson ellipsis hidden-xs">
										<span>${__("Current Salesperson")}</span>
									</div>
								</div>
								<div class="level-right list-col-action-head">
									<span class="list-count text-muted"></span>
								</div>
							</header>
						</div>
						<div class="assignment-rows">
							<div class="assignment-loading text-muted">${__("Loading authorized retailers…")}</div>
						</div>
					</div>
					<div class="assignment-pagination-wrap"></div>
				</div>
			</div>
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

		this.$root.on("change", ".list-check-all", (event) => {
			const isChecked = $(event.currentTarget).is(":checked");
			this.$root.find(".list-row-checkbox").prop("checked", isChecked);
		});

		this.$root.on("click", "[data-assignment-page]", (event) => {
			this.state.page = Number(event.currentTarget.dataset.assignmentPage);
			this.refresh();
		});

		this.$root.on("click", ".reassign-retailer", (event) => {
			event.stopPropagation();
			this.open_reassignment(event.currentTarget.dataset.customer);
		});

		this.$root.on("click", ".list-row", (event) => {
			if ($(event.target).is("input, button, a")) {
				return;
			}
			const customer = $(event.currentTarget).data("customer");
			if (customer) {
				this.open_reassignment(customer);
			}
		});
	}

	escape(value) {
		return frappe.utils.escape_html(value || "");
	}

	async refresh() {
		const { message } = await frappe.call({
			method: "clothing_erp.retailer_assignment.get_reassignment_directory",
			args: {
				page: this.state.page,
				search: this.state.search,
			},
		});
		this.salespeople = message.salespeople || [];
		this.render(message);
	}

	render(data) {
		if (data.scope_required) {
			this.$root.find(".assignment-scope-info").text("");
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
			this.$root.find(".assignment-pagination-wrap").empty();
			this.$root.find(".list-count").text("");
			return;
		}

		this.$root.find(".list-count").text(
			data.retailers.length === 1 ? __("1 item") : __("{0} items", [data.retailers.length])
		);

		const rowsHtml = data.retailers.map((row) => {
			const id = this.escape(row.name);
			const shopName = this.escape(row.customer_name || row.name);
			const territory = this.escape(row.territory || "");
			const salesperson = this.escape(row.current_salesperson || __("Unassigned"));
			const salespersonClass = row.current_salesperson ? "" : "text-muted";

			return `<div class="list-row-container" tabindex="1">
				<div class="level list-row" data-customer="${id}">
					<div class="level-left list-header-subject ellipsis">
						<div class="list-row-col list-col-id list-subject level">
							<span class="level-item select-like">
								<input class="list-row-checkbox" type="checkbox" data-customer="${id}">
							</span>
							<span class="level-item bold ellipsis">
								<a class="ellipsis bold reassign-retailer" data-customer="${id}" title="${id}">
									${id}
								</a>
							</span>
						</div>
						<div class="list-row-col list-col-shop ellipsis">
							<span class="ellipsis" title="${shopName}">${shopName}</span>
						</div>
						<div class="list-row-col list-col-territory ellipsis hidden-xs">
							<span class="ellipsis text-muted" title="${territory}">${territory}</span>
						</div>
						<div class="list-row-col list-col-salesperson ellipsis hidden-xs">
							<span class="ellipsis ${salespersonClass}" title="${salesperson}">${salesperson}</span>
						</div>
					</div>
					<div class="level-right list-col-action">
						<button class="btn btn-default btn-sm reassign-retailer" data-customer="${id}">
							${__("Reassign")}
						</button>
					</div>
				</div>
			</div>`;
		}).join("");

		this.$root.find(".assignment-rows").html(rowsHtml);

		const page = data.pagination.page;
		this.$root.find(".assignment-pagination-wrap").html(`
			<div class="list-paging-area level">
				<div class="level-left">
					<div class="btn-group">
						<button class="btn btn-default btn-sm active" disabled>20</button>
					</div>
					<span class="text-muted ml-3" style="font-size: var(--text-sm);">${__("Page {0}", [page])}</span>
				</div>
				<div class="level-right">
					<div class="btn-group">
						<button class="btn btn-default btn-sm" data-assignment-page="${page - 1}" ${page === 1 ? "disabled" : ""}>
							${__("Previous")}
						</button>
						<button class="btn btn-default btn-sm" data-assignment-page="${page + 1}" ${data.pagination.has_more ? "" : "disabled"}>
							${__("Next")}
						</button>
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
