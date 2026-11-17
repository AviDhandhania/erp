// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/picking_controller.dart';
import '../../models/fulfillment_task_model.dart';

/// Screen presenting the warehouse Pick List queue.
///
/// Features:
/// - Bounded search and filtering by wave or status.
/// - Warehouse-scoped Pick Lists only.
/// - Remaining item count and progress.
class PickListScreen {
  final PickingController controller;
  final List<FulfillmentTaskModel> tasks;

  const PickListScreen({
    required this.controller,
    required this.tasks,
  });

  Map<String, dynamic> buildViewData({String? searchQuery, String? statusFilter}) {
    var filtered = tasks;

    if (searchQuery != null && searchQuery.isNotEmpty) {
      filtered = filtered.where((t) =>
        t.name.toLowerCase().contains(searchQuery.toLowerCase()) ||
        (t.referenceDoc ?? '').toLowerCase().contains(searchQuery.toLowerCase()) ||
        (t.wave ?? '').toLowerCase().contains(searchQuery.toLowerCase())
      ).toList();
    }

    if (statusFilter != null && statusFilter.isNotEmpty && statusFilter != 'All') {
      filtered = filtered.where((t) => t.status == statusFilter).toList();
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'total_tasks': tasks.length,
      'filtered_count': filtered.length,
      'active_pick_list': controller.activePickList,
      'is_online': controller.isOnline,
      'tasks': filtered.map((t) => {
        'name': t.name,
        'warehouse': t.warehouse,
        'status': t.status,
        'total_items': t.totalItems,
        'picked_items': t.pickedItems,
        'remaining_items': t.remainingItems,
        'is_complete': t.isComplete,
        'reference_doc': t.referenceDoc,
        'wave': t.wave,
      }).toList(),
    };
  }
}
