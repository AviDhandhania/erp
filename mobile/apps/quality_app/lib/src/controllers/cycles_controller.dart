// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/production_cycle_model.dart';
import '../services/quality_cycle_manager.dart';

/// State controller for browsing and filtering Production Quality Cycles.
class CyclesController {
  final QualityCycleManager cycleManager;

  List<ProductionCycleModel> cycles = [];
  ProductionCycleModel? selectedCycle;
  bool isLoading = false;
  String? errorMessage;
  int? selectedStageFilter;
  String? selectedSupplierFilter;

  CyclesController({required this.cycleManager});

  Future<void> fetchCycles({bool isOnline = true}) async {
    isLoading = true;
    errorMessage = null;

    try {
      cycles = await cycleManager.loadCycles(
        supplier: selectedSupplierFilter,
        isOnline: isOnline,
      );
    } catch (e) {
      errorMessage = 'Failed to load production cycles: $e';
    } finally {
      isLoading = false;
    }
  }

  void selectCycle(ProductionCycleModel cycle) {
    selectedCycle = cycle;
  }

  void filterByStage(int? stage) {
    selectedStageFilter = stage;
  }

  void filterBySupplier(String? supplier) {
    selectedSupplierFilter = supplier;
  }

  List<ProductionCycleModel> get filteredCycles {
    var result = cycles;
    if (selectedStageFilter != null) {
      result = result.where((c) => c.currentStage == selectedStageFilter).toList();
    }
    if (selectedSupplierFilter != null && selectedSupplierFilter!.isNotEmpty) {
      result = result.where((c) => c.supplier == selectedSupplierFilter).toList();
    }
    return result;
  }
}
