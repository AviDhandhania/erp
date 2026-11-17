// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Ephemeral controlled quality inspection report representation.
///
/// Security Boundary:
/// - Never exposes permanent private File URLs.
/// - Bound to short-lived HMAC token with strict expiry window (e.g. 15 minutes).
/// - Embeds watermarking with viewer identity, timestamp, and audit hash.
/// - Deleted from device storage immediately on token expiry, logout, or session revocation.
@immutable
class ControlledReportModel {
  final String reportToken;
  final String cycleKey;
  final String? inspectionName;
  final String watermarkText;
  final String bundleHash;
  final DateTime expiresAt;
  final String? localTempPath;
  final int fileSizeBytes;

  const ControlledReportModel({
    required this.reportToken,
    required this.cycleKey,
    this.inspectionName,
    required this.watermarkText,
    required this.bundleHash,
    required this.expiresAt,
    this.localTempPath,
    this.fileSizeBytes = 0,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);
  Duration get remainingDuration => expiresAt.difference(DateTime.now());

  factory ControlledReportModel.fromJson(Map<String, dynamic> json) {
    return ControlledReportModel(
      reportToken: json['report_token'] as String? ?? json['token'] as String? ?? '',
      cycleKey: json['cycle_key'] as String? ?? '',
      inspectionName: json['inspection_name'] as String?,
      watermarkText: json['watermark_text'] as String? ?? 'CONFIDENTIAL - CONTROLLED COPY',
      bundleHash: json['bundle_hash'] as String? ?? '',
      expiresAt: DateTime.tryParse(json['expires_at'] as String? ?? '') ??
          DateTime.now().add(const Duration(minutes: 15)),
      localTempPath: json['local_temp_path'] as String?,
      fileSizeBytes: (json['file_size_bytes'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'report_token': reportToken,
    'cycle_key': cycleKey,
    'inspection_name': inspectionName,
    'watermark_text': watermarkText,
    'bundle_hash': bundleHash,
    'expires_at': expiresAt.toIso8601String(),
    'local_temp_path': localTempPath,
    'file_size_bytes': fileSizeBytes,
    'is_expired': isExpired,
  };
}
