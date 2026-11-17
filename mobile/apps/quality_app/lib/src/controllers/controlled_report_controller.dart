// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/controlled_report_model.dart';
import '../services/controlled_report_manager.dart';

/// State controller for controlled PDF inspection report preview and ephemeral device storage.
class ControlledReportController {
  final ControlledReportManager reportManager;

  ControlledReportModel? activeReport;
  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  ControlledReportController({required this.reportManager});

  /// Loads ephemeral report bundle for viewing.
  Future<void> loadReport({
    required String cycleName,
    String? stageReport,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      activeReport = await reportManager.loadControlledReport(
        cycleName: cycleName,
        stageReport: stageReport,
      );
      statusMessage = 'Report bundle loaded with ephemeral access token.';
    } catch (e) {
      errorMessage = 'Failed to load report bundle: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Verifies if active report is still valid or has expired.
  bool get isReportActive => activeReport != null && !activeReport!.isExpired;

  /// Purges expired reports.
  Future<void> cleanupExpired() async {
    await reportManager.purgeExpiredReports();
    if (activeReport != null && activeReport!.isExpired) {
      activeReport = null;
      statusMessage = 'Previous report access expired and was purged from local device storage.';
    }
  }
}
