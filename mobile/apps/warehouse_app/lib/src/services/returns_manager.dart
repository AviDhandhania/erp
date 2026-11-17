// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:clothing_core/clothing_core.dart';
import '../models/return_intake_model.dart';
import '../models/refurbishment_model.dart';
import 'warehouse_api_service.dart';
import 'warehouse_local_cache.dart';

/// Manages customer return intake, quarantine isolation, refurbishment operations,
/// and post-reinspection restock gates.
class ReturnsManager {
  final WarehouseApiService apiService;
  final WarehouseLocalCache localCache;
  final SafePhotoManager photoManager;

  ReturnsManager({
    required this.apiService,
    required this.localCache,
    required this.photoManager,
  });

  /// Captures and sanitizes defect evidence photo:
  /// - Strips EXIF/GPS
  /// - Enforces 2MB size limit
  /// - Calculates SHA-256 digest
  Future<String> processReturnEvidence(File rawPhoto) async {
    final safePhoto = await photoManager.processAndSanitize(
      sourceFile: rawPhoto,
      tag: 'return_defect',
    );
    return safePhoto.sanitizedPath;
  }

  /// Submits customer return garment into quarantine isolation.
  Future<Map<String, dynamic>> submitReturn(
    ReturnIntakeModel returnModel, {
    bool isOnline = true,
  }) async {
    if (!isOnline) {
      throw StateError('Cannot intake return while offline. Stock isolation requires server verification.');
    }

    if (!returnModel.canReturn(returnModel.returnQty)) {
      throw ArgumentError(
        'Return quantity (${returnModel.returnQty}) exceeds remaining returnable quantity (${returnModel.remainingReturnableQty}).',
      );
    }

    final res = await apiService.recordCustomerReturn(
      originalDeliveryNote: returnModel.originalDeliveryNote,
      itemCode: returnModel.itemCode,
      returnQty: returnModel.returnQty,
      returnReason: returnModel.returnReason,
      quarantineWarehouse: returnModel.quarantineWarehouse,
      conditionOnArrival: returnModel.conditionOnArrival,
      customer: returnModel.customer,
      batchNo: returnModel.batchNo,
      serialNo: returnModel.serialNo,
    );

    return res;
  }

  /// Intakes customer return garment into quarantine isolation (typed model return).
  Future<ReturnIntakeModel> intakeReturn({
    required ReturnIntakeModel returnModel,
    bool isOnline = true,
  }) async {
    if (!isOnline) {
      throw StateError('Cannot intake return while offline. Stock isolation requires server verification.');
    }
    return apiService.intakeReturn(returnModel);
  }

  /// Moves inspected quarantine item to refurbishment staging.
  Future<Map<String, dynamic>> moveToRefurbishment({
    required String quarantineName,
    required String refurbishmentWarehouse,
    required String requestId,
  }) async {
    return apiService.moveRefurbishment(
      quarantineName: quarantineName,
      refurbishmentWarehouse: refurbishmentWarehouse,
      requestId: requestId,
    );
  }

  /// Assigns refurbishment operation to a technician.
  Future<Map<String, dynamic>> assignRefurbishment({
    required String quarantineName,
    required String assignee,
    required String operation,
    double estimatedCost = 0.0,
    String? consumedMaterial,
    String? photoBefore,
    String? notes,
    required String requestId,
  }) async {
    return apiService.assignRefurbishment(
      quarantineName: quarantineName,
      assignee: assignee,
      operation: operation,
      estimatedCost: estimatedCost,
      consumedMaterial: consumedMaterial,
      photoBefore: photoBefore,
      notes: notes,
      requestId: requestId,
    );
  }

  /// Completes refurbishment work and submits for reinspection.
  Future<Map<String, dynamic>> completeRefurbishmentWork({
    required String quarantineName,
    String? photoAfter,
    String? consumedMaterial,
    double? actualCost,
    String? notes,
    required String requestId,
  }) async {
    return apiService.completeRefurbishmentWork(
      quarantineName: quarantineName,
      photoAfter: photoAfter,
      consumedMaterial: consumedMaterial,
      actualCost: actualCost,
      notes: notes,
      requireReinspection: true,
      requestId: requestId,
    );
  }

  /// Restocks passed refurbished garment to saleable stock.
  /// Strictly rejected if post-reinspection is not passed.
  Future<Map<String, dynamic>> restockToSaleable({
    RefurbishmentModel? task,
    RefurbishmentModel? refurbishment,
    String? saleableWarehouse,
    String? targetSaleableWarehouse,
    String? notes,
    String? requestId,
  }) async {
    final model = task ?? refurbishment;
    if (model == null) {
      throw ArgumentError('Refurbishment model is required.');
    }

    final targetWarehouse = saleableWarehouse ?? targetSaleableWarehouse ?? model.saleableWarehouse;

    if (model.reinspectionStatus != 'Passed') {
      throw StateError(
        'Cannot restock item to saleable inventory: '
        'Post-refurbishment quality inspection has not passed (Status: ${model.reinspectionStatus}).',
      );
    }

    return apiService.completeRefurbishment(
      quarantineName: model.quarantineName,
      targetSaleableWarehouse: targetWarehouse,
      notes: notes,
      requestId: requestId ?? 'req-${DateTime.now().microsecondsSinceEpoch}',
    );
  }
}
