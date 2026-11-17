// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/collection_model.dart';
import '../services/sales_api_service.dart';

/// State controller for the 90–120 day overdue collection worklist.
///
/// Security & Accounting:
/// Interacts strictly with native ERPNext outstanding invoices. Never creates parallel ledgers
/// and rejects any attempt to collect or store payment secrets (CVVs, PINs, card numbers).
class CollectionsController {
  final SalesApiService apiService;

  List<CollectionInvoiceModel> invoices = [];
  bool isLoading = false;
  String? errorMessage;
  int currentPage = 1;
  bool hasMore = false;

  CollectionsController({required this.apiService});

  Future<void> fetchCollectionWorklist({
    String? customer,
    String? targetDate,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      invoices.clear();
    }
    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getCollectionWorklist(
        customer: customer,
        targetDate: targetDate,
        page: currentPage,
        pageSize: 20,
      );

      if (refresh) {
        invoices = res.items;
      } else {
        invoices.addAll(res.items);
      }
      hasMore = res.hasMore;
    } catch (e) {
      errorMessage = 'Failed to load collection worklist: $e';
    } finally {
      isLoading = false;
    }
  }

  Future<bool> recordOutcome(CollectionFollowUpOutcome outcome) async {
    if (!CollectionFollowUpOutcome.validOutcomes.contains(outcome.outcome)) {
      errorMessage = 'Invalid collection outcome.';
      return false;
    }

    isLoading = true;
    errorMessage = null;

    try {
      await apiService.recordCollectionFollowUp(outcome);
      // Update local invoice state
      final idx = invoices.indexWhere((i) => i.invoiceNo == outcome.invoiceNo);
      if (idx >= 0) {
        final current = invoices[idx];
        invoices[idx] = CollectionInvoiceModel(
          invoiceNo: current.invoiceNo,
          customer: current.customer,
          customerName: current.customerName,
          territory: current.territory,
          postingDate: current.postingDate,
          dueDate: current.dueDate,
          grandTotal: current.grandTotal,
          outstandingAmount: current.outstandingAmount,
          daysOverdue: current.daysOverdue,
          lastFollowUpOutcome: outcome.outcome,
          lastFollowUpDate: DateTime.now(),
        );
      }
      return true;
    } catch (e) {
      errorMessage = 'Failed to record follow-up: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
