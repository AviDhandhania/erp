// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/quality_boot_model.dart';
import '../services/quality_api_service.dart';
import '../services/quality_local_cache.dart';

/// State controller for Quality Home dashboard, role validation, and queue summaries.
class QualityHomeController {
  final QualityApiService apiService;
  final QualityLocalCache? localCache;
  final SessionLifecycleManager sessionLifecycle;

  QualityBootModel? bootContext;
  bool isLoading = false;
  String? errorMessage;
  bool isOnline = true;

  QualityHomeController({
    required this.apiService,
    this.localCache,
    required this.sessionLifecycle,
  });

  int get activeCyclesCount => bootContext?.queues.activeCycles ?? 0;
  int get stageDueCount => bootContext?.queues.stageDue ?? 0;
  int get pendingCorrectionsCount => bootContext?.queues.pendingCorrections ?? 0;
  int get returnsAwaitingInspectionCount => bootContext?.queues.returnsAwaitingInspection ?? 0;
  int get pendingGateReviewsCount => bootContext?.queues.pendingGateReviews ?? 0;

  /// Loads boot context and validates quality roles.
  Future<void> loadDashboard() async {
    isLoading = true;
    errorMessage = null;

    try {
      final boot = await apiService.getBoot();
      bootContext = boot;

      if (!boot.hasAuthorizedQualityRole) {
        await sessionLifecycle.wipeSessionAndCache();
        throw const SecurityException(
          'Access denied: User does not possess an authorized Clothing Quality role.',
        );
      }

      isOnline = true;
    } on ClothingApiException catch (e) {
      errorMessage = e.message;
      if (e.isSessionRevoked) {
        await sessionLifecycle.wipeSessionAndCache();
      }
    } on SecurityException catch (e) {
      errorMessage = e.message;
      await sessionLifecycle.wipeSessionAndCache();
      rethrow;
    } catch (e) {
      errorMessage = 'Network connection unavailable. Operating in offline mode.';
      isOnline = false;
    } finally {
      isLoading = false;
    }
  }
}
