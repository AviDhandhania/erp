// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/cart_order_model.dart';
import '../services/sales_api_service.dart';

/// State controller for order management, supervisory reviews, and resubmissions.
class OrdersController {
  final SalesApiService apiService;

  List<SalesOrderModel> orders = [];
  bool isLoading = false;
  String? errorMessage;
  int currentPage = 1;
  bool hasMore = false;
  String currentFilter = 'all';

  OrdersController({required this.apiService});

  Future<void> fetchOrders({
    String state = 'all',
    String? search,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      orders.clear();
    }
    currentFilter = state;
    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getOrders(
        search: search,
        state: state,
        page: currentPage,
        pageSize: 20,
      );

      if (refresh) {
        orders = res.items;
      } else {
        orders.addAll(res.items);
      }
      hasMore = res.hasMore;
    } catch (e) {
      errorMessage = 'Failed to load orders: $e';
    } finally {
      isLoading = false;
    }
  }

  /// RSM Action: Approve/submit draft order to ERPNext native Sales Order controller.
  Future<bool> approveAndSubmitOrder(String orderName) async {
    isLoading = true;
    errorMessage = null;
    try {
      final updated = await apiService.submitOrder(orderName);
      final idx = orders.indexWhere((o) => o.id == orderName);
      if (idx >= 0) {
        orders[idx] = updated;
      }
      return true;
    } catch (e) {
      errorMessage = 'Approval failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// RSM Action: Reject draft order and send back to ASM with formal reasons.
  Future<bool> rejectOrder(String orderName, String reason) async {
    isLoading = true;
    errorMessage = null;
    try {
      final updated = await apiService.rejectOrder(orderName, reason);
      final idx = orders.indexWhere((o) => o.id == orderName);
      if (idx >= 0) {
        orders[idx] = updated;
      }
      return true;
    } catch (e) {
      errorMessage = 'Rejection failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// ASM Action: Resubmit draft order after corrections.
  Future<bool> resubmitCorrectedOrder(String orderName, {String? notes}) async {
    isLoading = true;
    errorMessage = null;
    try {
      final updated = await apiService.resubmitOrder(orderName, notes: notes);
      final idx = orders.indexWhere((o) => o.id == orderName);
      if (idx >= 0) {
        orders[idx] = updated;
      }
      return true;
    } catch (e) {
      errorMessage = 'Resubmission failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
