// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/sales_dashboard_model.dart';
import '../services/sales_api_service.dart';

/// State controller for the ASM/RSM Home Dashboard.
class SalesHomeController {
  final SalesApiService apiService;
  final SessionLifecycleManager sessionLifecycle;

  SalesDashboardModel? dashboard;
  bool isLoading = false;
  String? errorMessage;
  bool isOnline = true;

  SalesHomeController({
    required this.apiService,
    required this.sessionLifecycle,
  });

  /// Loads home dashboard and enforces role authorization.
  /// Rejects unauthorized roles and wipes session immediately.
  Future<void> loadDashboard() async {
    isLoading = true;
    errorMessage = null;

    try {
      final boot = await apiService.getMobileBoot();
      final role = boot['role'] as String? ?? '';

      // Strict role check: must be ASM, RSM, or Business Admin
      final isAuthorized = role.contains('Sales') || role.contains('ASM') || role.contains('RSM') || role.contains('Admin');
      if (!isAuthorized) {
        await sessionLifecycle.wipeSessionAndCache();
        throw ClothingApiException(
          message: 'Access denied: User does not possess an authorized Clothing ERP Sales role.',
          statusCode: 403,
          errorCode: 'ROLE_REVOKED',
        );
      }

      dashboard = await apiService.getOperationalDashboard();
      isOnline = true;
    } on ClothingApiException catch (e) {
      errorMessage = e.message;
      if (e.isSessionRevoked) {
        await sessionLifecycle.wipeSessionAndCache();
      }
    } catch (e) {
      errorMessage = 'Network connection unavailable. Operating in offline mode.';
      isOnline = false;
    } finally {
      isLoading = false;
    }
  }
}
