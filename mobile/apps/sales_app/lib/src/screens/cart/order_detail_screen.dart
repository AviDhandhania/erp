// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/cart_order_model.dart';
import '../controllers/orders_controller.dart';

/// Screen displaying order detail, workflow approval progression, and correction feedback.
class OrderDetailScreen {
  final SalesOrderModel order;
  final OrdersController controller;
  final bool isRsm;

  const OrderDetailScreen({
    required this.order,
    required this.controller,
    this.isRsm = false,
  });

  Map<String, dynamic> buildViewData() {
    return {
      'order_id': order.id,
      'customer': order.customer,
      'customer_name': order.customerName,
      'transaction_date': order.transactionDate.toIso8601String().substring(0, 10),
      'delivery_date': order.deliveryDate.toIso8601String().substring(0, 10),
      'total_qty': order.totalQty,
      'currency': order.currency,
      'grand_total': order.grandTotal,
      'docstatus': order.docstatus,
      'status': order.status,
      'is_draft': order.isDraft,
      'is_submitted': order.isSubmitted,
      'is_rejected': order.isRejected,
      'rejection_reason': order.rejectionReason,
      'amended_from': order.amendedFrom,
      'request_id': order.requestId,
      'can_rsm_approve': isRsm && order.isDraft,
      'can_rsm_reject': isRsm && order.isDraft,
      'can_asm_resubmit': !isRsm && order.isDraft && order.isRejected,
      'actions': [
        if (isRsm && order.isDraft) 'rsm_approve',
        if (isRsm && order.isDraft) 'rsm_reject',
        if (!isRsm && order.isDraft && order.isRejected) 'resubmit_corrections',
      ],
    };
  }
}
