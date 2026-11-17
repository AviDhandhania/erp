// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/supervision_model.dart';
import '../models/retailer_application_model.dart';
import '../models/cart_order_model.dart';
import '../services/sales_api_service.dart';
import '../services/sales_application_manager.dart';

/// State controller for Regional Sales Manager (RSM) supervision of assigned ASMs and pending approvals.
///
/// Security Boundary:
/// Restricted to RSM and Administrator roles. Has zero user-management authority.
class RsmSupervisionController {
  final SalesApiService apiService;
  final SalesApplicationManager applicationManager;

  RsmSupervisionOverviewModel? overview;
  List<RetailerApplicationModel> pendingApplications = [];
  List<SalesOrderModel> pendingOrders = [];
  bool isLoading = false;
  String? errorMessage;

  RsmSupervisionController({
    required this.apiService,
    required this.applicationManager,
  });

  Future<void> fetchSupervisionData() async {
    isLoading = true;
    errorMessage = null;

    try {
      overview = await apiService.getRsmSupervisionOverview();

      // Fetch pending application reviews
      final appRes = await apiService.getApplicationQueue(queueType: 'pending', pageSize: 50);
      pendingApplications = appRes.items;

      // Fetch pending order approvals
      final orderRes = await apiService.getOrders(state: 'draft', pageSize: 50);
      pendingOrders = orderRes.items;
    } catch (e) {
      errorMessage = 'Failed to load supervision overview: $e';
    } finally {
      isLoading = false;
    }
  }

  /// RSM Action: Approve retailer application with proposed initial limit.
  Future<bool> approveApplication(String applicationName, {double? initialCreditLimit}) async {
    isLoading = true;
    errorMessage = null;
    try {
      await applicationManager.approveApplication(
        applicationName: applicationName,
        initialCreditLimit: initialCreditLimit,
      );
      pendingApplications.removeWhere((a) => a.id == applicationName);
      return true;
    } catch (e) {
      errorMessage = 'Failed to approve application: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// RSM Action: Request more information from responsible ASM.
  Future<bool> requestMoreInfo(String applicationName, String comments) async {
    isLoading = true;
    errorMessage = null;
    try {
      await applicationManager.requestMoreInformation(
        applicationName: applicationName,
        comments: comments,
      );
      pendingApplications.removeWhere((a) => a.id == applicationName);
      return true;
    } catch (e) {
      errorMessage = 'Failed to request info: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// RSM Action: Reject retailer application.
  Future<bool> rejectApplication(String applicationName, String reason) async {
    isLoading = true;
    errorMessage = null;
    try {
      await applicationManager.rejectApplication(
        applicationName: applicationName,
        reason: reason,
      );
      pendingApplications.removeWhere((a) => a.id == applicationName);
      return true;
    } catch (e) {
      errorMessage = 'Failed to reject application: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
