// Copyright (c) 2026, Clothing ERP Contributors
// For license information, please see license.txt

frappe.ui.form.on('Production Quality Cycle', {
	refresh: function(frm) {
		if (frm.is_new()) return;

		const user_roles = new Set(frappe.user_roles || []);
		const is_admin = ['Clothing Business Administrator', 'System Manager', 'Administrator'].some(r => user_roles.has(r));

		// 1. Status Headlines
		if (frm.doc.go_ahead_status === 'Approved' && frm.doc.final_inspection_status === 'Approved') {
			frm.dashboard.set_headline_alert(
				__('<b>All Quality Gates Approved:</b> Production authorized and cleared for Purchase Receipt.'),
				'green'
			);
		} else if (frm.doc.go_ahead_status === 'Approved') {
			frm.dashboard.set_headline_alert(
				__('<b>Gate 4 (Production Go Ahead) Approved:</b> Bulk cutting authorized. Production in progress.'),
				'blue'
			);
		} else if (frm.doc.status === 'On Hold') {
			frm.dashboard.set_headline_alert(
				__('<b>Quality Cycle On Hold:</b> Gate decision rejected or outstanding critical defects.'),
				'red'
			);
		}

		// 2. Custom Buttons
		frm.add_custom_button(__('Gate Review Desk'), () => {
			frappe.set_route('quality-gate-review');
		}, __('Quality Gates'));

		frm.add_custom_button(__('Export Report Bundle'), async () => {
			frappe.show_alert({ message: __('Generating controlled PDF report bundle...'), indicator: 'blue' });
			const exp = await frappe.call({
				method: 'quality_erp.quality.export_quality_report_bundle',
				args: { cycle_name: frm.doc.name, as_pdf: true }
			});
			if (exp.message && exp.message.file_bytes_base64) {
				const blob = b64_to_blob(exp.message.file_bytes_base64, exp.message.content_type || 'application/pdf');
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = exp.message.filename;
				a.click();
				frappe.show_alert({ message: __('Report bundle downloaded.'), indicator: 'green' });
			}
		}, __('Quality Gates'));

		if (is_admin && frm.doc.go_ahead_status === 'Pending') {
			frm.add_custom_button(__('Decide Production Go Ahead'), async () => {
				const bundle = await frappe.call({
					method: 'quality_erp.quality.get_production_go_ahead_review_bundle',
					args: { cycle_name: frm.doc.name }
				});
				const pga = bundle.message || {};
				prompt_gate_dialog({
					title: __('Decide Gate 4: Production Go Ahead'),
					ready: pga.ready_for_decision,
					blocking: pga.blocking_reasons,
					on_decision: async (decision, conditions, notes) => {
						await frappe.call({
							method: 'quality_erp.quality.decide_production_go_ahead',
							args: {
								cycle_name: frm.doc.name,
								decision: decision,
								reviewed_revisions: pga.reviewed_revisions,
								conditions: conditions,
								notes: notes,
								bundle_hash: pga.bundle_hash
							},
							freeze: true
						});
						frm.reload_doc();
					}
				});
			}, __('Quality Gates')).addClass('btn-primary');
		}

		if (is_admin && frm.doc.final_inspection_status === 'Pending') {
			frm.add_custom_button(__('Decide Final Inspection'), async () => {
				const bundle = await frappe.call({
					method: 'quality_erp.quality.get_final_inspection_review_bundle',
					args: { cycle_name: frm.doc.name }
				});
				const fin = bundle.message || {};
				prompt_gate_dialog({
					title: __('Decide Gate 7: Final Inspection'),
					ready: fin.ready_for_decision,
					blocking: fin.blocking_reasons,
					on_decision: async (decision, conditions, notes) => {
						await frappe.call({
							method: 'quality_erp.quality.decide_final_inspection',
							args: {
								cycle_name: frm.doc.name,
								decision: decision,
								reviewed_revisions: fin.reviewed_revisions,
								conditions: conditions,
								notes: notes,
								bundle_hash: fin.bundle_hash
							},
							freeze: true
						});
						frm.reload_doc();
					}
				});
			}, __('Quality Gates')).addClass('btn-primary');
		}
	}
});

function prompt_gate_dialog({ title, ready, blocking, on_decision }) {
	const d = new frappe.ui.Dialog({
		title: title,
		fields: [
			{
				fieldname: 'readiness_html',
				fieldtype: 'HTML',
				options: ready
					? `<div class="alert alert-success">${__('All prerequisite stages are approved and ready for gate decision.')}</div>`
					: `<div class="alert alert-warning"><strong>${__('Prerequisites Incomplete:')}</strong><ul>${(blocking || []).map(b => `<li>${b}</li>`).join('')}</ul></div>`
			},
			{
				fieldname: 'decision',
				fieldtype: 'Select',
				label: __('Decision'),
				options: 'Approved\nConditionally Approved\nRejected',
				default: ready ? 'Approved' : 'Conditionally Approved',
				reqd: 1
			},
			{
				fieldname: 'conditions',
				fieldtype: 'Small Text',
				label: __('Conditions (Mandatory for Conditional Approval)'),
				depends_on: 'eval:doc.decision=="Conditionally Approved"'
			},
			{
				fieldname: 'notes',
				fieldtype: 'Small Text',
				label: __('Decision Notes / Rejection Reason')
			}
		],
		primary_action_label: __('Submit Decision'),
		primary_action: async ({ decision, conditions, notes }) => {
			if (decision === 'Conditionally Approved' && !conditions) {
				frappe.msgprint(__('Conditions are required for Conditional Approval.'));
				return;
			}
			if (decision === 'Rejected' && !notes) {
				frappe.msgprint(__('A rejection reason is required in Decision Notes.'));
				return;
			}
			d.hide();
			await on_decision(decision, conditions, notes);
		}
	});
	d.show();
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
