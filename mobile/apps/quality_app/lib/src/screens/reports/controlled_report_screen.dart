// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/controlled_report_controller.dart';
import '../../models/controlled_report_model.dart';

/// Screen presenting controlled, watermarked PDF report preview with ephemeral device storage.
class ControlledReportScreen {
  final ControlledReportController controller;

  const ControlledReportScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final report = controller.activeReport;

    if (report == null) {
      return {'state': 'empty', 'message': 'No controlled report loaded.'};
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'cycle_key': report.cycleKey,
      'inspection_name': report.inspectionName,
      'watermark_text': report.watermarkText,
      'bundle_hash': report.bundleHash,
      'expires_at': report.expiresAt.toIso8601String(),
      'is_expired': report.isExpired,
      'remaining_seconds': report.remainingDuration.inSeconds,
      'file_size_bytes': report.fileSizeBytes,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'ephemeral_policy': {
        'notice': 'Controlled Copy: Access token expires automatically. Local copy will be purged on expiry or session close.',
        'zero_permanent_urls': true,
      },
      'actions': [
        'refresh_preview',
        'cleanup_expired',
      ],
    };
  }
}
