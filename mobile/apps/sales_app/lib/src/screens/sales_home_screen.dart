// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_design_system/clothing_design_system.dart';
import '../controllers/sales_home_controller.dart';
import '../models/sales_dashboard_model.dart';

/// Role-aware Home Dashboard screen for Area Sales Managers and Regional Sales Managers.
class SalesHomeScreen {
  final SalesHomeController controller;

  const SalesHomeScreen({required this.controller});

  /// Builds a structured view of the sales dashboard based on controller state.
  Map<String, dynamic> buildViewData() {
    final dashboard = controller.dashboard;
    if (controller.isLoading) {
      return {'state': 'loading', 'message': 'Loading sales dashboard...'};
    }

    if (controller.errorMessage != null && dashboard == null) {
      return {'state': 'error', 'error': controller.errorMessage};
    }

    if (dashboard == null) {
      return {'state': 'empty', 'message': 'No dashboard data available.'};
    }

    return {
      'state': 'ready',
      'user': dashboard.user,
      'role': dashboard.operationalRole,
      'is_rsm': dashboard.isRSM,
      'is_asm': dashboard.isASM,
      'territories': dashboard.assignedTerritories,
      'is_online': controller.isOnline,
      'cards': {
        'applications': {
          'title': 'Retailer Onboarding',
          'pending': dashboard.pendingApplications,
          'rfi': dashboard.rfiApplications,
          'approved_month': dashboard.approvedApplicationsThisMonth,
        },
        'visits': {
          'title': 'Visit Cadence',
          'completed_month': dashboard.completedVisitsThisMonth,
          'rsm_overdue': dashboard.rsmOverdueVisits,
          'rsm_grace': dashboard.rsmGraceVisits,
          'upcoming': dashboard.upcomingObligations,
        },
        'orders': {
          'title': 'Orders',
          'draft': dashboard.draftOrdersCount,
          'submitted': dashboard.submittedOrdersCount,
          'submitted_value': dashboard.submittedOrdersValue,
        },
        'exposure': {
          'title': 'Territory Retailers & Exposure',
          'retailers_count': dashboard.totalAssignedRetailers,
          'approved_limit': dashboard.totalApprovedExposureLimit,
          'current_exposure': dashboard.totalCurrentExposure,
          'over_limit_count': dashboard.retailersOverExposureLimit,
        },
        'collections': {
          'title': '90–120 Day Collections',
          'overdue_count': dashboard.overdueInvoices90To120Days,
          'overdue_amount': dashboard.totalOverdueCollectionAmount,
          'blocked_retailers': dashboard.hardBlockedRetailersCount,
        },
        'deliveries': {
          'title': 'Delivery Follow-Ups',
          'pending': dashboard.pendingDeliveryFollowUps,
          'escalated': dashboard.escalatedDeliveryFollowUps,
        },
      },
      'actions': [
        'retailers_directory',
        'new_application',
        'visit_queue',
        'catalogue_and_scanner',
        'cart_and_orders',
        'collections_worklist',
        'delivery_follow_up',
        if (dashboard.isRSM) 'rsm_supervision',
      ],
    };
  }
}
