frappe.pages["retailer-assignments"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Sales Territory Assignments"),
		single_column: true,
	});
	wrapper.sales_territory_assignments = new SalesTerritoryAssignments(page);
};

frappe.pages["retailer-assignments"].refresh = (wrapper) => {
	if (wrapper.sales_territory_assignments) {
		wrapper.sales_territory_assignments.refresh();
	}
};

class SalesTerritoryAssignments {
	constructor(page) {
		this.page = page;
		this.state = { page: 1, page_size: 20, search: "", status: "Active" };
		this.is_admin = false;
		this.records = [];
		this.setup_dom();
		this.bind();
		this.refresh();
	}

	setup_dom() {
		this.page.main.html(`<div class="retailer-assignments">
			<section class="assignment-panel" aria-label="${__("Sales territory assignments")}">
				<div class="assignment-toolbar">
					<div class="assignment-search-box">
						<div class="input-group">
							<input class="form-control assignment-search" type="search" placeholder="${__("Search territory, ASM or RSM")}" aria-label="${__("Search territory, ASM or RSM")}" autocomplete="off">
							<div class="input-group-btn">
								<button type="button" class="btn btn-default status-filter-btn" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false" title="${__("Status filter")}">
									<span class="status-filter-label">${__("Active")}</span> <span class="caret"></span>
								</button>
								<ul class="dropdown-menu status-dropdown-menu dropdown-menu-right">
									<li class="dropdown-item" data-status="Active">${__("Active")}</li>
									<li class="dropdown-item" data-status="">${__("All statuses")}</li>
									<li class="dropdown-item" data-status="Superseded">${__("Superseded")}</li>
									<li class="dropdown-item" data-status="Cancelled">${__("Cancelled")}</li>
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
						<div role="columnheader">${__("Territory")}</div>
						<div role="columnheader">${__("Area Sales Manager")}</div>
						<div role="columnheader">${__("Supervising RSM")}</div>
						<div role="columnheader">${__("Status & Dates")}</div>
						<div class="assignment-action-heading" role="columnheader">${__("Actions")}</div>
					</div>
					<div class="assignment-rows" role="rowgroup">
						<div class="assignment-loading text-muted">${__("Loading territory assignments…")}</div>
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

		this.$root.find(".status-dropdown-menu .dropdown-item").on("click", (event) => {
			event.preventDefault();
			const status = $(event.currentTarget).data("status");
			this.state.status = status;
			const label = status ? status : __("All");
			this.$root.find(".status-filter-label").text(label);
			this.state.page = 1;
			this.refresh();
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

		this.$root.on("click", ".reassign-rsm-btn", (event) => {
			event.stopPropagation();
			const name = $(event.currentTarget).data("name");
			const record = this.records.find((r) => r.name === name);
			if (record) this.open_reassign_dialog(record);
		});

		this.$root.on("click", ".end-assignment-btn", (event) => {
			event.stopPropagation();
			const name = $(event.currentTarget).data("name");
			const record = this.records.find((r) => r.name === name);
			if (record) this.open_end_dialog(record);
		});

		this.$root.on("click", ".view-assignment-btn, .assignment-id-button", (event) => {
			event.stopPropagation();
			const name = $(event.currentTarget).data("name");
			const record = this.records.find((r) => r.name === name);
			if (record) this.open_view_dialog(record);
		});

		this.$root.on("click", ".assignment-row", (event) => {
			if ($(event.target).is("input, button, a")) {
				return;
			}
			const name = $(event.currentTarget).data("name");
			const record = this.records.find((r) => r.name === name);
			if (record) this.open_view_dialog(record);
		});
	}

	escape(value) {
		return frappe.utils.escape_html(value || "");
	}

	async refresh() {
		this.$root.find(".assignment-rows").html(
			`<div class="assignment-loading text-muted">${__("Loading territory assignments…")}</div>`
		);
		const { message } = await frappe.call({
			method: "sales_erp.supervision.get_asm_supervision_directory",
			args: {
				page: this.state.page,
				page_size: this.state.page_size,
				search: this.state.search,
				status: this.state.status || null,
			},
		});

		this.records = message.records || [];
		this.is_admin = !!message.is_admin;

		if (this.is_admin && !this.primary_action_added) {
			this.page.set_primary_action(__("Assign Territory"), () => {
				this.open_assign_dialog();
			}, "octicon octicon-plus");
			this.primary_action_added = true;
		}

		this.render(message);
	}

	render(data) {
		const scopeText = data.scope_info || "";
		this.$root.find(".assignment-scope-info").text(scopeText);

		if (!data.records || !data.records.length) {
			this.$root.find(".assignment-rows").html(
				`<div class="assignment-empty text-muted">${__("No territory assignments found.")}</div>`
			);
			this.$root.find(".assignment-item-count").text(__("0 items"));
			this.render_pagination(data.pagination);
			return;
		}

		this.$root.find(".assignment-item-count").text(
			data.records.length === 1 ? __("1 item") : __("{0} items", [data.records.length])
		);

		const rowsHtml = data.records.map((row) => {
			const id = this.escape(row.name);
			const territory = this.escape(row.territory || __("Unspecified"));
			const asm = this.escape(row.asm || "");
			const rsm = this.escape(row.rsm || "");
			const status = row.status || "Active";
			const statusClass = status === "Active" ? "badge-active" : (status === "Cancelled" ? "badge-cancelled" : "badge-superseded");
			const dateInfo = row.effective_from ? (row.effective_to ? `${row.effective_from} → ${row.effective_to}` : `From ${row.effective_from}`) : "";

			let actionButtons = "";
			if (this.is_admin && status === "Active") {
				actionButtons = `
					<button type="button" class="btn btn-default btn-xs reassign-rsm-btn" data-name="${id}" title="${__("Reassign supervising RSM")}">${__("Reassign RSM")}</button>
					<button type="button" class="btn btn-default btn-xs text-danger end-assignment-btn" data-name="${id}" title="${__("End assignment")}">${__("End")}</button>
				`;
			} else {
				actionButtons = `
					<button type="button" class="btn btn-default btn-xs view-assignment-btn" data-name="${id}">${__("View")}</button>
				`;
			}

			return `<div class="assignment-row assignment-grid" data-name="${id}" role="row" tabindex="0">
				<div class="assignment-id ellipsis" role="cell">
					<button type="button" class="assignment-id-button ellipsis" data-name="${id}" title="${territory}">${territory}</button>
				</div>
				<div class="ellipsis" role="cell" title="${asm}">${asm}</div>
				<div class="ellipsis text-muted" role="cell" title="${rsm}">${rsm}</div>
				<div class="ellipsis" role="cell">
					<span class="status-badge ${statusClass}">${status}</span>
					<small class="text-muted ml-1">${this.escape(dateInfo)}</small>
				</div>
				<div class="assignment-action" role="cell">
					<div class="btn-group">${actionButtons}</div>
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

	open_assign_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: __("Assign Sales Territory"),
			fields: [
				{
					fieldname: "territory",
					fieldtype: "Link",
					label: __("Sales Territory"),
					options: "Territory",
					get_query() {
						return { filters: { is_group: 0 } };
					},
					reqd: 1,
				},
				{
					fieldname: "asm",
					fieldtype: "Link",
					label: __("Area Sales Manager (ASM)"),
					options: "User",
					get_query() {
						return {
							query: "sales_erp.supervision.sales_role_user_query",
							filters: { role: "Clothing Area Sales Manager" },
						};
					},
					reqd: 1,
				},
				{
					fieldname: "rsm",
					fieldtype: "Link",
					label: __("Supervising Regional Sales Manager (RSM)"),
					options: "User",
					get_query() {
						return {
							query: "sales_erp.supervision.sales_role_user_query",
							filters: { role: "Clothing Regional Sales Manager" },
						};
					},
					reqd: 1,
				},
				{
					fieldname: "effective_from",
					fieldtype: "Date",
					label: __("Effective From"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				},
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Reason / Notes"),
				},
			],
			primary_action_label: __("Assign Territory"),
			primary_action: async (values) => {
				await frappe.call({
					method: "sales_erp.supervision.assign_asm_supervision",
					type: "POST",
					args: {
						territory: values.territory,
						asm: values.asm,
						rsm: values.rsm,
						effective_from: values.effective_from,
						reason: values.reason,
					},
					freeze: true,
					freeze_message: __("Assigning sales territory…"),
				});
				dialog.hide();
				frappe.show_alert({ message: __("Sales territory assigned"), indicator: "green" });
				this.refresh();
			},
		});
		dialog.show();
	}

	open_reassign_dialog(record) {
		const dialog = new frappe.ui.Dialog({
			title: __("Reassign Supervising RSM — {0}", [record.territory]),
			fields: [
				{
					fieldname: "territory",
					fieldtype: "Link",
					label: __("Sales Territory"),
					options: "Territory",
					default: record.territory,
					read_only: 1,
				},
				{
					fieldname: "asm",
					fieldtype: "Link",
					label: __("Area Sales Manager"),
					options: "User",
					default: record.asm,
					read_only: 1,
				},
				{
					fieldname: "current_rsm",
					fieldtype: "Data",
					label: __("Current Supervising RSM"),
					default: record.rsm,
					read_only: 1,
				},
				{
					fieldname: "new_rsm",
					fieldtype: "Link",
					label: __("New Supervising RSM"),
					options: "User",
					get_query() {
						return {
							query: "sales_erp.supervision.sales_role_user_query",
							filters: { role: "Clothing Regional Sales Manager" },
						};
					},
					reqd: 1,
				},
				{
					fieldname: "effective_from",
					fieldtype: "Date",
					label: __("Effective From"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				},
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Reason for Reassignment"),
					reqd: 1,
				},
			],
			primary_action_label: __("Reassign RSM"),
			primary_action: async (values) => {
				await frappe.call({
					method: "sales_erp.supervision.assign_asm_supervision",
					type: "POST",
					args: {
						territory: record.territory,
						asm: record.asm,
						rsm: values.new_rsm,
						effective_from: values.effective_from,
						reason: values.reason,
					},
					freeze: true,
					freeze_message: __("Reassigning supervising RSM…"),
				});
				dialog.hide();
				frappe.show_alert({ message: __("Supervising RSM reassigned"), indicator: "green" });
				this.refresh();
			},
		});
		dialog.show();
	}

	open_end_dialog(record) {
		const dialog = new frappe.ui.Dialog({
			title: __("End Territory Assignment — {0}", [record.territory]),
			fields: [
				{
					fieldname: "territory",
					fieldtype: "Link",
					label: __("Sales Territory"),
					options: "Territory",
					default: record.territory,
					read_only: 1,
				},
				{
					fieldname: "asm",
					fieldtype: "Link",
					label: __("Area Sales Manager"),
					options: "User",
					default: record.asm,
					read_only: 1,
				},
				{
					fieldname: "end_date",
					fieldtype: "Date",
					label: __("End Date"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				},
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Reason for Ending Assignment"),
					reqd: 1,
				},
			],
			primary_action_label: __("End Assignment"),
			primary_action: async (values) => {
				await frappe.call({
					method: "sales_erp.supervision.end_asm_supervision",
					type: "POST",
					args: {
						name: record.name,
						end_date: values.end_date,
						reason: values.reason,
					},
					freeze: true,
					freeze_message: __("Ending territory assignment…"),
				});
				dialog.hide();
				frappe.show_alert({ message: __("Territory assignment ended"), indicator: "orange" });
				this.refresh();
			},
		});
		dialog.show();
	}

	open_view_dialog(record) {
		const status = record.status || "Active";
		const statusClass = status === "Active" ? "badge-active" : (status === "Cancelled" ? "badge-cancelled" : "badge-superseded");
		const dateInfo = record.effective_from ? (record.effective_to ? `${record.effective_from} → ${record.effective_to}` : `From ${record.effective_from}`) : "";

		const dialog = new frappe.ui.Dialog({
			title: __("Territory Assignment: {0}", [record.territory || record.name]),
			fields: [
				{
					fieldname: "details_html",
					fieldtype: "HTML",
					options: `
						<div class="assignment-details p-3">
							<div class="row mb-3">
								<div class="col-sm-4 text-muted">${__("Territory")}:</div>
								<div class="col-sm-8 font-weight-bold">${this.escape(record.territory)}</div>
							</div>
							<div class="row mb-3">
								<div class="col-sm-4 text-muted">${__("Area Sales Manager")}:</div>
								<div class="col-sm-8">${this.escape(record.asm)}</div>
							</div>
							<div class="row mb-3">
								<div class="col-sm-4 text-muted">${__("Supervising RSM")}:</div>
								<div class="col-sm-8">${this.escape(record.rsm)}</div>
							</div>
							<div class="row mb-3">
								<div class="col-sm-4 text-muted">${__("Status")}:</div>
								<div class="col-sm-8">
									<span class="status-badge ${statusClass}">${this.escape(status)}</span>
									<span class="text-muted ml-2">${this.escape(dateInfo)}</span>
								</div>
							</div>
							${record.reason ? `
							<div class="row mb-3">
								<div class="col-sm-4 text-muted">${__("Notes / Reason")}:</div>
								<div class="col-sm-8">${this.escape(record.reason)}</div>
							</div>` : ""}
							<div class="row mb-2">
								<div class="col-sm-4 text-muted">${__("Assigned By")}:</div>
								<div class="col-sm-8 text-muted">${this.escape(record.assigned_by || "")} ${record.assigned_on ? `(${record.assigned_on})` : ""}</div>
							</div>
							<div class="assignment-history-section mt-4 pt-3 border-top">
								<div class="d-flex justify-content-between align-items-center mb-2">
									<div class="font-weight-bold">${__("Assignment History")}</div>
									<a href="/desk#List/Retailer%20Assignment%20History?territory=${encodeURIComponent(record.territory)}" class="small text-muted">${__("Full History →")}</a>
								</div>
								<div class="assignment-history-content text-muted small">${__("Loading territory assignment history…")}</div>
							</div>
						</div>
					`,
				},
			],
		});

		frappe.call({
			method: "sales_erp.supervision.get_territory_assignment_history",
			args: { territory: record.territory },
			callback: (r) => {
				const history = r.message || [];
				const $hist = dialog.$wrapper.find(".assignment-history-content");
				if (!history.length) {
					$hist.text(__("No previous assignment changes recorded for this territory."));
					return;
				}
				const rows = history.map((h) => `
					<div class="history-item mb-2 pb-2 border-bottom">
						<div class="d-flex justify-content-between">
							<span class="font-weight-bold">${this.escape(h.new_asm || __("Ended"))} ${h.new_rsm ? `(${__("RSM")}: ${this.escape(h.new_rsm)})` : ""}</span>
							<span class="text-muted">${this.escape(h.changed_on ? h.changed_on.split(" ")[0] : "")}</span>
						</div>
						${h.previous_asm || h.previous_rsm ? `<div class="text-muted">${__("Replaced")}: ${this.escape(h.previous_asm || __("None"))} (${__("RSM")}: ${this.escape(h.previous_rsm || __("None"))})</div>` : ""}
						${h.reason ? `<div class="text-muted">${__("Reason")}: ${this.escape(h.reason)}</div>` : ""}
					</div>
				`).join("");
				$hist.html(rows);
			},
		});

		if (this.is_admin && status === "Active") {
			dialog.set_secondary_action(__("Reassign RSM"), () => {
				dialog.hide();
				this.open_reassign_dialog(record);
			});
			dialog.add_custom_action(__("End Assignment"), () => {
				dialog.hide();
				this.open_end_dialog(record);
			});
		}

		dialog.show();
	}
}
