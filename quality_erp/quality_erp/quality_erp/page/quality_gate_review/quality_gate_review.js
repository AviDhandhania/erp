// Quality Gate Review Desk - Frappe Page Controller

frappe.pages['quality-gate-review'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Quality Gate Review Desk'),
		single_column: true,
	});

	page.main.html(`
		<div class="quality-review-desk">
			<div class="quality-review-header">
				<h2>${__('Production Quality Gate Review & Decision Desk')}</h2>
				<p class="text-muted">
					${__('Authorized review bundles for Gate 4 (Production Go Ahead) and Gate 7 (Final Inspection). Enforces exact reviewed-revision locking and cryptographic bundle integrity.')}
				</p>
				<div class="row" style="margin-top: 15px;">
					<div class="col-md-5" id="cycle-selector-container"></div>
					<div class="col-md-7" id="cycle-actions-container" style="display: flex; gap: 8px; align-items: flex-end;"></div>
				</div>
			</div>
			<div id="quality-review-content">
				<div class="text-center text-muted p-5">
					<i class="fa fa-spinner fa-spin fa-2x"></i><br><br>
					${__('Select a Production Quality Cycle above to review gate bundles.')}
				</div>
			</div>
		</div>
	`);

	const cycle_field = frappe.ui.form.make_control({
		df: {
			fieldtype: 'Link',
			options: 'Production Quality Cycle',
			fieldname: 'selected_cycle',
			label: __('Production Quality Cycle'),
			placeholder: __('Select Cycle (PQC-...)'),
			onchange: () => {
				const cycle_name = cycle_field.get_value();
				if (cycle_name) {
					load_cycle_review(cycle_name);
				}
			}
		},
		parent: page.main.find('#cycle-selector-container'),
		render_input: true
	});

	async function load_cycle_review(cycle_name) {
		const content = page.main.find('#quality-review-content');
		content.html(`<div class="text-center text-muted p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><br><br>${__('Loading Gate Review Bundles...')}</div>`);

		try {
			const [pga_res, final_res, hist_res] = await Promise.all([
				frappe.call({
					method: 'quality_erp.quality.get_production_go_ahead_review_bundle',
					args: { cycle_name: cycle_name }
				}),
				frappe.call({
					method: 'quality_erp.quality.get_final_inspection_review_bundle',
					args: { cycle_name: cycle_name }
				}),
				frappe.call({
					method: 'quality_erp.quality.get_complete_stage_history',
					args: { cycle_name: cycle_name }
				})
			]);

			const pga = pga_res.message || {};
			const final_bundle = final_res.message || {};
			const hist = hist_res.message || {};

			const user_roles = new Set(frappe.user_roles || []);
			const is_admin = ['Clothing Business Administrator', 'System Manager', 'Administrator'].some(r => user_roles.has(r));

			render_review_desk({ pga, final_bundle, hist, is_admin, cycle_name });
		} catch (err) {
			content.html(`<div class="alert alert-danger">${__('Error loading review bundle:')} ${err.message || err}</div>`);
		}
	}

	function render_review_desk({ pga, final_bundle, hist, is_admin, cycle_name }) {
		const content = page.main.find('#quality-review-content');
		const actions = page.main.find('#cycle-actions-container');

		actions.html(`
			<button class="btn btn-default btn-sm" id="btn-export-pdf">
				<i class="fa fa-file-pdf-o"></i> ${__('Export Controlled PDF Bundle')}
			</button>
			<button class="btn btn-default btn-sm" id="btn-open-cycle">
				<i class="fa fa-external-link"></i> ${__('Open Cycle Form')}
			</button>
		`);

		actions.find('#btn-export-pdf').on('click', async () => {
			frappe.show_alert({ message: __('Generating watermarked report bundle...'), indicator: 'blue' });
			const exp = await frappe.call({
				method: 'quality_erp.quality.export_quality_report_bundle',
				args: { cycle_name: cycle_name, as_pdf: true }
			});
			if (exp.message && exp.message.file_bytes_base64) {
				const blob = b64_to_blob(exp.message.file_bytes_base64, exp.message.content_type || 'application/pdf');
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = exp.message.filename;
				a.click();
				frappe.show_alert({ message: __('Bundle downloaded successfully.'), indicator: 'green' });
			}
		});

		actions.find('#btn-open-cycle').on('click', () => {
			frappe.set_route('Form', 'Production Quality Cycle', cycle_name);
		});

		content.html(`
			<div class="row">
				<!-- Gate 4 Card -->
				<div class="col-md-6">
					<div class="quality-bundle-card">
						<div style="display: flex; justify-content: space-between; align-items: center;">
							<h3 style="margin: 0;">${__('Gate 4: Production Go Ahead')}</h3>
							<span class="quality-badge ${get_badge_class(pga.go_ahead_status)}">${pga.go_ahead_status}</span>
						</div>
						<div class="bundle-hash-indicator">
							<strong>${__('Revision Hash:')}</strong> ${pga.bundle_hash ? pga.bundle_hash.substring(0, 32) + '...' : 'N/A'}
						</div>
						<p style="margin: 5px 0;"><strong>${__('Decided By:')}</strong> ${pga.go_ahead_approved_by || __('Pending')} (${pga.go_ahead_date || 'N/A'})</p>
						<p style="margin: 5px 0;"><strong>${__('Conditions / Notes:')}</strong> ${pga.go_ahead_conditions || __('None')}</p>
						
						<div style="margin-top: 12px;">
							<strong>${__('Prerequisites (Stages 1-3):')}</strong>
							${pga.ready_for_decision ? '<span class="text-success"><i class="fa fa-check"></i> All prerequisites satisfied</span>' : '<span class="text-danger"><i class="fa fa-warning"></i> Prerequisites incomplete</span>'}
							${pga.blocking_reasons && pga.blocking_reasons.length ? `<ul style="color: #dc2626; margin-top: 5px; padding-left: 20px;">${pga.blocking_reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
						</div>

						<div style="margin-top: 15px; display: flex; gap: 8px;">
							${is_admin && pga.go_ahead_status === 'Pending' ? `
								<button class="btn btn-primary btn-sm btn-pga-action" data-decision="Approved">${__('Approve Production Go Ahead')}</button>
								<button class="btn btn-warning btn-sm btn-pga-action" data-decision="Conditionally Approved">${__('Conditionally Approve')}</button>
								<button class="btn btn-danger btn-sm btn-pga-action" data-decision="Rejected">${__('Reject Gate')}</button>
							` : (is_admin ? `<span class="text-muted"><i class="fa fa-lock"></i> Gate decision immutable</span>` : `<span class="text-muted"><i class="fa fa-shield"></i> Administrator approval required</span>`)}
						</div>
					</div>
				</div>

				<!-- Gate 7 Card -->
				<div class="col-md-6">
					<div class="quality-bundle-card">
						<div style="display: flex; justify-content: space-between; align-items: center;">
							<h3 style="margin: 0;">${__('Gate 7: Final Inspection')}</h3>
							<span class="quality-badge ${get_badge_class(final_bundle.final_inspection_status)}">${final_bundle.final_inspection_status}</span>
						</div>
						<div class="bundle-hash-indicator">
							<strong>${__('Revision Hash:')}</strong> ${final_bundle.bundle_hash ? final_bundle.bundle_hash.substring(0, 32) + '...' : 'N/A'}
						</div>
						<p style="margin: 5px 0;"><strong>${__('Decided By:')}</strong> ${final_bundle.final_inspection_approved_by || __('Pending')} (${final_bundle.final_inspection_date || 'N/A'})</p>
						<p style="margin: 5px 0;"><strong>${__('Clearance Status:')}</strong> ${final_bundle.clearance_status || 'Pending'}</p>
						
						<div style="margin-top: 12px;">
							<strong>${__('Pre-clearance Check (Stages 1-6 & Gate 4):')}</strong>
							${final_bundle.ready_for_decision ? '<span class="text-success"><i class="fa fa-check"></i> Ready for clearance</span>' : '<span class="text-danger"><i class="fa fa-warning"></i> Clearance prerequisites incomplete</span>'}
							${final_bundle.blocking_reasons && final_bundle.blocking_reasons.length ? `<ul style="color: #dc2626; margin-top: 5px; padding-left: 20px;">${final_bundle.blocking_reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
						</div>

						<div style="margin-top: 15px; display: flex; gap: 8px;">
							${is_admin && final_bundle.final_inspection_status === 'Pending' ? `
								<button class="btn btn-primary btn-sm btn-final-action" data-decision="Approved">${__('Clear Final Inspection')}</button>
								<button class="btn btn-warning btn-sm btn-final-action" data-decision="Conditionally Approved">${__('Conditional Clearance')}</button>
								<button class="btn btn-danger btn-sm btn-final-action" data-decision="Rejected">${__('Reject Final Gate')}</button>
							` : (is_admin ? `<span class="text-muted"><i class="fa fa-lock"></i> Final decision immutable</span>` : `<span class="text-muted"><i class="fa fa-shield"></i> Administrator approval required</span>`)}
						</div>
					</div>
				</div>
			</div>

			<!-- Seven Stage Complete Timeline Table -->
			<div class="quality-bundle-card" style="margin-top: 15px;">
				<h3 style="margin-top: 0;">${__('Seven-Stage Quality History & Visit Records')}</h3>
				<table class="stage-timeline-table">
					<thead>
						<tr>
							<th>${__('Stage')}</th>
							<th>${__('Visit')}</th>
							<th>${__('Revision')}</th>
							<th>${__('Date')}</th>
							<th>${__('Inspector')}</th>
							<th>${__('Status / Result')}</th>
							<th>${__('Defects (Crit/Maj/Min)')}</th>
							<th>${__('Locked')}</th>
							<th>${__('Actions')}</th>
						</tr>
					</thead>
					<tbody>
						${render_stage_rows(hist)}
					</tbody>
				</table>
			</div>
		`);

		// Event handlers for Gate 4 decision
		content.find('.btn-pga-action').on('click', function() {
			const dec = $(this).data('decision');
			prompt_decision_dialog({
				title: __('Decide Gate 4: Production Go Ahead ({0})', [dec]),
				decision: dec,
				requires_conditions: dec === 'Conditionally Approved',
				requires_reason: dec === 'Rejected',
				on_submit: async ({ conditions, notes }) => {
					await frappe.call({
						method: 'quality_erp.quality.decide_production_go_ahead',
						args: {
							cycle_name: cycle_name,
							decision: dec,
							reviewed_revisions: pga.reviewed_revisions,
							conditions: conditions,
							notes: notes,
							bundle_hash: pga.bundle_hash
						},
						freeze: true
					});
					frappe.show_alert({ message: __('Production Go Ahead decided: {0}', [dec]), indicator: 'green' });
					load_cycle_review(cycle_name);
				}
			});
		});

		// Event handlers for Gate 7 decision
		content.find('.btn-final-action').on('click', function() {
			const dec = $(this).data('decision');
			prompt_decision_dialog({
				title: __('Decide Gate 7: Final Inspection ({0})', [dec]),
				decision: dec,
				requires_conditions: dec === 'Conditionally Approved',
				requires_reason: dec === 'Rejected',
				on_submit: async ({ conditions, notes }) => {
					await frappe.call({
						method: 'quality_erp.quality.decide_final_inspection',
						args: {
							cycle_name: cycle_name,
							decision: dec,
							reviewed_revisions: final_bundle.reviewed_revisions,
							conditions: conditions,
							notes: notes,
							bundle_hash: final_bundle.bundle_hash
						},
						freeze: true
					});
					frappe.show_alert({ message: __('Final Inspection decided: {0}', [dec]), indicator: 'green' });
					load_cycle_review(cycle_name);
				}
			});
		});
	}

	function render_stage_rows(hist) {
		const stages = [
			'1. First Submission', '2. Second Submission', '3. Size Set Submission',
			'4. Production Go Ahead', '5. Inline Visit', '6. Mid-line Visit', '7. Final Inspection'
		];
		let rows = '';

		stages.forEach(stg => {
			const reports = (hist.stage_groups && hist.stage_groups[stg]) || [];
			if (!reports.length) {
				rows += `
					<tr>
						<td><strong>${stg}</strong></td>
						<td colspan="8" class="text-muted" style="font-style: italic;">${__('No reports submitted yet')}</td>
					</tr>
				`;
			} else {
				reports.forEach(r => {
					rows += `
						<tr>
							<td><strong>${stg}</strong> ${r.is_latest ? '<span class="badge badge-info">Latest</span>' : '<span class="badge badge-secondary">Rev</span>'}</td>
							<td>${r.visit_number} (${r.visit_type || 'Standard'})</td>
							<td>r${r.revision}</td>
							<td>${r.inspection_date || 'N/A'}</td>
							<td>${r.inspector}</td>
							<td><span class="quality-badge ${get_badge_class(r.status)}">${r.status}</span> / ${r.result}</td>
							<td>${r.critical_defects_count || 0} / ${r.major_defects_count || 0} / ${r.minor_defects_count || 0}</td>
							<td>${r.gate_locked ? '<i class="fa fa-lock text-success" title="' + (r.locked_gate_decision || '') + '"></i>' : '<i class="fa fa-unlock-alt text-muted"></i>'}</td>
							<td>
								<a href="/desk#Form/Supplier%20Quality%20Inspection/${r.name}" target="_blank" class="btn btn-xs btn-default">
									${__('View')}
								</a>
							</td>
						</tr>
					`;
				});
			}
		});

		return rows;
	}

	function get_badge_class(status) {
		if (status === 'Approved' || status === 'Final Inspection Approved' || status === 'Production Go Ahead Approved') return 'quality-badge-approved';
		if (status === 'Conditionally Approved') return 'quality-badge-cond';
		if (status === 'Rejected' || status === 'On Hold') return 'quality-badge-rejected';
		return 'quality-badge-pending';
	}

	function prompt_decision_dialog({ title, decision, requires_conditions, requires_reason, on_submit }) {
		const fields = [];
		if (requires_conditions) {
			fields.push({
				fieldname: 'conditions',
				fieldtype: 'Small Text',
				label: __('Conditions & Remediation Terms'),
				reqd: 1
			});
		}
		fields.push({
			fieldname: 'notes',
			fieldtype: 'Small Text',
			label: __('Decision Notes / Rationale'),
			reqd: requires_reason ? 1 : 0
		});

		frappe.prompt(fields, on_submit, title, __('Submit Decision'));
	}

	function b64_to_blob(b64Data, contentType) {
		contentType = contentType || '';
		const sliceSize = 512;
		const byteCharacters = atob(b64Data);
		const byteArrays = [];
		for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
			const slice = byteCharacters.slice(offset, offset + sliceSize);
			const byteNumbers = new Array(slice.length);
			for (let i = 0; i < slice.length; i++) {
				byteNumbers[i] = slice.charCodeAt(i);
			}
			byteArrays.push(new Uint8Array(byteNumbers));
		}
		return new Blob(byteArrays, { type: contentType });
	}
};
