// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Customer return intake model isolating returned goods in quarantine.
///
/// Stock & Financial Boundary:
/// Returned garments must never enter saleable stock directly. They are routed
/// to `quarantine_warehouse` pending quality inspection and commercial authorization.
@immutable
class ReturnIntakeModel {
  final String? quarantineName; // Created Return Quarantine doc name (e.g. RQ-2026-0001)
  final String deliveryNote;
  final String itemCode;
  final String? itemName;
  final String? size;
  final int returnQuantity;
  final int deliveredQuantity;
  final int remainingReturnableQuantity;
  final String quarantineWarehouse;
  final String returnReason; // e.g. Defective Fabric | Stitching Issue | Transit Damage | Excess Stock
  final String? serialNo;
  final String? batchNo;
  final List<String> photoUrls;
  final String? notes;
  final String? financialStatus;
  final String requestId; // UUID idempotency key

  const ReturnIntakeModel({
    this.quarantineName,
    required this.deliveryNote,
    required this.itemCode,
    this.itemName,
    this.size,
    required this.returnQuantity,
    this.deliveredQuantity = 0,
    this.remainingReturnableQuantity = 0,
    required this.quarantineWarehouse,
    required this.returnReason,
    this.serialNo,
    this.batchNo,
    this.photoUrls = const [],
    this.notes,
    this.financialStatus,
    required this.requestId,
  });

  bool get isValidQuantity => returnQuantity > 0 &&
      (remainingReturnableQuantity <= 0 || returnQuantity <= remainingReturnableQuantity);

  factory ReturnIntakeModel.fromJson(Map<String, dynamic> json) {
    final rawPhotos = json['photo_evidence'] as List<dynamic>? ?? json['photos'] as List<dynamic>? ?? [];
    return ReturnIntakeModel(
      quarantineName: json['name'] as String? ?? json['quarantine_name'] as String?,
      deliveryNote: json['delivery_note'] as String? ?? '',
      itemCode: json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String?,
      size: json['size'] as String?,
      returnQuantity: (json['quantity'] as num?)?.toInt() ?? 1,
      deliveredQuantity: (json['delivered_qty'] as num?)?.toInt() ?? 0,
      remainingReturnableQuantity: (json['remaining_returnable_qty'] as num?)?.toInt() ?? 0,
      quarantineWarehouse: json['quarantine_warehouse'] as String? ?? '',
      returnReason: json['return_reason'] as String? ?? 'Defective Fabric',
      serialNo: json['serial_no'] as String?,
      batchNo: json['batch_no'] as String?,
      photoUrls: rawPhotos.map((p) => p.toString()).toList(),
      notes: json['notes'] as String?,
      financialStatus: json['financial_status'] as String?,
      requestId: json['request_id'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'name': quarantineName,
    'delivery_note': deliveryNote,
    'item_code': itemCode,
    'item_name': itemName,
    'size': size,
    'quantity': returnQuantity,
    'delivered_qty': deliveredQuantity,
    'remaining_returnable_qty': remainingReturnableQuantity,
    'quarantine_warehouse': quarantineWarehouse,
    'return_reason': returnReason,
    'serial_no': serialNo,
    'batch_no': batchNo,
    'photo_evidence': photoUrls,
    'notes': notes,
    'financial_status': financialStatus,
    'request_id': requestId,
  };
}
