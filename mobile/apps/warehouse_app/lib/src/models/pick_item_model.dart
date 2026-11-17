// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Single row item in a Pick List representing a garment SKU to be picked.
@immutable
class PickItemModel {
  final String locationId; // Pick List Item row name
  final String itemCode; // Garment SKU
  final String itemName;
  final String? size;
  final String warehouse;
  final int requiredQty;
  final int pickedQty;
  final String? barcode;
  final String? batchNo;
  final String? serialNo;
  final String? serialAndBatchBundle;
  final bool hasBatch;
  final bool hasSerial;

  const PickItemModel({
    required this.locationId,
    required this.itemCode,
    required this.itemName,
    this.size,
    required this.warehouse,
    required this.requiredQty,
    this.pickedQty = 0,
    this.barcode,
    this.batchNo,
    this.serialNo,
    this.serialAndBatchBundle,
    this.hasBatch = false,
    this.hasSerial = false,
  });

  int get remainingQty => (requiredQty - pickedQty).clamp(0, requiredQty);
  bool get isFullyPicked => pickedQty >= requiredQty;
  bool get isPartiallyPicked => pickedQty > 0 && pickedQty < requiredQty;
  bool get isUnpicked => pickedQty == 0;

  PickItemModel copyWith({
    int? pickedQty,
    String? batchNo,
    String? serialNo,
    String? serialAndBatchBundle,
  }) {
    return PickItemModel(
      locationId: locationId,
      itemCode: itemCode,
      itemName: itemName,
      size: size,
      warehouse: warehouse,
      requiredQty: requiredQty,
      pickedQty: pickedQty ?? this.pickedQty,
      barcode: barcode,
      batchNo: batchNo ?? this.batchNo,
      serialNo: serialNo ?? this.serialNo,
      serialAndBatchBundle: serialAndBatchBundle ?? this.serialAndBatchBundle,
      hasBatch: hasBatch,
      hasSerial: hasSerial,
    );
  }

  factory PickItemModel.fromJson(Map<String, dynamic> json) => PickItemModel(
    locationId: json['name'] as String? ?? json['location'] as String? ?? '',
    itemCode: json['item_code'] as String? ?? '',
    itemName: json['item_name'] as String? ?? '',
    size: json['size'] as String? ?? json['variant_size'] as String?,
    warehouse: json['warehouse'] as String? ?? '',
    requiredQty: (json['qty'] as num?)?.toInt() ?? (json['stock_qty'] as num?)?.toInt() ?? 1,
    pickedQty: (json['picked_qty'] as num?)?.toInt() ?? 0,
    barcode: json['barcode'] as String?,
    batchNo: json['batch_no'] as String?,
    serialNo: json['serial_no'] as String?,
    serialAndBatchBundle: json['serial_and_batch_bundle'] as String?,
    hasBatch: json['has_batch_no'] == 1 || json['has_batch'] == true,
    hasSerial: json['has_serial_no'] == 1 || json['has_serial'] == true,
  );

  Map<String, dynamic> toJson() => {
    'name': locationId,
    'item_code': itemCode,
    'item_name': itemName,
    'size': size,
    'warehouse': warehouse,
    'qty': requiredQty,
    'picked_qty': pickedQty,
    'barcode': barcode,
    'batch_no': batchNo,
    'serial_no': serialNo,
    'serial_and_batch_bundle': serialAndBatchBundle,
    'has_batch_no': hasBatch ? 1 : 0,
    'has_serial_no': hasSerial ? 1 : 0,
  };
}
