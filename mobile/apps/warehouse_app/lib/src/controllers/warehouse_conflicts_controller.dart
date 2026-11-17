// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/warehouse_conflict_model.dart';
import '../services/warehouse_local_cache.dart';
import '../services/fulfillment_manager.dart';

/// State controller for reviewing and resolving offline scan reconciliation failures and races.
class WarehouseConflictsController {
  final WarehouseLocalCache localCache;
  final FulfillmentManager fulfillmentManager;

  List<WarehouseConflictModel> conflicts = [];
  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  WarehouseConflictsController({
    required this.localCache,
    required this.fulfillmentManager,
  });

  /// Fetches all unresolved offline reconciliation and concurrency conflicts.
  Future<void> fetchConflicts() async {
    isLoading = true;
    errorMessage = null;
    try {
      conflicts = await localCache.getUnresolvedConflicts();
      statusMessage = 'Found ${conflicts.length} unresolved scan conflicts.';
    } catch (e) {
      errorMessage = 'Failed to load conflicts: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Retries an offline scan conflict against the server.
  Future<bool> retryConflict(WarehouseConflictModel conflict) async {
    isLoading = true;
    errorMessage = null;

    try {
      if (conflict.operationType == 'scan_barcode' &&
          conflict.documentReference != null &&
          conflict.scannedBarcode != null) {
        // Attempt scan validation again online
        final result = await fulfillmentManager.recordScan(
          pickList: conflict.documentReference!,
          locationId: 'LOC-RETRY',
          barcode: conflict.scannedBarcode!,
        );

        if (result['success'] == true) {
          await localCache.updateConflictResolution(conflict.mutationId, 'Resolved');
          conflicts.removeWhere((c) => c.mutationId == conflict.mutationId);
          statusMessage = 'Conflict resolved: scan accepted.';
          return true;
        } else {
          errorMessage = 'Retry rejected: ${result['error']}';
          return false;
        }
      } else {
        errorMessage = 'Unsupported conflict retry operation: ${conflict.operationType}';
        return false;
      }
    } catch (e) {
      errorMessage = 'Retry failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Discards a conflict permanently from the queue.
  Future<void> discardConflict(String mutationId) async {
    await localCache.updateConflictResolution(mutationId, 'Discarded');
    conflicts.removeWhere((c) => c.mutationId == mutationId);
    statusMessage = 'Conflict discarded.';
  }

  /// Triggers full reconciliation of all pending offline scans.
  Future<Map<String, dynamic>> reconcileOfflineScans() async {
    isLoading = true;
    errorMessage = null;
    try {
      final res = await fulfillmentManager.reconcileOfflineScans();
      await fetchConflicts();
      statusMessage = 'Reconciliation complete: ${res['reconciled']} reconciled, ${res['conflicts']} conflicts.';
      return res;
    } catch (e) {
      errorMessage = 'Reconciliation error: $e';
      return {'reconciled': 0, 'conflicts': 0, 'error': e.toString()};
    } finally {
      isLoading = false;
    }
  }
}
