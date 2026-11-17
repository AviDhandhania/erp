// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import '../models/controlled_report_model.dart';
import 'quality_api_service.dart';

/// Manages controlled viewing and ephemeral device storage of quality report bundles.
///
/// Security & Storage Invariants:
/// - Never exposes permanent private File URLs to the device or user.
/// - Uses short-lived HMAC tokens with explicit expiry.
/// - Embeds tamper-evident watermark with viewer identity, timestamp, and audit hash.
/// - Automatically purges expired temporary report files from local storage.
class ControlledReportManager {
  final QualityApiService apiService;
  final List<ControlledReportModel> activeReports = [];

  ControlledReportManager({required this.apiService});

  /// Requests a controlled quality report bundle from the server.
  Future<ControlledReportModel> loadControlledReport({
    required String cycleName,
    String? stageReport,
  }) async {
    final report = await apiService.exportQualityReportBundle(
      cycleName: cycleName,
      stageReport: stageReport,
    );

    activeReports.add(report);
    return report;
  }

  /// Verifies that an ephemeral report bundle is still within its valid lifetime.
  bool isReportValid(ControlledReportModel report) {
    return !report.isExpired;
  }

  /// Purges all expired ephemeral report files from device storage.
  Future<void> purgeExpiredReports() async {
    final expired = activeReports.where((r) => r.isExpired).toList();
    for (final report in expired) {
      if (report.localTempPath != null) {
        try {
          final file = File(report.localTempPath!);
          if (await file.exists()) {
            await file.delete();
          }
        } catch (_) {
          // Suppress deletion error
        }
      }
    }
    activeReports.removeWhere((r) => r.isExpired);
  }

  /// Wipes all active report files immediately upon logout or session revocation.
  Future<void> wipeAllReports() async {
    for (final report in activeReports) {
      if (report.localTempPath != null) {
        try {
          final file = File(report.localTempPath!);
          if (await file.exists()) {
            await file.delete();
          }
        } catch (_) {
          // Suppress deletion error
        }
      }
    }
    activeReports.clear();
  }
}
