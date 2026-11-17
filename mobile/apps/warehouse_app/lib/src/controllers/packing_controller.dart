// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/packing_model.dart';
import '../models/fulfillment_task_model.dart';
import '../services/fulfillment_manager.dart';

/// State controller for package measurement capture, carton identity, and packing slips.
class PackingController {
  final FulfillmentManager fulfillmentManager;

  List<FulfillmentTaskModel> packTasks = [];
  bool isLoading = false;
  String? errorMessage;
  PackingPackageModel? createdPackage;

  PackingController({required this.fulfillmentManager});

  Future<void> fetchPackingTasks({String? warehouse, String? search}) async {
    isLoading = true;
    errorMessage = null;

    try {
      final res = await fulfillmentManager.apiService.getTasks(
        taskType: 'pack',
        state: 'open',
        search: search,
      );
      packTasks = res.items;
    } catch (e) {
      errorMessage = 'Failed to load packing tasks: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Creates a Packing Slip with package identity, weight, and cubic dimensions.
  Future<bool> createPackageSlip({
    required String deliveryNote,
    required String cartonBarcode,
    int caseNumber = 1,
    double grossWeightPkg = 0.0,
    double netWeightPkg = 0.0,
    double? length,
    double? width,
    double? height,
    String dimensionUom = 'cm',
    bool isOnline = true,
  }) async {
    isLoading = true;
    errorMessage = null;

    final package = PackingPackageModel(
      deliveryNote: deliveryNote,
      fromCaseNo: caseNumber,
      toCaseNo: caseNumber,
      packageBarcode: cartonBarcode,
      grossWeightPkg: grossWeightPkg,
      netWeightPkg: netWeightPkg,
      length: length,
      width: width,
      height: height,
      dimensionUom: dimensionUom,
    );

    try {
      createdPackage = await fulfillmentManager.packCarton(
        package: package,
        isOnline: isOnline,
      );
      return true;
    } catch (e) {
      errorMessage = 'Failed to create Packing Slip: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
