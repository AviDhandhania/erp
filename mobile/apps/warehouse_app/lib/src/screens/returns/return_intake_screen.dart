// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/returns_controller.dart';
import '../../models/return_intake_model.dart';

/// Screen for scanning customer returns against original Delivery Notes and routing to Quarantine Warehouse.
///
/// Features:
/// - Return scan validation against original Delivery Note and Item SKU.
/// - Remaining returnable quantity check.
/// - Return reason and condition on arrival selection.
/// - Private photo evidence via SafePhotoManager.
/// - Strict routing to quarantine warehouse (isolating from saleable stock).
/// - Idempotent scan submission.
class ReturnIntakeScreen {
  final ReturnsController controller;

  const ReturnIntakeScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final activeReturn = controller.activeReturn;

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'is_online': controller.isOnline,
      'error_message': controller.errorMessage,
      'status_message': controller.statusMessage,
      'active_return': activeReturn == null
          ? null
          : {
              'return_id': activeReturn.returnId,
              'original_delivery_note': activeReturn.originalDeliveryNote,
              'item_code': activeReturn.itemCode,
              'customer': activeReturn.customer,
              'delivered_qty': activeReturn.deliveredQty,
              'previously_returned_qty': activeReturn.previouslyReturnedQty,
              'remaining_returnable_qty': activeReturn.remainingReturnableQty,
              'return_qty': activeReturn.returnQty,
              'quarantine_warehouse': activeReturn.quarantineWarehouse,
              'return_reason': activeReturn.returnReason,
              'condition_on_arrival': activeReturn.conditionOnArrival,
              'is_quarantined': activeReturn.isQuarantined,
              'photos_count': activeReturn.evidencePhotos.length,
              'evidence_photos': activeReturn.evidencePhotos.map((p) => {
                'photo_id': p.photoId,
                'caption': p.caption,
                'sha256': p.sha256Checksum,
              }).toList(),
            },
      'supported_return_reasons': [
        'Customer Defect / Damage',
        'Incorrect Size / Fit',
        'Fabric Bleeding / Stitching Defect',
        'Wrong SKU Shipped',
        'Retailer Stock Correction',
        'Transit Damage',
      ],
      'supported_conditions': [
        'Intact in Polybag',
        'Tag Attached / Unworn',
        'Damaged / Soiled',
        'Defective Stitching',
        'Customer Worn',
      ],
      'quarantine_isolation_rule': 'Returned goods are routed exclusively to quarantine warehouses. Direct restocking into saleable inventory is prohibited.',
      'actions': [
        'scan_return_barcode',
        'set_return_qty',
        'select_reason',
        'select_condition',
        'capture_evidence_photo',
        'submit_quarantine_intake',
      ],
    };
  }
}
