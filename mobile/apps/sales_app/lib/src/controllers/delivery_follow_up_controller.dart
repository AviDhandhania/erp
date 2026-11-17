// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/delivery_follow_up_model.dart';
import '../services/sales_api_service.dart';

/// State controller for post-dispatch delivery follow-up obligations and carton barcode checks.
class DeliveryFollowUpController {
  final SalesApiService apiService;
  final MobileScannerController scannerController;

  List<DeliveryFollowUpModel> obligations = [];
  bool isLoading = false;
  String? errorMessage;
  int currentPage = 1;
  bool hasMore = false;

  DeliveryFollowUpController({
    required this.apiService,
    required this.scannerController,
  });

  Future<void> fetchObligations({
    String status = 'all',
    String? search,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      obligations.clear();
    }
    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getDeliveryFollowUps(
        status: status,
        search: search,
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
      errorMessage = 'Failed to load delivery follow-ups: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Verifies a scanned carton/package barcode against the delivery obligation's package list.
  bool verifyCartonBarcode(DeliveryFollowUpModel obligation, String scannedBarcode) {
    if (obligation.packageBarcodes.isEmpty) {
      // If no explicit carton IDs exist, check if barcode equals DN or package pattern
      return scannedBarcode.contains(obligation.deliveryNote);
    }
    return obligation.packageBarcodes.contains(scannedBarcode.trim());
  }

  Future<bool> recordFollowUpOutcome({
    required String obligationName,
    required String outcome,
    String? contactPerson,
    String? notes,
  }) async {
    if (!DeliveryFollowUpModel.validOutcomes.contains(outcome)) {
      errorMessage = 'Invalid delivery outcome.';
      return false;
    }

    isLoading = true;
    errorMessage = null;

    try {
      await apiService.recordDeliveryFollowUp(
        obligation: obligationName,
        outcome: outcome,
        contactPerson: contactPerson,
        contactDatetime: DateTime.now().toIso8601String(),
        issueNotes: notes,
      );

      final idx = obligations.indexWhere((o) => o.id == obligationName);
      if (idx >= 0) {
        final current = obligations[idx];
        obligations[idx] = DeliveryFollowUpModel(
          id: current.id,
          deliveryNote: current.deliveryNote,
          salesOrder: current.salesOrder,
          customer: current.customer,
          customerName: current.customerName,
          territory: current.territory,
          deliveryDate: current.deliveryDate,
          carrier: current.carrier,
          trackingNumber: current.trackingNumber,
          cartonCount: current.cartonCount,
          status: outcome == 'Goods Received in Full' ? 'Satisfied' : 'Escalated',
          packageBarcodes: current.packageBarcodes,
          followUpOutcome: outcome,
          issueNotes: notes,
        );
      }
      return true;
    } catch (e) {
      errorMessage = 'Failed to record delivery follow-up: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
