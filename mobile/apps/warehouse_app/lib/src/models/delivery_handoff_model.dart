// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Immutable carrier handoff record confirming physical transfer to logistics.
@immutable
class DeliveryHandoffModel {
  final String? handoffName; // Created Handoff record name
  final String deliveryNote;
  final String transporterName;
  final String acceptedByHandler;
  final int packagesCount;
  final double grossWeight;
  final String? vehicleNo;
  final String? lrNo; // Lorry Receipt / Air Waybill / Tracking
  final DateTime? lrDate;
  final String? driverName;
  final String? driverPhone;
  final String? proofPhotoUrl;
  final String? notes;
  final String requestId; // UUID idempotency key
  final DateTime? handoffTimestamp;

  const DeliveryHandoffModel({
    this.handoffName,
    required this.deliveryNote,
    required this.transporterName,
    required this.acceptedByHandler,
    this.packagesCount = 1,
    this.grossWeight = 0.0,
    this.vehicleNo,
    this.lrNo,
    this.lrDate,
    this.driverName,
    this.driverPhone,
    this.proofPhotoUrl,
    this.notes,
    required this.requestId,
    this.handoffTimestamp,
  });

  factory DeliveryHandoffModel.fromJson(Map<String, dynamic> json) => DeliveryHandoffModel(
    handoffName: json['name'] as String? ?? json['handoff_id'] as String?,
    deliveryNote: json['delivery_note'] as String? ?? '',
    transporterName: json['transporter_name'] as String? ?? '',
    acceptedByHandler: json['accepted_by_handler'] as String? ?? '',
    packagesCount: (json['packages_count'] as num?)?.toInt() ?? 1,
    grossWeight: (json['gross_weight'] as num?)?.toDouble() ?? 0.0,
    vehicleNo: json['vehicle_no'] as String?,
    lrNo: json['lr_no'] as String?,
    lrDate: DateTime.tryParse(json['lr_date'] as String? ?? ''),
    driverName: json['driver_name'] as String?,
    driverPhone: json['driver_phone'] as String?,
    proofPhotoUrl: json['proof_photo'] as String?,
    notes: json['notes'] as String?,
    requestId: json['request_id'] as String? ?? '',
    handoffTimestamp: DateTime.tryParse(json['creation'] as String? ?? json['handoff_timestamp'] as String? ?? ''),
  );

  Map<String, dynamic> toJson() => {
    'name': handoffName,
    'delivery_note': deliveryNote,
    'transporter_name': transporterName,
    'accepted_by_handler': acceptedByHandler,
    'packages_count': packagesCount,
    'gross_weight': grossWeight,
    'vehicle_no': vehicleNo,
    'lr_no': lrNo,
    'lr_date': lrDate?.toIso8601String().substring(0, 10),
    'driver_name': driverName,
    'driver_phone': driverPhone,
    'proof_photo': proofPhotoUrl,
    'notes': notes,
    'request_id': requestId,
    'handoff_timestamp': handoffTimestamp?.toIso8601String(),
  };
}
