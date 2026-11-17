// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/warehouse_boot_model.dart';
import '../services/warehouse_api_service.dart';
import '../services/warehouse_local_cache.dart';

/// State controller for the Warehouse Home dashboard and assigned warehouse scoping.
class WarehouseHomeController {
  final WarehouseApiService apiService;
  final WarehouseLocalCache? localCache;
  final SessionLifecycleManager sessionLifecycle;

  WarehouseBootModel? bootContext;
  WarehouseBootModel? get bootModel => bootContext;
  String? selectedWarehouse;
  bool isLoading = false;
  String? errorMessage;
  bool isOnline = true;
  int unresolvedConflictsCount = 0;

  WarehouseHomeController({
    required this.apiService,
    this.localCache,
    required this.sessionLifecycle,
  });

  int get pendingPickCount => bootContext?.queues.pendingPick ?? 0;
  int get pendingPackCount => bootContext?.queues.pendingPack ?? 0;
  int get pendingDispatchCount => bootContext?.queues.pendingDispatch ?? 0;
  int get pendingReturnsCount => bootContext?.queues.pendingReturns ?? 0;
  int get activeRefurbishmentCount => bootContext?.queues.activeRefurbishment ?? 0;

  /// Bootstraps manager session (alias for loadDashboard).
  Future<void> bootstrapSession() async {
    return loadDashboard();
  }

  /// Loads manager context and strictly validates role.
  /// Rejects unauthorized roles (e.g. operators) and wipes session immediately.
  Future<void> loadDashboard() async {
    isLoading = true;
    errorMessage = null;

    try {
      final boot = await apiService.getBoot();
      bootContext = boot;

      // Strict role check: must be Clothing Warehouse Manager or Business Admin
      if (!boot.hasAuthorizedManagerRole) {
        await sessionLifecycle.wipeSessionAndCache();
        throw const SecurityException(
          'Access denied: User does not possess an authorized Clothing Warehouse Manager role.',
        );
      }

      if (boot.assignedWarehouses.isNotEmpty && boot.assignedWarehouses.first != '*') {
        selectedWarehouse = boot.assignedWarehouses.first;
      }

      if (localCache != null) {
        final conflicts = await localCache!.getUnresolvedConflicts();
        unresolvedConflictsCount = conflicts.length;
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

  void selectWarehouse(String warehouse) {
    if (bootContext != null && bootContext!.isWarehouseAllowed(warehouse)) {
      selectedWarehouse = warehouse;
    }
  }
}
