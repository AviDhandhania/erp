// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Represents an offline scan reconciliation failure or multi-device concurrency collision.
///
/// Stock Invariant:
/// Native document submission and stock transitions remain strictly BLOCKED
/// while any unresolved conflict exists in the local database.
@immutable
class WarehouseConflictModel {
  final String mutationId; // UUID of queued scan mutation
  final String operationType; // 'verify_mobile_scan' | 'complete_mobile_pick' | 'intake_mobile_return'
  final String documentReference; // Pick List or Delivery Note identifier
  final String scannedBarcode;
  final String errorMessage;
  final String? serverErrorCode;
  final DateTime failedAt;
  final String resolutionStatus; // 'Unresolved' | 'Discarded' | 'Retried'

  const WarehouseConflictModel({
    required this.mutationId,
    required this.operationType,
    required this.documentReference,
    required this.scannedBarcode,
    required this.errorMessage,
    this.serverErrorCode,
    required this.failedAt,
    this.resolutionStatus = 'Unresolved',
  });

  bool get isUnresolved => resolutionStatus == 'Unresolved';

  WarehouseConflictModel copyWith({String? resolutionStatus}) => WarehouseConflictModel(
    mutationId: mutationId,
    operationType: operationType,
    documentReference: documentReference,
    scannedBarcode: scannedBarcode,
    errorMessage: errorMessage,
    serverErrorCode: serverErrorCode,
    failedAt: failedAt,
    resolutionStatus: resolutionStatus ?? this.resolutionStatus,
  );

  factory WarehouseConflictModel.fromJson(Map<String, dynamic> json) => WarehouseConflictModel(
    mutationId: json['mutation_id'] as String? ?? '',
    operationType: json['operation_type'] as String? ?? '',
    documentReference: json['document_reference'] as String? ?? json['document_name'] as String? ?? '',
    scannedBarcode: json['scanned_barcode'] as String? ?? '',
    errorMessage: json['error_message'] as String? ?? 'Scan validation failed on server',
    serverErrorCode: json['error_code'] as String?,
    failedAt: DateTime.tryParse(json['failed_at'] as String? ?? '') ?? DateTime.now(),
    resolutionStatus: json['resolution_status'] as String? ?? 'Unresolved',
  );

  Map<String, dynamic> toJson() => {
    'mutation_id': mutationId,
    'operation_type': operationType,
    'document_reference': documentReference,
    'scanned_barcode': scannedBarcode,
    'error_message': errorMessage,
    'error_code': serverErrorCode,
    'failed_at': failedAt.toIso8601String(),
    'resolution_status': resolutionStatus,
  };
}
