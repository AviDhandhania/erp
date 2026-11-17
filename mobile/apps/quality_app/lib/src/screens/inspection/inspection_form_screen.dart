// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/inspection_controller.dart';

/// Screen for performing a stage quality inspection with checklists, measurements, defects, and photo evidence.
class InspectionFormScreen {
  final InspectionController controller;

  const InspectionFormScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final active = controller.activeInspection;

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'inspection_name': active?.name,
      'cycle_key': active?.cycleKey,
      'stage': active?.stage,
      'stage_name': active?.stageName,
      'visit_number': active?.visitNumber,
      'supplier': active?.supplier,
      'item_code': active?.itemCode,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'checklist_section': {
        'total_checkpoints': controller.checklistItems.length,
        'passed_count': controller.checklistItems.where((c) => c.isPassed).length,
        'failed_count': controller.checklistItems.where((c) => c.isFailed).length,
        'na_count': controller.checklistItems.where((c) => c.isNA).length,
        'items': controller.checklistItems.map((c) => {
          'checkpoint': c.checkpoint,
          'category': c.category,
          'status': c.status,
          'notes': c.notes,
          'is_mandatory': c.isMandatory,
        }).toList(),
      },
      'measurements_section': {
        'total_readings': controller.readings.length,
        'in_spec_count': controller.readings.where((r) => r.isInSpec).length,
        'out_of_spec_count': controller.readings.where((r) => !r.isInSpec).length,
        'readings': controller.readings.map((r) => {
          'parameter': r.parameter,
          'size': r.size,
          'spec_target': r.specTarget,
          'tolerance_plus': r.tolerancePlus,
          'tolerance_minus': r.toleranceMinus,
          'actual_reading': r.actualReading,
          'variance': r.variance,
          'is_in_spec': r.isInSpec,
          'status': r.status,
        }).toList(),
      },
      'defects_section': {
        'total_defects': controller.defects.length,
        'critical_count': controller.defects.where((d) => d.isCritical).length,
        'major_count': controller.defects.where((d) => d.isMajor).length,
        'minor_count': controller.defects.where((d) => d.isMinor).length,
        'defects': controller.defects.map((d) => {
          'code': d.defectCode,
          'description': d.description,
          'count': d.count,
          'severity': d.severity,
        }).toList(),
      },
      'evidence_photos_section': {
        'total_photos': controller.evidencePhotos.length,
        'photos': controller.evidencePhotos.map((p) => {
          'photo_id': p.photoId,
          'caption': p.caption,
          'evidence_type': p.evidenceType,
          'sha256': p.sha256Checksum,
          'display_order': p.displayOrder,
        }).toList(),
      },
      'decision_section': {
        'recommendation': controller.recommendation,
        'result': controller.result,
        'corrective_action_required': controller.correctiveActionRequired,
        'corrective_action_description': controller.correctiveActionDescription,
        'corrective_action_owner': controller.correctiveActionOwner,
        'corrective_action_due_date': controller.correctiveActionDueDate?.toIso8601String().substring(0, 10),
      },
      'actions': [
        'update_checklist_item',
        'add_measurement_reading',
        'add_defect_observation',
        'capture_safe_photo',
        'save_draft',
        'submit_inspection',
      ],
    };
  }
}
