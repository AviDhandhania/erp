// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/conflict_model.dart';
import '../services/sales_local_cache.dart';

/// State controller for reviewing and resolving offline synchronization conflicts.
class ConflictsController {
  final SalesLocalCache localCache;
  final OfflineMutationQueue mutationQueue;

  List<ConflictModel> conflicts = [];
  bool isLoading = false;
  String? errorMessage;

  ConflictsController({
    required this.localCache,
    required this.mutationQueue,
  });

  Future<void> fetchConflicts() async {
    isLoading = true;
    errorMessage = null;
    try {
      conflicts = await localCache.getUnresolvedConflicts();
    } catch (e) {
      errorMessage = 'Failed to load conflicts: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Retries a conflict mutation by re-queuing into OfflineMutationQueue.
  Future<void> retryConflict(ConflictModel conflict) async {
    await mutationQueue.enqueue(
      id: conflict.mutationId,
      endpoint: '/api/method/sales_erp.mobile_api.${conflict.operationType}',
      payload: conflict.payload,
    );
    await localCache.updateConflictResolution(conflict.mutationId, 'Retried');
    conflicts.removeWhere((c) => c.mutationId == conflict.mutationId);
  }

  /// Discards a conflict mutation permanently.
  Future<void> discardConflict(String mutationId) async {
    await localCache.updateConflictResolution(mutationId, 'Discarded');
    conflicts.removeWhere((c) => c.mutationId == mutationId);
  }
}
