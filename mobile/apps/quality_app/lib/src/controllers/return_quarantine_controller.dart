// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import '../models/return_quarantine_model.dart';
import '../services/quarantine_disposition_manager.dart';

/// State controller for Return Quarantine quality inspection and two-step dispositions.
class ReturnQuarantineController {
  final QuarantineDispositionManager dispositionManager;

  List<ReturnQuarantineModel> quarantineQueue = [];
  ReturnQuarantineModel? selectedItem;
  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  ReturnQuarantineController({required this.dispositionManager});

  Future<void> fetchQueue({String? status, bool isOnline = true}) async {
    isLoading = true;
    errorMessage = null;

    try {
      quarantineQueue = await dispositionManager.loadQuarantineQueue(
        status: status,
        isOnline: isOnline,
      );
    } catch (e) {
      errorMessage = 'Failed to load quarantine queue: $e';
    } finally {
      isLoading = false;
    }
  }

  void selectItem(ReturnQuarantineModel item) {
    selectedItem = item;
  }

  /// Inspector recommends a disposition.
  Future<bool> recommendDisposition({
    required String quarantineName,
    required String disposition,
    String? notes,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      await dispositionManager.recommendDisposition(
        quarantineName: quarantineName,
        disposition: disposition,
        notes: notes,
      );
      statusMessage = 'Disposition ($disposition) recommended successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Failed to recommend disposition: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Administrator approves or rejects disposition.
  Future<bool> approveDisposition({
    required String quarantineName,
    required String decision,
    String? targetWarehouse,
    String? notes,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      await dispositionManager.approveDisposition(
        quarantineName: quarantineName,
        decision: decision,
        targetWarehouse: targetWarehouse,
        notes: notes,
      );
      statusMessage = 'Disposition decision ($decision) committed successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Failed to approve disposition: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Captures defect evidence photo for return quarantine.
  Future<void> capturePhoto(File photoFile, String caption) async {
    if (selectedItem == null) return;

    try {
      final photo = await dispositionManager.captureQuarantinePhoto(
        rawPhotoFile: photoFile,
        caption: caption,
      );
      final updatedPhotos = List<dynamic>.from(selectedItem!.evidencePhotos)..add(photo);
      // Update local item
      statusMessage = 'Quarantine photo evidence captured.';
    } catch (e) {
      errorMessage = 'Photo capture failed: $e';
    }
  }
}
