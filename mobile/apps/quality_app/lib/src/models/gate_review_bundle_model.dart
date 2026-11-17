// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Immutable review bundle and security challenge for high-risk gate approvals.
///
/// Security Boundary:
/// - Administrator gate reviews on mobile require online connectivity and strong reauthentication.
/// - The bundle hash (SHA-256) locks all stage revisions immutably; any tampering or revision mismatch aborts the gate decision.
@immutable
class GateReviewBundleModel {
  final String cycleName;
  final String cycleKey;
  final String gate; // 'Production Go Ahead' | 'Final Inspection'
  final String bundleHash;
  final String supplier;
  final String itemCode;
  final String? itemName;
  final String? purchaseOrder;
  final Map<String, String> reviewedRevisions; // stage_name -> inspection_name
  final List<Map<String, dynamic>> stageSummaries;
  final bool isApproved;
  final String? gateDecision; // 'Approved' | 'Rejected' | 'Conditional'
  final String? decisionNotes;
  final DateTime generatedAt;

  const GateReviewBundleModel({
    required this.cycleName,
    required this.cycleKey,
    required this.gate,
    required this.bundleHash,
    required this.supplier,
    required this.itemCode,
    this.itemName,
    this.purchaseOrder,
    this.reviewedRevisions = const {},
    this.stageSummaries = const [],
    this.isApproved = false,
    this.gateDecision,
    this.decisionNotes,
    required this.generatedAt,
  });

  bool get isProductionGoAhead => gate == 'Production Go Ahead';
  bool get isFinalInspection => gate == 'Final Inspection';

  factory GateReviewBundleModel.fromJson(Map<String, dynamic> json) {
    final rawRevs = json['reviewed_revisions'] as Map<String, dynamic>? ?? {};
    final rawStages = json['stage_summaries'] as List<dynamic>? ?? [];

    return GateReviewBundleModel(
      cycleName: json['cycle_name'] as String? ?? json['name'] as String? ?? '',
      cycleKey: json['cycle_key'] as String? ?? '',
      gate: json['gate'] as String? ?? 'Production Go Ahead',
      bundleHash: json['bundle_hash'] as String? ?? '',
      supplier: json['supplier'] as String? ?? '',
      itemCode: json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String?,
      purchaseOrder: json['purchase_order'] as String?,
      reviewedRevisions: rawRevs.map((k, v) => MapEntry(k, v.toString())),
      stageSummaries: rawStages.whereType<Map<String, dynamic>>().toList(),
      isApproved: json['is_approved'] == true || json['is_approved'] == 1,
      gateDecision: json['gate_decision'] as String?,
      decisionNotes: json['decision_notes'] as String?,
      generatedAt: DateTime.tryParse(json['generated_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'cycle_name': cycleName,
    'cycle_key': cycleKey,
    'gate': gate,
    'bundle_hash': bundleHash,
    'supplier': supplier,
    'item_code': itemCode,
    'item_name': itemName,
    'purchase_order': purchaseOrder,
    'reviewed_revisions': reviewedRevisions,
    'stage_summaries': stageSummaries,
    'is_approved': isApproved,
    'gate_decision': gateDecision,
    'decision_notes': decisionNotes,
    'generated_at': generatedAt.toIso8601String(),
  };
}
