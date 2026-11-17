// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Sequential 7-stage quality lifecycle for manufacturing cycles.
const List<String> qualityStages = [
  'First Submission — Fit Sample',
  'Second Submission — Refit Sample',
  'Size Set Submission',
  'Production Go Ahead',
  'Inline Visits',
  'Mid-line Visits',
  'Final Inspection',
];

/// Domain model for Production Quality Cycle.
@immutable
class ProductionCycleModel {
  final String name;
  final String cycleKey;
  final String supplier;
  final String itemCode;
  final String? itemName;
  final String? purchaseOrder;
  final String? productionLot;
  final String? season;
  final String company;
  final String status; // 'Active' | 'Completed' | 'Cancelled'
  final int currentStage; // 1 to 7
  final String currentStageName;
  final String? gateReviewStatus; // 'Pending' | 'Approved' | 'Rejected' | 'Conditional'
  final int completedStagesCount;
  final DateTime? createdAt;
  final DateTime? modifiedAt;

  const ProductionCycleModel({
    required this.name,
    required this.cycleKey,
    required this.supplier,
    required this.itemCode,
    this.itemName,
    this.purchaseOrder,
    this.productionLot,
    this.season,
    required this.company,
    this.status = 'Active',
    this.currentStage = 1,
    required this.currentStageName,
    this.gateReviewStatus,
    this.completedStagesCount = 0,
    this.createdAt,
    this.modifiedAt,
  });

  bool get isActive => status == 'Active';
  bool get isCompleted => status == 'Completed';
  bool get isProductionGoAheadStage => currentStage == 4;
  bool get isFinalInspectionStage => currentStage == 7;
  bool get requiresGateReview => isProductionGoAheadStage || isFinalInspectionStage;

  factory ProductionCycleModel.fromJson(Map<String, dynamic> json) {
    final stageNum = (json['current_stage'] as num?)?.toInt() ?? 1;
    final stageName = json['current_stage_name'] as String? ??
        (stageNum >= 1 && stageNum <= qualityStages.length
            ? qualityStages[stageNum - 1]
            : 'Unknown Stage');

    return ProductionCycleModel(
      name: json['name'] as String? ?? '',
      cycleKey: json['cycle_key'] as String? ?? json['name'] as String? ?? '',
      supplier: json['supplier'] as String? ?? '',
      itemCode: json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String?,
      purchaseOrder: json['purchase_order'] as String?,
      productionLot: json['production_lot'] as String?,
      season: json['season'] as String?,
      company: json['company'] as String? ?? '',
      status: json['status'] as String? ?? 'Active',
      currentStage: stageNum,
      currentStageName: stageName,
      gateReviewStatus: json['gate_review_status'] as String?,
      completedStagesCount: (json['completed_stages_count'] as num?)?.toInt() ?? 0,
      createdAt: DateTime.tryParse(json['creation'] as String? ?? ''),
      modifiedAt: DateTime.tryParse(json['modified'] as String? ?? ''),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'cycle_key': cycleKey,
    'supplier': supplier,
    'item_code': itemCode,
    'item_name': itemName,
    'purchase_order': purchaseOrder,
    'production_lot': productionLot,
    'season': season,
    'company': company,
    'status': status,
    'current_stage': currentStage,
    'current_stage_name': currentStageName,
    'gate_review_status': gateReviewStatus,
    'completed_stages_count': completedStagesCount,
    'creation': createdAt?.toIso8601String(),
    'modified': modifiedAt?.toIso8601String(),
  };
}
