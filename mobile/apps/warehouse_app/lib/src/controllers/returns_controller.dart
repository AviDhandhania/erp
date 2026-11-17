// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/return_intake_model.dart';
import '../services/returns_manager.dart';

/// State controller for customer return intake and quarantine isolation.
class ReturnsController {
  final ReturnsManager returnsManager;

  List<ReturnIntakeModel> recentReturns = [];
  bool isLoading = false;
  String? errorMessage;
  ReturnIntakeModel? currentIntake;

  ReturnsController({required this.returnsManager});

  Future<bool> processCustomerReturn({
    required String deliveryNote,
    required String itemCode,
    required int quantity,
    required String quarantineWarehouse,
    required String returnReason,
    String? serialNo,
    String? batchNo,
    List<String> photoUrls = const [],
    String? notes,
    bool isOnline = true,
  }) async {
    isLoading = true;
    errorMessage = null;

    final intake = ReturnIntakeModel(
      deliveryNote: deliveryNote,
      itemCode: itemCode,
      returnQuantity: quantity,
      quarantineWarehouse: quarantineWarehouse,
      returnReason: returnReason,
      serialNo: serialNo,
      batchNo: batchNo,
      photoUrls: photoUrls,
      notes: notes,
      requestId: 'ret-req-${DateTime.now().microsecondsSinceEpoch}',
    );

    try {
      final res = await returnsManager.intakeReturn(
        returnModel: intake,
        isOnline: isOnline,
      );
      currentIntake = res;
      recentReturns.insert(0, res);
      return true;
    } catch (e) {
      errorMessage = 'Return intake failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
