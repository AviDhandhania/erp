// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Fulfillment task summary for picking, packing, and dispatch work queues.
@immutable
class FulfillmentTaskModel {
  final String taskType; // 'pick' | 'pack' | 'dispatch'
  final String name; // Document identifier (e.g. PICK-2026-0001 or DN-2026-0001)
  final String customer;
  final String customerName;
  final String warehouse;
  final String status; // 'Draft' | 'Open' | 'Completed' | 'Cancelled'
  final int totalQty;
  final int pickedQty;
  final double progressPercent;
  final String? waveId;
  final String? routeId;
  final bool hasShortage;
  final DateTime? deliveryDate;

  const FulfillmentTaskModel({
    required this.taskType,
    required this.name,
    required this.customer,
    required this.customerName,
    required this.warehouse,
    required this.status,
    required this.totalQty,
    this.pickedQty = 0,
    this.progressPercent = 0.0,
    this.waveId,
    this.routeId,
    this.hasShortage = false,
    this.deliveryDate,
  });

  bool get isCompleted => status == 'Completed' || (totalQty > 0 && pickedQty >= totalQty);
  bool get isOpen => status == 'Open' || status == 'Draft';

  factory FulfillmentTaskModel.fromJson(Map<String, dynamic> json) {
    final tQty = (json['total_qty'] as num?)?.toInt() ?? 0;
    final pQty = (json['picked_qty'] as num?)?.toInt() ?? 0;
    final progress = tQty > 0 ? (pQty / tQty) * 100.0 : 0.0;

    return FulfillmentTaskModel(
      taskType: json['task_type'] as String? ?? 'pick',
      name: json['name'] as String? ?? '',
      customer: json['customer'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      warehouse: json['warehouse'] as String? ?? '',
      status: json['status'] as String? ?? 'Draft',
      totalQty: tQty,
      pickedQty: pQty,
      progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? progress,
      waveId: json['wave_id'] as String?,
      routeId: json['route_id'] as String?,
      hasShortage: json['has_shortage'] as bool? ?? false,
      deliveryDate: DateTime.tryParse(json['delivery_date'] as String? ?? ''),
    );
  }

  Map<String, dynamic> toJson() => {
    'task_type': taskType,
    'name': name,
    'customer': customer,
    'customer_name': customerName,
    'warehouse': warehouse,
    'status': status,
    'total_qty': totalQty,
    'picked_qty': pickedQty,
    'progress_percent': progressPercent,
    'wave_id': waveId,
    'route_id': routeId,
    'has_shortage': hasShortage,
    'delivery_date': deliveryDate?.toIso8601String().substring(0, 10),
  };
}
