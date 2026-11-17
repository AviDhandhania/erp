// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/refurbishment_model.dart';
import '../services/returns_manager.dart';

/// State controller for refurbishment operations, repair tracking, and restock gates.
class RefurbishmentController {
  final ReturnsManager returnsManager;

  List<RefurbishmentModel> refurbishmentItems = [];
  bool isLoading = false;
  String? errorMessage;

  RefurbishmentController({required this.returnsManager});

  Future<void> fetchRefurbishmentQueue({String? warehouse}) async {
    isLoading = true;
    errorMessage = null;

    try {
      final res = await returnsManager.apiService.getReturnsDashboard(warehouse: warehouse);
      final rawItems = res['refurbishment_queue'] as List<dynamic>? ?? [];
      refurbishmentItems = rawItems
          .whereType<Map<String, dynamic>>()
          .map((r) => RefurbishmentModel.fromJson(r))
          .toList();
    } catch (e) {
      errorMessage = 'Failed to load refurbishment queue: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Assigns repair operation to a technician.
  Future<bool> assignOperation({
    required String quarantineName,
    required String assignee,
    required String operation,
    double estimatedCost = 0.0,
    String? notes,
  }) async {
    isLoading = true;
    errorMessage = null;
    final reqId = 'ref-assign-${DateTime.now().microsecondsSinceEpoch}';

    try {
      await returnsManager.assignRefurbishment(
        quarantineName: quarantineName,
        assignee: assignee,
        operation: operation,
        estimatedCost: estimatedCost,
        notes: notes,
        requestId: reqId,
      );
      final idx = refurbishmentItems.indexWhere((r) => r.quarantineName == quarantineName);
      if (idx >= 0) {
        final current = refurbishmentItems[idx];
        refurbishmentItems[idx] = RefurbishmentModel(
          quarantineName: current.quarantineName,
          itemCode: current.itemCode,
          itemName: current.itemName,
          quantity: current.quantity,
          currentWarehouse: current.currentWarehouse,
          status: 'In Progress',
          operation: operation,
          assignee: assignee,
          estimatedCost: estimatedCost,
          reinspectionStatus: 'Pending',
        );
      }
      return true;
    } catch (e) {
      errorMessage = 'Failed to assign operation: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Restocks passed refurbished garment to saleable stock.
  /// Strictly rejected if post-reinspection is not passed.
  Future<bool> restockGarment({
    required RefurbishmentModel item,
    required String targetSaleableWarehouse,
  }) async {
    if (!item.canRestock) {
      errorMessage = 'Restock blocked: Post-refurbishment quality reinspection is required (Current status: ${item.reinspectionStatus}).';
      return false;
    }

    isLoading = true;
    errorMessage = null;
    final reqId = 'restock-${DateTime.now().microsecondsSinceEpoch}';

    try {
      await returnsManager.restockToSaleable(
        refurbishment: item,
        targetSaleableWarehouse: targetSaleableWarehouse,
        requestId: reqId,
      );
      refurbishmentItems.removeWhere((r) => r.quarantineName == item.quarantineName);
      return true;
    } catch (e) {
      errorMessage = 'Failed to restock garment: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
