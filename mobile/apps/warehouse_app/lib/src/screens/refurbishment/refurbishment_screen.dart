// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/refurbishment_controller.dart';
import '../../models/refurbishment_model.dart';

/// Screen presenting the refurbishment work queue, technician operations, and post-reinspection quality clearance.
///
/// Features:
/// - Refurbishment queue for items routed from return quarantine.
/// - Operation assignment (ironing, restitching, stain removal, repackaging).
/// - Refurbishment completion recording.
/// - Post-refurbishment reinspection quality gate: restock to saleable stock is BLOCKED unless reinspection has Passed.
class RefurbishmentScreen {
  final RefurbishmentController controller;

  const RefurbishmentScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? statusFilter}) {
    var filtered = controller.tasks;

    if (statusFilter != null && statusFilter.isNotEmpty && statusFilter != 'All') {
      filtered = filtered.where((t) => t.status == statusFilter).toList();
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'total_tasks': controller.tasks.length,
      'filtered_count': filtered.length,
      'is_online': controller.isOnline,
      'error_message': controller.errorMessage,
      'status_message': controller.statusMessage,
      'tasks': filtered.map((task) => {
        'task_id': task.taskId,
        'item_code': task.itemCode,
        'quantity': task.quantity,
        'defect_description': task.defectDescription,
        'operation_type': task.operationType,
        'assigned_to': task.assignedTo,
        'status': task.status,
        'reinspection_status': task.reinspectionStatus,
        'can_restock': task.canRestock,
        'restock_blocked_reason': !task.canRestock
            ? 'Restocking BLOCKED: Post-refurbishment reinspection must be "Passed" (current: ${task.reinspectionStatus}).'
            : null,
        'saleable_warehouse': task.saleableWarehouse,
        'notes': task.notes,
      }).toList(),
      'supported_operations': [
        'Restitching / Seam Repair',
        'Stain Removal / Dry Clean',
        'Steam Ironing & Folding',
        'Button / Zipper Replacement',
        'Repackaging & Retagging',
      ],
      'actions': [
        'assign_technician',
        'start_operation',
        'complete_refurbishment',
        'request_reinspection',
        'restock_to_saleable',
      ],
    };
  }
}
