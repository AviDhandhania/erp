// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';
import 'checklist_template_model.dart';
import 'inspection_reading_model.dart';
import 'inspection_defect_model.dart';
import 'inspection_evidence_photo.dart';

/// Supplier Quality Inspection stage report model.
@immutable
class StageInspectionModel {
  final String name;
  final String cycleKey;
  final int stage; // 1-7
  final String stageName;
  final int visitNumber; // 1, 2, ... for multiple Inline / Mid-line visits
  final int revision;
  final bool isLatest;
  final String? supersedes;
  final String? supersededBy;
  final String supplier;
  final String itemCode;
  final String? itemName;
  final String? purchaseOrder;
  final String? productionLot;
  final String? checklistTemplate;
  final List<InspectionChecklistItem> checklistItems;
  final List<InspectionReadingModel> readings;
  final List<InspectionDefectModel> defects;
  final AqlSamplingPlanModel samplingPlan;
  final List<InspectionEvidencePhoto> evidencePhotos;
  final String recommendation;
  final String result; // 'Passed' | 'Failed' | 'Conditionally Passed' | 'Pending Review'
  final bool correctiveActionRequired;
  final String? correctiveActionDescription;
  final String? correctiveActionOwner;
  final DateTime? correctiveActionDueDate;
  final String? correctiveActionStatus; // 'Open' | 'In Progress' | 'Resolved' | 'Overdue'
  final String? correctiveActionResolutionNotes;
  final String? inspector;
  final DateTime? inspectedAt;
  final bool isApproved;

  const StageInspectionModel({
    required this.name,
    required this.cycleKey,
    required this.stage,
    required this.stageName,
    this.visitNumber = 1,
    this.revision = 1,
    this.isLatest = true,
    this.supersedes,
    this.supersededBy,
    required this.supplier,
    required this.itemCode,
    this.itemName,
    this.purchaseOrder,
    this.productionLot,
    this.checklistTemplate,
    this.checklistItems = const [],
    this.readings = const [],
    this.defects = const [],
    this.samplingPlan = const AqlSamplingPlanModel(lotSize: 0, sampleSize: 0),
    this.evidencePhotos = const [],
    this.recommendation = 'Accept Lot',
    this.result = 'Pending Review',
    this.correctiveActionRequired = false,
    this.correctiveActionDescription,
    this.correctiveActionOwner,
    this.correctiveActionDueDate,
    this.correctiveActionStatus,
    this.correctiveActionResolutionNotes,
    this.inspector,
    this.inspectedAt,
    this.isApproved = false,
  });

  bool get isPassed => result == 'Passed';
  bool get isFailed => result == 'Failed';
  bool get isConditional => result == 'Conditionally Passed';
  bool get hasCriticalDefects => defects.any((d) => d.isCritical);
  bool get hasMajorDefects => defects.any((d) => d.isMajor);
  bool get hasChecklistFailures => checklistItems.any((c) => c.isFailed);

  factory StageInspectionModel.fromJson(Map<String, dynamic> json) {
    final rawChecklists = json['checklist_items'] as List<dynamic>? ?? [];
    final rawReadings = json['readings'] as List<dynamic>? ?? [];
    final rawDefects = json['defects'] as List<dynamic>? ?? [];
    final rawPhotos = json['evidence_photos'] as List<dynamic>? ?? [];
    final samplingJson = json['sampling_plan'] as Map<String, dynamic>? ?? {};

    return StageInspectionModel(
      name: json['name'] as String? ?? '',
      cycleKey: json['cycle_key'] as String? ?? json['production_cycle'] as String? ?? '',
      stage: (json['stage'] as num?)?.toInt() ?? 1,
      stageName: json['stage_name'] as String? ?? '',
      visitNumber: (json['visit_number'] as num?)?.toInt() ?? 1,
      revision: (json['revision'] as num?)?.toInt() ?? 1,
      isLatest: json['is_latest'] == true || json['is_latest'] == 1,
      supersedes: json['supersedes'] as String?,
      supersededBy: json['superseded_by'] as String?,
      supplier: json['supplier'] as String? ?? '',
      itemCode: json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String?,
      purchaseOrder: json['purchase_order'] as String?,
      productionLot: json['production_lot'] as String?,
      checklistTemplate: json['checklist_template'] as String?,
      checklistItems: rawChecklists
          .whereType<Map<String, dynamic>>()
          .map((c) => InspectionChecklistItem.fromJson(c))
          .toList(),
      readings: rawReadings
          .whereType<Map<String, dynamic>>()
          .map((r) => InspectionReadingModel.fromJson(r))
          .toList(),
      defects: rawDefects
          .whereType<Map<String, dynamic>>()
          .map((d) => InspectionDefectModel.fromJson(d))
          .toList(),
      samplingPlan: AqlSamplingPlanModel.fromJson(samplingJson),
      evidencePhotos: rawPhotos
          .whereType<Map<String, dynamic>>()
          .map((p) => InspectionEvidencePhoto.fromJson(p))
          .toList(),
      recommendation: json['recommendation'] as String? ?? 'Accept Lot',
      result: json['result'] as String? ?? 'Pending Review',
      correctiveActionRequired: json['corrective_action_required'] == true || json['corrective_action_required'] == 1,
      correctiveActionDescription: json['corrective_action_description'] as String?,
      correctiveActionOwner: json['corrective_action_owner'] as String?,
      correctiveActionDueDate: DateTime.tryParse(json['corrective_action_due_date'] as String? ?? ''),
      correctiveActionStatus: json['corrective_action_status'] as String?,
      correctiveActionResolutionNotes: json['corrective_action_resolution_notes'] as String?,
      inspector: json['inspector'] as String? ?? json['owner'] as String?,
      inspectedAt: DateTime.tryParse(json['inspection_datetime'] as String? ?? json['creation'] as String? ?? ''),
      isApproved: json['is_approved'] == true || json['is_approved'] == 1,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'cycle_key': cycleKey,
    'stage': stage,
    'stage_name': stageName,
    'visit_number': visitNumber,
    'revision': revision,
    'is_latest': isLatest,
    'supersedes': supersedes,
    'superseded_by': supersededBy,
    'supplier': supplier,
    'item_code': itemCode,
    'item_name': itemName,
    'purchase_order': purchaseOrder,
    'production_lot': productionLot,
    'checklist_template': checklistTemplate,
    'checklist_items': checklistItems.map((c) => c.toJson()).toList(),
    'readings': readings.map((r) => r.toJson()).toList(),
    'defects': defects.map((d) => d.toJson()).toList(),
    'sampling_plan': samplingPlan.toJson(),
    'evidence_photos': evidencePhotos.map((p) => p.toJson()).toList(),
    'recommendation': recommendation,
    'result': result,
    'corrective_action_required': correctiveActionRequired,
    'corrective_action_description': correctiveActionDescription,
    'corrective_action_owner': correctiveActionOwner,
    'corrective_action_due_date': correctiveActionDueDate?.toIso8601String().substring(0, 10),
    'corrective_action_status': correctiveActionStatus,
    'corrective_action_resolution_notes': correctiveActionResolutionNotes,
    'inspector': inspector,
    'inspection_datetime': inspectedAt?.toIso8601String(),
    'is_approved': isApproved,
  };
}
