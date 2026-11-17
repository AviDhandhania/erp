// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/delivery_handoff_model.dart';
import '../models/fulfillment_task_model.dart';
import '../services/fulfillment_manager.dart';

/// State controller for dispatch and carrier handoff verification.
class DispatchController {
  final FulfillmentManager fulfillmentManager;

  List<FulfillmentTaskModel> dispatchTasks = [];
  bool isLoading = false;
  String? errorMessage;
  DeliveryHandoffModel? recordedHandoff;

  DispatchController({required this.fulfillmentManager});

  Future<void> fetchDispatchTasks({String? warehouse, String? search}) async {
    isLoading = true;
    errorMessage = null;

    try {
      final res = await fulfillmentManager.apiService.getTasks(
        taskType: 'dispatch',
        state: 'open',
        search: search,
      );
      dispatchTasks = res.items;
    } catch (e) {
      errorMessage = 'Failed to load dispatch tasks: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Records physical carrier handoff with logistics tracking details.
  Future<bool> recordCarrierHandoff({
    required String deliveryNote,
    required String transporterName,
    required String acceptedByHandler,
    int packagesCount = 1,
    double grossWeight = 0.0,
    String? vehicleNo,
    String? lrNo,
    DateTime? lrDate,
    String? driverName,
    String? driverPhone,
    String? proofPhotoUrl,
    String? notes,
    bool isOnline = true,
  }) async {
    isLoading = true;
    errorMessage = null;

    final handoff = DeliveryHandoffModel(
      deliveryNote: deliveryNote,
      transporterName: transporterName,
      acceptedByHandler: acceptedByHandler,
      packagesCount: packagesCount,
      grossWeight: grossWeight,
      vehicleNo: vehicleNo,
      lrNo: lrNo,
      lrDate: lrDate,
      driverName: driverName,
      driverPhone: driverPhone,
      proofPhotoUrl: proofPhotoUrl,
      notes: notes,
      requestId: 'handoff-${DateTime.now().microsecondsSinceEpoch}',
    );

    try {
      recordedHandoff = await fulfillmentManager.recordHandoff(
        handoff: handoff,
        isOnline: isOnline,
      );
      // Also trigger dispatch on the delivery note
      await fulfillmentManager.dispatchDelivery(
        deliveryNote: deliveryNote,
        transporterName: transporterName,
        vehicleNo: vehicleNo,
        lrNo: lrNo,
        lrDate: lrDate?.toIso8601String().substring(0, 10),
        isOnline: isOnline,
      );
      return true;
    } catch (e) {
      errorMessage = 'Failed to record carrier handoff: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
