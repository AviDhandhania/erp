// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/return_quarantine_controller.dart';
import '../../models/return_quarantine_model.dart';

/// Screen presenting quarantine inspection, disposition recommendation, and business authorization.
class ReturnQuarantineDetailScreen {
  final ReturnQuarantineController controller;

  const ReturnQuarantineDetailScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final item = controller.selectedItem;

    if (item == null) {
      return {'state': 'empty', 'message': 'No quarantine item selected.'};
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'name': item.name,
      'item_code': item.itemCode,
      'item_name': item.itemName,
      'customer': item.customer,
      'original_delivery_note': item.originalDeliveryNote,
      'quarantine_warehouse': item.quarantineWarehouse,
      'return_qty': item.returnQty,
      'return_reason': item.returnReason,
      'quality_decision': item.qualityDecision,
      'recommended_disposition': item.recommendedDisposition,
      'inspector_notes': item.inspectorNotes,
      'business_approval_status': item.businessApprovalStatus,
      'approved_disposition': item.approvedDisposition,
      'approved_target_warehouse': item.approvedTargetWarehouse,
      'approved_by': item.approvedBy,
      'linked_supplier_claim': item.linkedSupplierClaim,
      'reinspection_status': item.reinspectionStatus,
      'is_reinspection_cleared': controller.dispositionManager.isReinspectionCleared(item),
      'supported_dispositions': supportedDispositions,
      'photos_count': item.evidencePhotos.length,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'actions': [
        'recommend_disposition',
        'approve_disposition',
        'capture_quarantine_photo',
      ],
    };
  }
}
