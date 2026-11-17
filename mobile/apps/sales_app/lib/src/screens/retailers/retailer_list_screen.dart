// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/retailer_directory_controller.dart';
import '../models/retailer_model.dart';

/// Screen displaying the territory-scoped list of authorized retailers.
class RetailerListScreen {
  final RetailerDirectoryController controller;

  const RetailerListScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? search, String? group}) {
    return {
      'state': controller.isLoading && controller.retailers.isEmpty ? 'loading' : 'ready',
      'is_offline': controller.isOfflineMode,
      'search_query': search ?? '',
      'selected_group': group ?? 'All',
      'retailers_count': controller.retailers.length,
      'has_more': controller.hasMore,
      'retailers': controller.retailers.map((r) => {
        'id': r.id,
        'customer_name': r.customerName,
        'territory': r.territory,
        'operating_type': r.operatingType,
        'mobile_no': r.mobileNo,
        'cadence_status': r.cadenceStatus,
        'order_blocked': r.orderBlocked,
        'approved_limit': r.approvedExposureLimit,
        'total_exposure': r.totalExposure,
      }).toList(),
    };
  }
}
