// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/dispatch_controller.dart';
import '../../models/delivery_handoff_model.dart';

/// Screen for recording carrier handoff, vehicle & LR details, proof photos, and dispatching Delivery Notes.
///
/// Features:
/// - Carrier and vehicle number capture.
/// - Lorry Receipt (LR) / consignment note recording.
/// - Handler / driver signature and private proof photo evidence via SafePhotoManager.
/// - Carrier manifest generation and native Delivery Note submission.
/// - Visibly blocks dispatch while offline.
class DispatchScreen {
  final DispatchController controller;

  const DispatchScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final handoff = controller.activeHandoff;

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'active_delivery_note': controller.activeDeliveryNote,
      'is_online': controller.isOnline,
      'error_message': controller.errorMessage,
      'status_message': controller.statusMessage,
      'handoff_details': handoff == null
          ? null
          : {
              'handoff_id': handoff.handoffId,
              'delivery_note': handoff.deliveryNote,
              'carrier_name': handoff.carrierName,
              'tracking_number': handoff.trackingNumber,
              'vehicle_number': handoff.vehicleNumber,
              'driver_name': handoff.driverName,
              'driver_phone': handoff.driverPhone,
              'packages_count': handoff.packagesCount,
              'proof_photo_path': handoff.proofPhotoPath,
              'is_handler_accepted': handoff.isHandlerAccepted,
              'is_dispatched': handoff.isDispatched,
              'is_complete': handoff.isComplete,
            },
      'can_dispatch': controller.isOnline && handoff != null && handoff.isComplete,
      'dispatch_blocked_reason': !controller.isOnline
          ? 'OFFLINE: Carrier dispatch and stock transitions are strictly blocked offline.'
          : (handoff == null || !handoff.isComplete
              ? 'Incomplete: Carrier, vehicle, LR number, and handler acceptance required.'
              : null),
      'actions': [
        'update_carrier_info',
        'capture_proof_photo',
        'confirm_handler_acceptance',
        'generate_carrier_manifest',
        'submit_dispatch',
      ],
    };
  }
}
