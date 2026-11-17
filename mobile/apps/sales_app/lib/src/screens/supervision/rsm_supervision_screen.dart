// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/rsm_supervision_controller.dart';
import '../models/supervision_model.dart';

/// Screen enabling Regional Sales Managers to supervise assigned ASMs, monitor capacity guidance,
/// and process pending application/order approvals.
///
/// Security Boundary:
/// Restricted to RSMs. Zero user-management permissions.
class RsmSupervisionScreen {
  final RsmSupervisionController controller;

  const RsmSupervisionScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final overview = controller.overview;
    if (controller.isLoading && overview == null) {
      return {'state': 'loading', 'message': 'Loading supervision data...'};
    }

    if (overview == null) {
      return {'state': 'empty', 'message': 'No supervision overview available.'};
    }

    return {
      'state': 'ready',
      'rsm_user': overview.rsmUser,
      'capacity': {
        'active_asms_count': overview.activeAsmCount,
        'max_recommended_asms': overview.maxRecommendedAsms,
        'total_retailers_count': overview.totalRetailersCount,
        'max_recommended_retailers': overview.maxRecommendedRetailers,
        'is_within_capacity': overview.isWithinCapacity,
        'warning_message': overview.capacityWarningMessage,
      },
      'supervised_asms': overview.supervisedAsms.map((a) => {
        'username': a.username,
        'full_name': a.fullName,
        'territory': a.assignedTerritory,
        'retailer_count': a.activeRetailerCount,
        'pending_visits': a.pendingVisitsCount,
        'pending_orders': a.pendingOrdersCount,
      }).toList(),
      'pending_applications': {
        'count': controller.pendingApplications.length,
        'items': controller.pendingApplications.map((app) => {
          'id': app.id,
          'retailer_name': app.retailerName,
          'territory': app.territory,
          'salesperson': app.salesperson,
          'status': app.status,
        }).toList(),
      },
      'pending_orders': {
        'count': controller.pendingOrders.length,
        'items': controller.pendingOrders.map((ord) => {
          'id': ord.id,
          'customer': ord.customer,
          'customer_name': ord.customerName,
          'grand_total': ord.grandTotal,
          'total_qty': ord.totalQty,
        }).toList(),
      },
      'actions': [
        'review_application',
        'review_order',
        'refresh_supervision',
      ],
    };
  }
}
