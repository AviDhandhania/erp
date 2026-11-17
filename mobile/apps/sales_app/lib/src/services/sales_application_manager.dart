// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:clothing_core/clothing_core.dart';
import '../models/retailer_application_model.dart';
import 'sales_api_service.dart';
import 'sales_local_cache.dart';

/// Manages prospective retailer onboarding, draft persistence, private multi-photo evidence,
/// and supervisory approval lifecycle.
class SalesApplicationManager {
  final SalesApiService apiService;
  final SalesLocalCache localCache;
  final SafePhotoManager photoManager;

  SalesApplicationManager({
    required this.apiService,
    required this.localCache,
    required this.photoManager,
  });

  /// Captures and sanitizes private onboarding evidence (Storefront, GST cert, Cheque, etc.).
  Future<ApplicationEvidencePhoto> processEvidencePhoto({
    required File rawFile,
    required String photoType,
    required String caption,
  }) async {
    final safePhoto = await photoManager.processAndSanitize(
      sourceFile: rawFile,
      tag: 'retailer_application_$photoType',
    );

    return ApplicationEvidencePhoto(
      photoPathOrUrl: safePhoto.sanitizedPath,
      caption: caption,
      photoType: photoType,
      sha256Checksum: safePhoto.sha256Hash,
      fileSize: safePhoto.fileSizeBytes,
    );
  }

  /// Saves draft application locally for later resumption.
  Future<void> saveDraft(RetailerApplicationModel draft) async {
    await localCache.saveApplicationDraft(draft);
  }

  /// Retrieves all pending local drafts.
  Future<List<RetailerApplicationModel>> getSavedDrafts() async {
    return localCache.getSavedApplicationDrafts();
  }

  /// Submits draft application to RSM supervisory queue.
  Future<RetailerApplicationModel> submitToRsmQueue(
    RetailerApplicationModel application, {
    required String requestId,
  }) async {
    final submitted = await apiService.submitRetailerApplication(
      application,
      requestId: requestId,
    );
    // Delete local draft once submitted successfully
    await localCache.deleteApplicationDraft(application.clientDraftId);
    return submitted;
  }

  /// RSM commercial review action: Request More Information from ASM.
  Future<Map<String, dynamic>> requestMoreInformation({
    required String applicationName,
    required String comments,
  }) async {
    return apiService.requestMoreInfoApplication(applicationName, comments);
  }

  /// ASM action: Resubmit application after addressing RFI.
  Future<Map<String, dynamic>> resubmitApplication({
    required String applicationName,
    String? notes,
  }) async {
    return apiService.resubmitApplication(applicationName, notes: notes);
  }

  /// RSM action: Approve application with initial credit/exposure limit.
  Future<Map<String, dynamic>> approveApplication({
    required String applicationName,
    double? initialCreditLimit,
  }) async {
    return apiService.approveApplication(
      applicationName,
      initialCreditLimit: initialCreditLimit,
    );
  }

  /// RSM action: Reject application with formal justification.
  Future<Map<String, dynamic>> rejectApplication({
    required String applicationName,
    required String reason,
  }) async {
    return apiService.rejectApplication(applicationName, reason);
  }

  /// RSM action: Update commercial assessment fields.
  Future<Map<String, dynamic>> updateCommercialFields({
    required String applicationName,
    required Map<String, dynamic> updates,
  }) async {
    return apiService.updateCommercialFields(applicationName, updates);
  }
}
