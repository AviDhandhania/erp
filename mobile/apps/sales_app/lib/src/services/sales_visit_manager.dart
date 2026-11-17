// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:clothing_core/clothing_core.dart';
import '../models/retailer_visit_model.dart';
import '../models/conflict_model.dart';
import 'sales_api_service.dart';
import 'sales_local_cache.dart';

/// Manages field visit execution, check-in verification, photo evidence, and submission.
class SalesVisitManager {
  final SalesApiService apiService;
  final SalesLocalCache localCache;
  final OfflineMutationQueue mutationQueue;
  final SafePhotoManager photoManager;

  SalesVisitManager({
    required this.apiService,
    required this.localCache,
    required this.mutationQueue,
    required this.photoManager,
  });

  /// Processes storefront/signboard check-in photo evidence safely:
  /// - Strips dangerous EXIF & GPS metadata
  /// - Compresses under 2MB
  /// - Computes SHA-256 cryptographic digest
  Future<SafePhoto> processCheckinEvidence(File rawPhoto) async {
    return photoManager.processAndSanitize(
      sourceFile: rawPhoto,
      tag: 'visit_checkin',
    );
  }

  /// Submits completed visit report with check-in data and specialist reviews.
  Future<Map<String, dynamic>> submitVisit({
    required RetailerVisitReportModel report,
    required String requestId,
    bool isOnline = true,
  }) async {
    if (isOnline) {
      try {
        final result = await apiService.submitVisitReport(
          report,
          requestId: requestId,
        );
        return result;
      } on ClothingApiException catch (e) {
        if (e.isBusinessConflict) {
          await localCache.recordConflict(ConflictModel(
            mutationId: requestId,
            operationType: 'submit_mobile_visit',
            payload: report.toJson(),
            errorMessage: e.message,
            serverErrorCode: e.errorCode,
            failedAt: DateTime.now(),
          ));
        }
        rethrow;
      }
    } else {
      // Offline queue
      await mutationQueue.enqueue(
        id: requestId,
        endpoint: '/api/method/sales_erp.mobile_api.submit_mobile_visit',
        payload: {
          ...report.toJson(),
          'request_id': requestId,
        },
      );
      return {
        'status': 'Queued',
        'mutation_id': requestId,
        'customer': report.customer,
      };
    }
  }
}
