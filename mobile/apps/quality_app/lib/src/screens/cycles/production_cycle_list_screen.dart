// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/cycles_controller.dart';
import '../../models/production_cycle_model.dart';

/// Screen presenting the Production Quality Cycles queue with stage and supplier filters.
class ProductionCycleListScreen {
  final CyclesController controller;

  const ProductionCycleListScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? searchQuery}) {
    var items = controller.filteredCycles;

    if (searchQuery != null && searchQuery.isNotEmpty) {
      final q = searchQuery.toLowerCase();
      items = items.where((c) =>
        c.cycleKey.toLowerCase().contains(q) ||
        c.itemCode.toLowerCase().contains(q) ||
        (c.purchaseOrder ?? '').toLowerCase().contains(q) ||
        (c.productionLot ?? '').toLowerCase().contains(q) ||
        c.supplier.toLowerCase().contains(q)
      ).toList();
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'total_cycles': controller.cycles.length,
      'filtered_count': items.length,
      'selected_stage_filter': controller.selectedStageFilter,
      'selected_supplier_filter': controller.selectedSupplierFilter,
      'stages_list': qualityStages,
      'error_message': controller.errorMessage,
      'cycles': items.map((c) => {
        'name': c.name,
        'cycle_key': c.cycleKey,
        'supplier': c.supplier,
        'item_code': c.itemCode,
        'item_name': c.itemName,
        'purchase_order': c.purchaseOrder,
        'production_lot': c.productionLot,
        'current_stage': c.currentStage,
        'current_stage_name': c.currentStageName,
        'status': c.status,
        'gate_review_status': c.gateReviewStatus,
        'requires_gate_review': c.requiresGateReview,
      }).toList(),
      'actions': [
        'select_cycle',
        'filter_stage',
        'filter_supplier',
        'search_cycles',
      ],
    };
  }
}
