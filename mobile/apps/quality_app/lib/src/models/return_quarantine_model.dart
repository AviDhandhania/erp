// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';
import 'inspection_evidence_photo.dart';

/// Supported quality failure dispositions.
const List<String> supportedDispositions = [
  'Scrap',
  'Seconds Sale',
  'Supplier Claim',
  'On Hold',
];

/// Return quarantine intake, quality inspection, and disposition decision model.
@immutable
class ReturnQuarantineModel {
  final String name;
  final String itemCode;
  final String? itemName;
  final String customer;
  final String originalDeliveryNote;
  final String quarantineWarehouse;
  final double returnQty;
  final String? returnReason;
  final String qualityDecision; // 'Pending' | 'Passed' | 'Failed'
  final String? recommendedDisposition; // 'Scrap' | 'Seconds Sale' | 'Supplier Claim' | 'On Hold'
  final String? inspectorNotes;
  final String businessApprovalStatus; // 'Pending' | 'Approved' | 'Rejected'
  final String? approvedDisposition;
  final String? approvedTargetWarehouse;
  final String? approvedBy;
  final DateTime? approvedAt;
  final String? linkedSupplierClaim;
  final String reinspectionStatus; // 'Not Required' | 'Pending Reinspection' | 'Passed' | 'Failed'
  final List<InspectionEvidencePhoto> evidencePhotos;

  const ReturnQuarantineModel({
    required this.name,
    required this.itemCode,
    this.itemName,
    required this.customer,
    required this.originalDeliveryNote,
    required this.quarantineWarehouse,
    required this.returnQty,
    this.returnReason,
    this.qualityDecision = 'Pending',
    this.recommendedDisposition,
    this.inspectorNotes,
    this.businessApprovalStatus = 'Pending',
    this.approvedDisposition,
    this.approvedTargetWarehouse,
    this.approvedBy,
    this.approvedAt,
    this.linkedSupplierClaim,
    this.reinspectionStatus = 'Not Required',
    this.evidencePhotos = const [],
  });

  bool get isAwaitingQualityDecision => qualityDecision == 'Pending';
  bool get isQualityPassed => qualityDecision == 'Passed';
  bool get isQualityFailed => qualityDecision == 'Failed';
  bool get isAwaitingBusinessApproval =>
      isQualityFailed && recommendedDisposition != null && businessApprovalStatus == 'Pending';
  bool get isBusinessApproved => businessApprovalStatus == 'Approved';

  factory ReturnQuarantineModel.fromJson(Map<String, dynamic> json) {
    final rawPhotos = json['evidence_photos'] as List<dynamic>? ?? [];

    return ReturnQuarantineModel(
      name: json['name'] as String? ?? '',
      itemCode: json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String?,
      customer: json['customer'] as String? ?? '',
      originalDeliveryNote: json['original_delivery_note'] as String? ?? json['delivery_note'] as String? ?? '',
      quarantineWarehouse: json['quarantine_warehouse'] as String? ?? '',
      returnQty: (json['return_qty'] as num?)?.toDouble() ?? (json['qty'] as num?)?.toDouble() ?? 1.0,
      returnReason: json['return_reason'] as String?,
      qualityDecision: json['quality_decision'] as String? ?? 'Pending',
      recommendedDisposition: json['recommended_disposition'] as String?,
      inspectorNotes: json['inspector_notes'] as String?,
      businessApprovalStatus: json['business_approval_status'] as String? ?? 'Pending',
      approvedDisposition: json['approved_disposition'] as String?,
      approvedTargetWarehouse: json['approved_target_warehouse'] as String?,
      approvedBy: json['approved_by'] as String?,
      approvedAt: DateTime.tryParse(json['approved_at'] as String? ?? ''),
      linkedSupplierClaim: json['linked_supplier_claim'] as String?,
      reinspectionStatus: json['reinspection_status'] as String? ?? 'Not Required',
      evidencePhotos: rawPhotos
          .whereType<Map<String, dynamic>>()
          .map((p) => InspectionEvidencePhoto.fromJson(p))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'item_code': itemCode,
    'item_name': itemName,
    'customer': customer,
    'original_delivery_note': originalDeliveryNote,
    'quarantine_warehouse': quarantineWarehouse,
    'return_qty': returnQty,
    'return_reason': returnReason,
    'quality_decision': qualityDecision,
    'recommended_disposition': recommendedDisposition,
    'inspector_notes': inspectorNotes,
    'business_approval_status': businessApprovalStatus,
    'approved_disposition': approvedDisposition,
    'approved_target_warehouse': approvedTargetWarehouse,
    'approved_by': approvedBy,
    'approved_at': approvedAt?.toIso8601String(),
    'linked_supplier_claim': linkedSupplierClaim,
    'reinspection_status': reinspectionStatus,
    'evidence_photos': evidencePhotos.map((p) => p.toJson()).toList(),
  };
}
