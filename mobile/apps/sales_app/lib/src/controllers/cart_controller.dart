// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/cart_order_model.dart';
import '../models/retailer_model.dart';
import '../services/sales_order_manager.dart';
import '../services/sales_local_cache.dart';

/// State controller for the active sales cart and order placement preflight.
class CartController {
  final SalesOrderManager orderManager;
  final SalesLocalCache localCache;

  CartModel? cart;
  bool isRepricing = false;
  bool isSubmitting = false;
  String? errorMessage;
  SalesOrderModel? submittedOrder;

  CartController({
    required this.orderManager,
    required this.localCache,
  });

  Future<void> initCartForRetailer(RetailerModel retailer) async {
    // Check if an existing cart was cached for this retailer
    final existing = await localCache.getActiveCart(retailer.id);
    if (existing != null) {
      cart = existing;
      await refreshPrices();
    } else {
      cart = CartModel(
        customer: retailer.id,
        customerName: retailer.customerName,
        territory: retailer.territory,
        deliveryDate: DateTime.now().add(const Duration(days: 3)),
        items: const [],
        clientRequestId: _generateUuid(),
      );
    }
  }

  void addItem({
    required String templateCode,
    required String itemName,
    required String colour,
    required String size,
    required String itemCode,
    required int quantity,
    required double indicativeRate,
  }) {
    if (cart == null) return;

    final existingIndex = cart!.items.indexWhere((i) => i.itemCode == itemCode);
    final updatedList = List<CartLineItem>.from(cart!.items);

    if (existingIndex >= 0) {
      final current = updatedList[existingIndex];
      updatedList[existingIndex] = current.copyWith(quantity: current.quantity + quantity);
    } else {
      updatedList.add(CartLineItem(
        templateCode: templateCode,
        itemName: itemName,
        colour: colour,
        size: size,
        itemCode: itemCode,
        quantity: quantity,
        indicativeRate: indicativeRate,
      ));
    }

    cart = cart!.copyWith(
      items: updatedList,
      isRepriced: false, // Invalidate server repricing on cart modification
    );
    localCache.saveActiveCart(cart!);
  }

  void updateQuantity(String itemCode, int newQty) {
    if (cart == null) return;
    final updatedList = List<CartLineItem>.from(cart!.items);
    if (newQty <= 0) {
      updatedList.removeWhere((i) => i.itemCode == itemCode);
    } else {
      final idx = updatedList.indexWhere((i) => i.itemCode == itemCode);
      if (idx >= 0) {
        updatedList[idx] = updatedList[idx].copyWith(quantity: newQty);
      }
    }
    cart = cart!.copyWith(items: updatedList, isRepriced: false);
    localCache.saveActiveCart(cart!);
  }

  Future<void> refreshPrices() async {
    if (cart == null || cart!.items.isEmpty) return;
    isRepricing = true;
    errorMessage = null;

    try {
      cart = await orderManager.refreshRepricingAndExposure(cart!);
    } catch (e) {
      errorMessage = 'Could not reprice order with server: $e';
    } finally {
      isRepricing = false;
    }
  }

  Future<bool> submitOrder({bool isOnline = true}) async {
    if (cart == null || cart!.items.isEmpty) {
      errorMessage = 'Cart is empty.';
      return false;
    }

    if (cart!.serverExceedsLimit == true) {
      errorMessage = 'Order exceeds approved stock exposure limit. Adjust quantities or request limit revision.';
      return false;
    }

    isSubmitting = true;
    errorMessage = null;

    try {
      submittedOrder = await orderManager.placeDraftOrder(
        cart: cart!,
        isOnline: isOnline,
      );
      cart = null; // Cleared on placement
      return true;
    } catch (e) {
      errorMessage = e.toString();
      return false;
    } finally {
      isSubmitting = false;
    }
  }

  String _generateUuid() {
    final now = DateTime.now().microsecondsSinceEpoch;
    return 'ord-req-$now';
  }
}
