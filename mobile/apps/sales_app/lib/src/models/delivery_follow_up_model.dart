// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Delivery follow-up obligation created after warehouse dispatch handoff.
@immutable
class DeliveryFollowUpModel {
  static const validOutcomes = <String>[
    'Goods Received in Full',
    'Shortage Reported',
    'Damage Reported',
    'Wrong Items Delivered',
    'Delivery Rejected',
  ];

  final String id;
  final String deliveryNote;
  final String? salesOrder;
  final String customer;
  final String customerName;
  final String territory;
  final DateTime deliveryDate;
  final String? carrier;
  final String? trackingNumber;
  final int cartonCount;
  final String status; // 'Pending Contact' | 'Satisfied' | 'Escalated'
  final List<String> packageBarcodes;
  final String? followUpOutcome;
  final String? issueNotes;

  const DeliveryFollowUpModel({
    required this.id,
    required this.deliveryNote,
    this.salesOrder,
    required this.customer,
    required this.customerName,
    required this.territory,
    required this.deliveryDate,
    this.carrier,
    this.trackingNumber,
    this.cartonCount = 1,
    this.status = 'Pending Contact',
    this.packageBarcodes = const [],
    this.followUpOutcome,
    this.issueNotes,
  });

  bool get isPending => status == 'Pending Contact';
  bool get isSatisfied => status == 'Satisfied';
  bool get isEscalated => status == 'Escalated';

  factory DeliveryFollowUpModel.fromJson(Map<String, dynamic> json) {
    final rawBarcodes = json['package_barcodes'] as List<dynamic>? ?? [];
    return DeliveryFollowUpModel(
      id: json['name'] as String? ?? '',
      deliveryNote: json['delivery_note'] as String? ?? '',
      salesOrder: json['sales_order'] as String?,
      customer: json['customer'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      territory: json['territory'] as String? ?? '',
      deliveryDate: DateTime.tryParse(json['delivery_date'] as String? ?? '') ?? DateTime.now(),
      carrier: json['carrier'] as String?,
      trackingNumber: json['tracking_no'] as String?,
      cartonCount: json['carton_count'] as int? ?? 1,
      status: json['status'] as String? ?? 'Pending Contact',
      packageBarcodes: rawBarcodes.map((b) => b.toString()).toList(),
      followUpOutcome: json['outcome'] as String?,
      issueNotes: json['issue_notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': id,
    'delivery_note': deliveryNote,
    'sales_order': salesOrder,
    'customer': customer,
    'customer_name': customerName,
    'territory': territory,
    'delivery_date': deliveryDate.toIso8601String().substring(0, 10),
    'carrier': carrier,
    'tracking_no': trackingNumber,
    'carton_count': cartonCount,
    'status': status,
    'package_barcodes': packageBarcodes,
    'outcome': followUpOutcome,
    'issue_notes': issueNotes,
  };
}
