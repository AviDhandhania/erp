// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Represents a business rejection or sync conflict for an offline mutation.
@immutable
class ConflictModel {
  final String mutationId; // UUID of queued mutation
  final String operationType; // e.g. 'create_mobile_order'
  final Map<String, dynamic> payload;
  final String errorMessage;
  final String? serverErrorCode;
  final DateTime failedAt;
  final String resolutionStatus; // 'Unresolved' | 'Retried' | 'Discarded'

  const ConflictModel({
    required this.mutationId,
    required this.operationType,
    required this.payload,
    required this.errorMessage,
    this.serverErrorCode,
    required this.failedAt,
    this.resolutionStatus = 'Unresolved',
  });

  bool get isUnresolved => resolutionStatus == 'Unresolved';

  ConflictModel copyWith({String? resolutionStatus}) => ConflictModel(
    mutationId: mutationId,
    operationType: operationType,
    payload: payload,
    errorMessage: errorMessage,
    serverErrorCode: serverErrorCode,
    failedAt: failedAt,
    resolutionStatus: resolutionStatus ?? this.resolutionStatus,
  );

  factory ConflictModel.fromJson(Map<String, dynamic> json) => ConflictModel(
    mutationId: json['mutation_id'] as String? ?? '',
    operationType: json['operation_type'] as String? ?? '',
    payload: json['payload'] as Map<String, dynamic>? ?? const {},
    errorMessage: json['error_message'] as String? ?? 'Unknown sync failure',
    serverErrorCode: json['error_code'] as String?,
    failedAt: DateTime.tryParse(json['failed_at'] as String? ?? '') ?? DateTime.now(),
    resolutionStatus: json['resolution_status'] as String? ?? 'Unresolved',
  );

  Map<String, dynamic> toJson() => {
    'mutation_id': mutationId,
    'operation_type': operationType,
    'payload': payload,
    'error_message': errorMessage,
    'error_code': serverErrorCode,
    'failed_at': failedAt.toIso8601String(),
    'resolution_status': resolutionStatus,
  };
}
