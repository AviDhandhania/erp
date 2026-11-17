// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/return_quarantine_controller.dart';
import '../../models/return_quarantine_model.dart';

/// Screen presenting customer returns queue awaiting quality decisions and disposition approvals.
class ReturnQuarantineListScreen {
  final ReturnQuarantineController controller;

  const ReturnQuarantineListScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? statusFilter}) {
    var items = controller.quarantineQueue;

    if (statusFilter != null && statusFilter.isNotEmpty && statusFilter != 'All') {
      items = items.where((i) => i.qualityDecision == statusFilter).toList();
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'total_items': controller.quarantineQueue.length,
      'filtered_count': items.length,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'items': items.map((item) => {
        'name': item.name,
        'item_code': item.itemCode,
        'item_name': item.itemName,
        'customer': item.customer,
        'original_delivery_note': item.originalDeliveryNote,
        'quarantine_warehouse': item.quarantineWarehouse,
        'return_qty': item.returnQty,
        'quality_decision': item.qualityDecision,
        'recommended_disposition': item.recommendedDisposition,
        'business_approval_status': item.businessApprovalStatus,
        'reinspection_status': item.reinspectionStatus,
      }).toList(),
      'actions': [
        'select_quarantine_item',
        'filter_status',
        'refresh_queue',
      ],
    };
  }
}
