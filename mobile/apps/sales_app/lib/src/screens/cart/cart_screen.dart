// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/cart_controller.dart';
import '../models/cart_order_model.dart';

/// Screen presenting the active sales cart, server repricing preflight, exposure verification,
/// and order placement.
class CartScreen {
  final CartController controller;

  const CartScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final cart = controller.cart;
    if (cart == null || cart.items.isEmpty) {
      return {
        'state': 'empty',
        'message': 'Your cart is empty. Browse catalogue to add styles.',
      };
    }

    return {
      'state': 'ready',
      'customer': cart.customer,
      'customer_name': cart.customerName,
      'territory': cart.territory,
      'delivery_date': cart.deliveryDate.toIso8601String().substring(0, 10),
      'client_request_id': cart.clientRequestId,
      'total_pieces': cart.totalPieces,
      'indicative_subtotal': cart.indicativeSubtotal,
      'items': cart.items.map((i) => {
        'template_code': i.templateCode,
        'item_name': i.itemName,
        'colour': i.colour,
        'size': i.size,
        'item_code': i.itemCode,
        'qty': i.quantity,
        'rate': i.indicativeRate,
        'line_total': i.lineTotal,
      }).toList(),
      'repricing': {
        'is_repricing': controller.isRepricing,
        'is_repriced': cart.isRepriced,
        'subtotal': cart.serverSubtotal ?? cart.indicativeSubtotal,
        'taxes': cart.serverTaxes ?? 0.0,
        'grand_total': cart.serverGrandTotal ?? cart.indicativeSubtotal,
        'approved_limit': cart.serverApprovedLimit,
        'new_total_exposure': cart.serverNewTotalExposure,
        'exceeds_limit': cart.serverExceedsLimit ?? false,
      },
      'can_submit': !controller.isRepricing &&
                    !controller.isSubmitting &&
                    (cart.serverExceedsLimit != true),
      'error_message': controller.errorMessage,
      'actions': [
        'modify_item_qty',
        'remove_item',
        'reprice_with_server',
        'submit_draft_order',
      ],
    };
  }
}
