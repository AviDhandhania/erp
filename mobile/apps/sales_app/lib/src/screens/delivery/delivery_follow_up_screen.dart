// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/delivery_follow_up_controller.dart';
import '../models/delivery_follow_up_model.dart';

/// Screen managing delivery follow-up obligations, carton barcode verification, and issue escalations.
class DeliveryFollowUpScreen {
  final DeliveryFollowUpController controller;

  const DeliveryFollowUpScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? statusFilter}) {
    final list = controller.obligations;

    return {
      'state': controller.isLoading && list.isEmpty ? 'loading' : 'ready',
      'total_obligations': list.length,
      'status_filter': statusFilter ?? 'all',
      'valid_outcomes': DeliveryFollowUpModel.validOutcomes,
      'obligations': list.map((d) => {
        'id': d.id,
        'delivery_note': d.deliveryNote,
        'sales_order': d.salesOrder,
        'customer': d.customer,
        'customer_name': d.customerName,
        'territory': d.territory,
        'delivery_date': d.deliveryDate.toIso8601String().substring(0, 10),
        'carrier': d.carrier,
        'tracking_no': d.trackingNumber,
        'carton_count': d.cartonCount,
        'status': d.status,
        'is_pending': d.isPending,
        'is_satisfied': d.isSatisfied,
        'is_escalated': d.isEscalated,
        'package_barcodes': d.packageBarcodes,
        'outcome': d.followUpOutcome,
        'issue_notes': d.issueNotes,
      }).toList(),
      'actions': [
        'scan_carton_barcode',
        'record_delivery_outcome',
        'refresh',
      ],
    };
  }
}
