// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Refurbishment tracking model representing garment repair operations and post-reinspection gates.
@immutable
class RefurbishmentModel {
  static const validOperations = <String>[
    'Steam Pressing',
    'Button Replacement',
    'Stitch Repair',
    'Label Reattachment',
    'Packaging Replacement',
    'Spot Cleaning',
  ];

  final String quarantineName;
  final String itemCode;
  final String? itemName;
  final int quantity;
  final String currentWarehouse;
  final String status; // 'Awaiting Refurbishment' | 'In Progress' | 'Awaiting Reinspection' | 'Reinspection Passed' | 'Restocked'
  final String? operation;
  final String? assignee;
  final double estimatedCost;
  final double? actualCost;
  final String? consumedMaterial;
  final String? photoBefore;
  final String? photoAfter;
  final String reinspectionStatus; // 'Pending' | 'Passed' | 'Rejected'
  final String? targetSaleableWarehouse;

  const RefurbishmentModel({
    required this.quarantineName,
    required this.itemCode,
    this.itemName,
    required this.quantity,
    required this.currentWarehouse,
    required this.status,
    this.operation,
    this.assignee,
    this.estimatedCost = 0.0,
    this.actualCost,
    this.consumedMaterial,
    this.photoBefore,
    this.photoAfter,
    this.reinspectionStatus = 'Pending',
    this.targetSaleableWarehouse,
  });

  /// Crucial Quality Gate:
  /// Moving to saleable inventory strictly requires reinspection to have Passed.
  bool get canRestock => reinspectionStatus == 'Passed' && status != 'Restocked';
  bool get isRestocked => status == 'Restocked';

  factory RefurbishmentModel.fromJson(Map<String, dynamic> json) => RefurbishmentModel(
    quarantineName: json['name'] as String? ?? json['quarantine_name'] as String? ?? '',
    itemCode: json['item_code'] as String? ?? '',
    itemName: json['item_name'] as String?,
    quantity: (json['quantity'] as num?)?.toInt() ?? 1,
    currentWarehouse: json['warehouse'] as String? ?? json['quarantine_warehouse'] as String? ?? '',
    status: json['status'] as String? ?? 'Awaiting Refurbishment',
    operation: json['operation'] as String?,
    assignee: json['assignee'] as String?,
    estimatedCost: (json['estimated_cost'] as num?)?.toDouble() ?? 0.0,
    actualCost: (json['actual_cost'] as num?)?.toDouble(),
    consumedMaterial: json['consumed_material'] as String?,
    photoBefore: json['photo_before'] as String?,
    photoAfter: json['photo_after'] as String?,
    reinspectionStatus: json['post_reinspection_status'] as String? ?? json['reinspection_status'] as String? ?? 'Pending',
    targetSaleableWarehouse: json['target_saleable_warehouse'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'name': quarantineName,
    'item_code': itemCode,
    'item_name': itemName,
    'quantity': quantity,
    'warehouse': currentWarehouse,
    'status': status,
    'operation': operation,
    'assignee': assignee,
    'estimated_cost': estimatedCost,
    'actual_cost': actualCost,
    'consumed_material': consumedMaterial,
    'photo_before': photoBefore,
    'photo_after': photoAfter,
    'post_reinspection_status': reinspectionStatus,
    'target_saleable_warehouse': targetSaleableWarehouse,
  };
}
