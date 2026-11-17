// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/retailer_visit_model.dart';
import '../services/sales_api_service.dart';
import '../services/sales_visit_manager.dart';

/// State controller for visit obligations, execution, and geolocation check-in.
class VisitsController {
  final SalesApiService apiService;
  final SalesVisitManager visitManager;

  List<VisitObligationModel> obligations = [];
  bool isLoading = false;
  String? errorMessage;
  int currentPage = 1;
  bool hasMore = false;

  VisitsController({
    required this.apiService,
    required this.visitManager,
  });

  Future<void> fetchObligations({
    String? obligationType,
    String? status,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      obligations.clear();
    }
    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getVisitObligations(
        obligationType: obligationType,
        status: status,
        page: currentPage,
        pageSize: 20,
      );

      if (refresh) {
        obligations = res.items;
      } else {
        obligations.addAll(res.items);
      }
      hasMore = res.hasMore;
    } catch (e) {
      errorMessage = 'Failed to load visit obligations: $e';
    } finally {
      isLoading = false;
    }
  }

  Future<bool> executeAndSubmitVisit({
    required RetailerVisitReportModel report,
    bool isOnline = true,
  }) async {
    isLoading = true;
    errorMessage = null;

    final requestId = 'vis-req-${DateTime.now().microsecondsSinceEpoch}';

    try {
      await visitManager.submitVisit(
        report: report,
        requestId: requestId,
        isOnline: isOnline,
      );
      // Mark satisfied in local list if matching obligation exists
      final idx = obligations.indexWhere((o) => o.customer == report.customer);
      if (idx >= 0) {
        final obl = obligations[idx];
        obligations[idx] = VisitObligationModel(
          id: obl.id,
          obligationType: obl.obligationType,
          customer: obl.customer,
          customerName: obl.customerName,
          retailerType: obl.retailerType,
          territory: obl.territory,
          dueDate: obl.dueDate,
          status: 'Satisfied',
        );
      }
      return true;
    } catch (e) {
      errorMessage = 'Visit submission failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
