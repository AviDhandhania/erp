// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/production_cycle_model.dart';
import 'quality_api_service.dart';
import 'quality_local_cache.dart';

/// Coordinates production cycle work queues, stage progression, and visit sequences.
class QualityCycleManager {
  final QualityApiService apiService;
  final QualityLocalCache localCache;

  QualityCycleManager({
    required this.apiService,
    required this.localCache,
  });

  /// Loads active production cycles, falling back to encrypted cache if offline.
  Future<List<ProductionCycleModel>> loadCycles({
    String? supplier,
    String? status,
    bool isOnline = true,
  }) async {
    if (isOnline) {
      try {
        final cycles = await apiService.getProductionCycles(
          supplier: supplier,
          status: status,
        );
        await localCache.cacheCycles(cycles);
        return cycles;
      } catch (_) {
        // Fallback to local encrypted cache
        return localCache.getCachedCycles(supplier: supplier, status: status);
      }
    } else {
      return localCache.getCachedCycles(supplier: supplier, status: status);
    }
  }

  /// Calculates the next visit number for Inline (Stage 5) or Mid-line (Stage 6) visits.
  int getNextVisitNumber({
    required ProductionCycleModel cycle,
    required int stage,
    required int existingVisitsCount,
  }) {
    if (stage == 5 || stage == 6) {
      return existingVisitsCount + 1;
    }
    return 1;
  }

  /// Evaluates whether a production cycle is blocked awaiting high-risk gate review.
  bool isCycleBlockedForGate(ProductionCycleModel cycle) {
    if (cycle.currentStage == 4 && cycle.gateReviewStatus != 'Approved') {
      return true; // Production Go Ahead required before cutting/production
    }
    if (cycle.currentStage == 7 && cycle.gateReviewStatus != 'Approved') {
      return true; // Final Inspection clearance required before release
    }
    return false;
  }
}
