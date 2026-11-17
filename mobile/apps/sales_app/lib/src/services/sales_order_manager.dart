// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'package:clothing_core/clothing_core.dart';
import '../models/cart_order_model.dart';
import '../models/conflict_model.dart';
import 'sales_api_service.dart';
import 'sales_local_cache.dart';

/// Coordinates cart updates, server-side repricing, exposure preflight, and idempotent order placement.
///
/// Principles:
/// - Prices, discounts, taxes, and credit limit checks are NEVER calculated locally as authoritative.
/// - The client always requests server repricing & exposure preflight before placing orders.
/// - If connectivity fails, the mutation is enqueued with a unique UUID v4 idempotency key.
class SalesOrderManager {
  final SalesApiService apiService;
  final SalesLocalCache localCache;
  final OfflineMutationQueue mutationQueue;

  SalesOrderManager({
    required this.apiService,
    required this.localCache,
    required this.mutationQueue,
  });

  /// Refresh cart prices and exposure against live ERPNext controllers.
  Future<CartModel> refreshRepricingAndExposure(CartModel cart) async {
    if (cart.items.isEmpty) return cart;

    final itemPayloads = cart.items.map((i) => {
      'item_code': i.itemCode,
      'qty': i.quantity,
    }).toList();

    try {
      final res = await apiService.prepriceAndCheckExposure(
        customer: cart.customer,
        items: itemPayloads,
      );

      final repricedCart = cart.copyWith(
        serverSubtotal: (res['subtotal'] as num?)?.toDouble() ?? cart.indicativeSubtotal,
        serverTaxes: (res['total_taxes_and_charges'] as num?)?.toDouble() ?? 0.0,
        serverGrandTotal: (res['grand_total'] as num?)?.toDouble(),
        serverApprovedLimit: (res['approved_limit'] as num?)?.toDouble(),
        serverNewTotalExposure: (res['new_total_exposure'] as num?)?.toDouble(),
        serverExceedsLimit: res['exceeds_limit'] as bool? ?? false,
        isRepriced: true,
      );

      await localCache.saveActiveCart(repricedCart);
      return repricedCart;
    } catch (e) {
      // Offline fallback: keep indicative numbers, mark unrepriced
      return cart.copyWith(isRepriced: false);
    }
  }

  /// Places a draft order. Dispatches immediately if online, or queues safely into encrypted offline store.
  Future<SalesOrderModel?> placeDraftOrder({
    required CartModel cart,
    bool isOnline = true,
  }) async {
    if (cart.items.isEmpty) {
      throw ArgumentError('Cannot place an empty order.');
    }

    final itemsPayload = cart.items.map((i) => {
      'item_code': i.itemCode,
      'qty': i.quantity,
    }).toList();

    if (isOnline) {
      try {
        final order = await apiService.createOrder(
          customer: cart.customer,
          items: itemsPayload,
          requestId: cart.clientRequestId,
          deliveryDate: cart.deliveryDate,
        );
        // Clear active cart on successful order placement
        await localCache.clearActiveCart(cart.customer);
        return order;
      } on ClothingApiException catch (e) {
        if (e.isBusinessConflict) {
          // Record sync conflict for explicit user resolution
          await localCache.recordConflict(ConflictModel(
            mutationId: cart.clientRequestId,
            operationType: 'create_mobile_order',
            payload: {
              'customer': cart.customer,
              'items': itemsPayload,
              'delivery_date': cart.deliveryDate.toIso8601String().substring(0, 10),
            },
            errorMessage: e.message,
            serverErrorCode: e.errorCode,
            failedAt: DateTime.now(),
          ));
        }
        rethrow;
      }
    } else {
      // Offline: Enqueue into encrypted SQLCipher mutation queue
      await mutationQueue.enqueue(
        id: cart.clientRequestId,
        endpoint: '/api/method/sales_erp.mobile_api.create_mobile_order',
        payload: {
          'customer': cart.customer,
          'items': itemsPayload,
          'request_id': cart.clientRequestId,
          'delivery_date': cart.deliveryDate.toIso8601String().substring(0, 10),
        },
      );
      await localCache.clearActiveCart(cart.customer);
      return null;
    }
  }
}
