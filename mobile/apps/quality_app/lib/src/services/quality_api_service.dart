// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/quality_boot_model.dart';
import '../models/production_cycle_model.dart';
import '../models/stage_inspection_model.dart';
import '../models/checklist_template_model.dart';
import '../models/revision_comparison_model.dart';
import '../models/return_quarantine_model.dart';
import '../models/gate_review_bundle_model.dart';
import '../models/controlled_report_model.dart';

/// High-level typed API client communicating with Quality ERP endpoints.
///
/// Invariants:
/// - Strictly POST for all mutating endpoints.
/// - Supplies client UUID idempotency keys.
/// - Catches and maps business conflict responses.
class QualityApiService {
  final ClothingApiClient apiClient;

  QualityApiService({required this.apiClient});

  /// Bootstraps quality session with user roles, assigned suppliers, and queue summaries.
  Future<QualityBootModel> getBoot() async {
    final res = await apiClient.get('/api/method/quality_erp.quality.get_quality_dashboard_summary');
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return QualityBootModel.fromJson(data);
  }

  /// Fetches production quality cycles with optional supplier and status filter.
  Future<List<ProductionCycleModel>> getProductionCycles({
    String? supplier,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = {
      if (supplier != null) 'supplier': supplier,
      if (status != null) 'status': status,
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };

    final res = await apiClient.get(
      '/api/method/quality_erp.quality.get_quality_dashboard_summary',
      queryParameters: queryParams,
    );

    final data = res['message'] as Map<String, dynamic>? ?? res;
    final rawCycles = data['cycles'] as List<dynamic>? ?? [];
    return rawCycles
        .whereType<Map<String, dynamic>>()
        .map((c) => ProductionCycleModel.fromJson(c))
        .toList();
  }

  /// Fetches checklist template for a garment item group.
  Future<ChecklistTemplateModel> getChecklistTemplate({
    required String itemGroup,
    int? version,
  }) async {
    final res = await apiClient.get(
      '/api/method/quality_erp.quality.get_checklist_template',
      queryParameters: {
        'item_group': itemGroup,
        if (version != null) 'version': version.toString(),
      },
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return ChecklistTemplateModel.fromJson(data);
  }

  /// Submits a new stage quality inspection report.
  Future<Map<String, dynamic>> submitQualityInspection(
    StageInspectionModel inspection, {
    required String requestId,
  }) async {
    final payload = {
      'production_cycle': inspection.cycleKey,
      'stage': inspection.stage,
      'stage_name': inspection.stageName,
      'visit_number': inspection.visitNumber,
      'supplier': inspection.supplier,
      'item_code': inspection.itemCode,
      if (inspection.purchaseOrder != null) 'purchase_order': inspection.purchaseOrder,
      if (inspection.productionLot != null) 'production_lot': inspection.productionLot,
      if (inspection.checklistTemplate != null) 'checklist_template': inspection.checklistTemplate,
      'checklist_items': inspection.checklistItems.map((c) => c.toJson()).toList(),
      'measurements': inspection.readings.map((r) => r.toJson()).toList(),
      'defects': inspection.defects.map((d) => d.toJson()).toList(),
      'sampling_plan': inspection.samplingPlan.toJson(),
      'evidence_photos': inspection.evidencePhotos.map((p) => p.toJson()).toList(),
      'recommendation': inspection.recommendation,
      'result': inspection.result,
      'corrective_action_required': inspection.correctiveActionRequired,
      if (inspection.correctiveActionDescription != null)
        'corrective_action_description': inspection.correctiveActionDescription,
      if (inspection.correctiveActionOwner != null)
        'corrective_action_owner': inspection.correctiveActionOwner,
      if (inspection.correctiveActionDueDate != null)
        'corrective_action_due_date': inspection.correctiveActionDueDate!.toIso8601String().substring(0, 10),
      'request_id': requestId,
    };

    return apiClient.post(
      '/api/method/quality_erp.quality.create_quality_inspection',
      body: payload,
    );
  }

  /// Revises an existing unapproved stage inspection.
  Future<Map<String, dynamic>> reviseQualityInspection({
    required String originalInspection,
    required List<Map<String, dynamic>> checklistItems,
    required List<Map<String, dynamic>> readings,
    required List<Map<String, dynamic>> defects,
    required List<Map<String, dynamic>> evidencePhotos,
    required String recommendation,
    required String result,
    String? revisionNotes,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.revise_quality_inspection',
      body: {
        'inspection_name': originalInspection,
        'checklist_items': checklistItems,
        'measurements': readings,
        'defects': defects,
        'evidence_photos': evidencePhotos,
        'recommendation': recommendation,
        'result': result,
        if (revisionNotes != null) 'revision_notes': revisionNotes,
        'request_id': requestId,
      },
    );
  }

  /// Fetches side-by-side comparison between original and revised inspection.
  Future<RevisionComparisonModel> compareRevisions({
    required String originalName,
    required String revisionName,
  }) async {
    final res = await apiClient.get(
      '/api/method/quality_erp.quality.compare_inspection_revisions',
      queryParameters: {
        'original_name': originalName,
        'revision_name': revisionName,
      },
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return RevisionComparisonModel.fromJson(data);
  }

  /// Requests corrections on an inspection report.
  Future<Map<String, dynamic>> requestInspectionCorrection({
    required String inspectionName,
    required String requestedCorrections,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.request_inspection_correction',
      body: {
        'inspection_name': inspectionName,
        'requested_corrections': requestedCorrections,
        'request_id': requestId,
      },
    );
  }

  /// Resubmits corrected inspection report.
  Future<Map<String, dynamic>> resubmitCorrection({
    required String inspectionName,
    required String correctionNotes,
    List<Map<String, dynamic>>? updatedChecklist,
    List<Map<String, dynamic>>? updatedReadings,
    List<Map<String, dynamic>>? updatedDefects,
    List<Map<String, dynamic>>? newEvidencePhotos,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.resubmit_inspection_correction',
      body: {
        'inspection_name': inspectionName,
        'correction_notes': correctionNotes,
        if (updatedChecklist != null) 'checklist_items': updatedChecklist,
        if (updatedReadings != null) 'measurements': updatedReadings,
        if (updatedDefects != null) 'defects': updatedDefects,
        if (newEvidencePhotos != null) 'evidence_photos': newEvidencePhotos,
        'request_id': requestId,
      },
    );
  }

  /// Fetches return quarantine queue awaiting quality decision.
  Future<List<ReturnQuarantineModel>> getReturnQuarantineQueue({
    String? status,
  }) async {
    final res = await apiClient.get(
      '/api/method/quality_erp.quality.get_quality_dashboard_summary',
      queryParameters: {
        if (status != null) 'quarantine_status': status,
      },
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    final rawReturns = data['quarantine_queue'] as List<dynamic>? ?? [];
    return rawReturns
        .whereType<Map<String, dynamic>>()
        .map((q) => ReturnQuarantineModel.fromJson(q))
        .toList();
  }

  /// Quality Inspector recommends disposition for defective return garment.
  Future<Map<String, dynamic>> recommendReturnDisposition({
    required String quarantineName,
    required String disposition, // 'Scrap' | 'Seconds Sale' | 'Supplier Claim' | 'On Hold'
    String? notes,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.recommend_return_disposition',
      body: {
        'quarantine_name': quarantineName,
        'disposition': disposition,
        if (notes != null) 'notes': notes,
        'request_id': requestId,
      },
    );
  }

  /// Business Administrator approves or rejects recommended return disposition.
  Future<Map<String, dynamic>> approveReturnDisposition({
    required String quarantineName,
    required String decision, // 'Approved' | 'Rejected'
    String? targetWarehouse,
    String? notes,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.approve_return_disposition',
      body: {
        'quarantine_name': quarantineName,
        'decision': decision,
        if (targetWarehouse != null) 'target_warehouse': targetWarehouse,
        if (notes != null) 'notes': notes,
        'request_id': requestId,
      },
    );
  }

  /// Fetches immutable Production Go Ahead review bundle with bundle hash.
  Future<GateReviewBundleModel> getProductionGoAheadBundle({
    required String cycleName,
  }) async {
    final res = await apiClient.get(
      '/api/method/quality_erp.quality.get_production_go_ahead_review_bundle',
      queryParameters: {'cycle_name': cycleName},
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return GateReviewBundleModel.fromJson(data);
  }

  /// Submits Administrator decision for Production Go Ahead gate.
  Future<Map<String, dynamic>> decideProductionGoAhead({
    required String cycleName,
    required String decision, // 'Approved' | 'Rejected' | 'Conditional'
    required String bundleHash,
    String? notes,
    required String reauthPassword,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.decide_production_go_ahead',
      body: {
        'cycle_name': cycleName,
        'decision': decision,
        'bundle_hash': bundleHash,
        if (notes != null) 'notes': notes,
        'reauth_token': reauthPassword,
        'request_id': requestId,
      },
    );
  }

  /// Fetches immutable Final Inspection review bundle.
  Future<GateReviewBundleModel> getFinalInspectionBundle({
    required String cycleName,
  }) async {
    final res = await apiClient.get(
      '/api/method/quality_erp.quality.get_final_inspection_review_bundle',
      queryParameters: {'cycle_name': cycleName},
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return GateReviewBundleModel.fromJson(data);
  }

  /// Submits Administrator decision for Final Inspection gate.
  Future<Map<String, dynamic>> decideFinalInspection({
    required String cycleName,
    required String decision,
    required String bundleHash,
    String? notes,
    required String reauthPassword,
    required String requestId,
  }) async {
    return apiClient.post(
      '/api/method/quality_erp.quality.decide_final_inspection',
      body: {
        'cycle_name': cycleName,
        'decision': decision,
        'bundle_hash': bundleHash,
        if (notes != null) 'notes': notes,
        'reauth_token': reauthPassword,
        'request_id': requestId,
      },
    );
  }

  /// Fetches ephemeral controlled PDF report bundle with watermark and token.
  Future<ControlledReportModel> exportQualityReportBundle({
    required String cycleName,
    String? stageReport,
  }) async {
    final res = await apiClient.post(
      '/api/method/quality_erp.quality.export_quality_report_bundle',
      body: {
        'cycle_name': cycleName,
        if (stageReport != null) 'stage_report': stageReport,
      },
    );
    final data = res['message'] as Map<String, dynamic>? ?? res;
    return ControlledReportModel.fromJson(data);
  }
}
