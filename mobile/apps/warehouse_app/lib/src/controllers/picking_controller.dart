// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/pick_item_model.dart';
import '../models/fulfillment_task_model.dart';
import '../services/fulfillment_manager.dart';
import '../services/warehouse_local_cache.dart';

/// State controller for Pick List scanning, barcode resolution, and shortage splitting.
class PickingController {
  final FulfillmentManager fulfillmentManager;
  final WarehouseLocalCache localCache;
  final MobileScannerController scannerController;

  String? activePickList;
  List<PickItemModel> pickItems = [];
  bool isLoading = false;
  String? errorMessage;
  String? scanFeedbackMessage;
  bool isScanSuccess = false;
  bool isOnline = true;

  PickingController({
    required this.fulfillmentManager,
    required this.localCache,
    required this.scannerController,
  }) {
    // Listen for peripheral hardware wedge or camera scan events
    scannerController.scanStream.listen(_onBarcodeScanned);
  }

  Future<void> loadPickList(String pickList) async {
    activePickList = pickList;
    isLoading = true;
    errorMessage = null;

    try {
      final detail = await fulfillmentManager.apiService.getTaskDetail('pick', pickList);
      final rawLocations = detail['locations'] as List<dynamic>? ?? [];
      pickItems = rawLocations
          .whereType<Map<String, dynamic>>()
          .map((loc) => PickItemModel.fromJson(loc))
          .toList();

      // Cache locally
      await localCache.cachePickItems(pickList, pickItems);
      isOnline = true;
    } catch (e) {
      // Offline fallback: load from SQLCipher cache
      pickItems = await localCache.getCachedPickItems(pickList);
      isOnline = false;
      if (pickItems.isEmpty) {
        errorMessage = 'Task detail unavailable offline.';
      }
    } finally {
      isLoading = false;
    }
  }

  void _onBarcodeScanned(BarcodeScanEvent event) {
    if (activePickList == null || isLoading) return;
    scanItem(event.rawCode);
  }

  /// Scans a barcode (Code 128, EAN, Serial, Batch) against open items in this Pick List.
  Future<bool> scanItem(String barcode, {int quantity = 1}) async {
    if (activePickList == null) return false;

    // Find first matching unpicked or partially picked item
    final cleanCode = barcode.trim();
    final matchingIndex = pickItems.indexWhere((item) =>
        !item.isFullyPicked &&
        (item.barcode == cleanCode ||
         item.itemCode == cleanCode ||
         item.serialNo == cleanCode ||
         item.batchNo == cleanCode));

    if (matchingIndex < 0) {
      scanFeedbackMessage = 'Barcode $cleanCode does not match any pending row in $activePickList.';
      isScanSuccess = false;
      scannerController.feedbackDelegate?.onError('No matching row');
      return false;
    }

    final targetItem = pickItems[matchingIndex];
    isLoading = true;
    scanFeedbackMessage = null;

    try {
      final res = await fulfillmentManager.processScan(
        pickList: activePickList!,
        locationId: targetItem.locationId,
        barcode: cleanCode,
        quantity: quantity,
        warehouse: targetItem.warehouse,
        isOnline: isOnline,
      );

      // Optimistically update local pick item state
      pickItems[matchingIndex] = targetItem.copyWith(
        pickedQty: targetItem.pickedQty + quantity,
      );
      await localCache.cachePickItems(activePickList!, pickItems);

      scanFeedbackMessage = 'Scanned ${targetItem.itemCode} (Picked: ${pickItems[matchingIndex].pickedQty}/${targetItem.requiredQty})';
      isScanSuccess = true;
      scannerController.feedbackDelegate?.onSuccess(cleanCode);
      return true;
    } catch (e) {
      scanFeedbackMessage = 'Scan rejected by server: $e';
      isScanSuccess = false;
      scannerController.feedbackDelegate?.onError(e.toString());
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Reverses an unsubmitted scan on a specific row.
  Future<bool> undoScan(String locationId, {String? barcode, int quantity = 1}) async {
    if (activePickList == null) return false;

    final idx = pickItems.indexWhere((item) => item.locationId == locationId);
    if (idx < 0) return false;

    isLoading = true;
    try {
      await fulfillmentManager.undoScan(
        pickList: activePickList!,
        locationId: locationId,
        barcode: barcode,
        quantity: quantity,
      );

      final current = pickItems[idx];
      pickItems[idx] = current.copyWith(
        pickedQty: (current.pickedQty - quantity).clamp(0, current.requiredQty),
      );
      await localCache.cachePickItems(activePickList!, pickItems);
      return true;
    } catch (e) {
      errorMessage = 'Undo scan failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Splits an unpicked shortage row so remaining picked items can be completed.
  Future<bool> splitShortage(String locationId, int unpickedQty) async {
    if (activePickList == null) return false;

    isLoading = true;
    try {
      await fulfillmentManager.splitShortage(
        pickList: activePickList!,
        locationId: locationId,
        unpickedQty: unpickedQty,
      );
      // Reload updated task rows
      await loadPickList(activePickList!);
      return true;
    } catch (e) {
      errorMessage = 'Failed to split shortage row: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Completes Pick List and transitions to delivery preparation.
  Future<bool> completePick() async {
    if (activePickList == null) return false;

    isLoading = true;
    errorMessage = null;

    try {
      await fulfillmentManager.completePickList(
        pickList: activePickList!,
        isOnline: isOnline,
      );
      return true;
    } catch (e) {
      errorMessage = e.toString();
      return false;
    } finally {
      isLoading = false;
    }
  }
}
