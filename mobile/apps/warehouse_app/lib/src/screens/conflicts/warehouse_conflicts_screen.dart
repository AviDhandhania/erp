// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/warehouse_conflicts_controller.dart';
import '../../models/warehouse_conflict_model.dart';

/// Screen presenting unresolved offline reconciliation failures, scan conflicts, and concurrency collisions.
///
/// Features:
/// - Unresolved conflict queue with error code, message, and original barcode/document.
/// - Retry conflict mutation online.
/// - Discard invalid or conflicting mutation permanently.
/// - Full offline scan queue reconciliation trigger.
class WarehouseConflictsScreen {
  final WarehouseConflictsController controller;

  const WarehouseConflictsScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'conflicts_count': controller.conflicts.length,
      'has_unresolved_conflicts': controller.conflicts.isNotEmpty,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'conflicts': controller.conflicts.map((c) => {
        'mutation_id': c.mutationId,
        'operation_type': c.operationType,
        'document_reference': c.documentReference,
        'scanned_barcode': c.scannedBarcode,
        'error_message': c.errorMessage,
        'server_error_code': c.serverErrorCode,
        'failed_at': c.failedAt.toIso8601String(),
        'resolution_status': c.resolutionStatus,
      }).toList(),
      'guidance': 'Offline scans that fail server validation (e.g., item already picked on another device or invalid barcode) must be reviewed and resolved before native documents can be completed.',
      'actions': [
        'refresh_conflicts',
        'retry_conflict',
        'discard_conflict',
        'reconcile_all_pending',
      ],
    };
  }
}
