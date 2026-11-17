// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:clothing_core/clothing_core.dart';
import '../models/return_quarantine_model.dart';
import '../models/inspection_evidence_photo.dart';
import 'quality_api_service.dart';
import 'quality_local_cache.dart';

/// Manages customer return quarantine inspections, two-step quality dispositions,
/// and post-refurbishment reinspection quality clearance.
class QuarantineDispositionManager {
  final QualityApiService apiService;
  final QualityLocalCache localCache;
  final SafePhotoManager photoManager;

  QuarantineDispositionManager({
    required this.apiService,
    required this.localCache,
    required this.photoManager,
  });

  /// Loads return quarantine queue, falling back to local cache if offline.
  Future<List<ReturnQuarantineModel>> loadQuarantineQueue({
    String? status,
    bool isOnline = true,
  }) async {
    if (isOnline) {
      try {
        final items = await apiService.getReturnQuarantineQueue(status: status);
        await localCache.cacheQuarantineItems(items);
        return items;
      } catch (_) {
        return localCache.getCachedQuarantineItems();
      }
    } else {
      return localCache.getCachedQuarantineItems();
    }
  }

  /// Captures defect evidence photo for return quarantine:
  /// - Strips EXIF/GPS metadata
  /// - Enforces 2MB size limit
  /// - Computes SHA-256 hash
  Future<InspectionEvidencePhoto> captureQuarantinePhoto({
    required File rawPhotoFile,
    required String caption,
  }) async {
    final sanitized = await photoManager.processAndSanitize(
      sourceFile: rawPhotoFile,
      tag: 'quarantine_defect',
    );

    return InspectionEvidencePhoto(
      photoId: 'rq-photo-${DateTime.now().microsecondsSinceEpoch}',
      localSanitizedPath: sanitized.sanitizedPath,
      caption: caption,
      evidenceType: 'Defect Observation',
      sha256Checksum: sanitized.sha256Hash,
      capturedAt: DateTime.now(),
    );
  }

  /// Inspector recommends a disposition for a defective returned garment.
  Future<Map<String, dynamic>> recommendDisposition({
    required String quarantineName,
    required String disposition, // 'Scrap' | 'Seconds Sale' | 'Supplier Claim' | 'On Hold'
    String? notes,
  }) async {
    if (!supportedDispositions.contains(disposition)) {
      throw ArgumentError('Invalid disposition: $disposition. Must be one of: $supportedDispositions');
    }

    final requestId = 'disp-rec-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.recommendReturnDisposition(
      quarantineName: quarantineName,
      disposition: disposition,
      notes: notes,
      requestId: requestId,
    );
  }

  /// Business Administrator approves or rejects the recommended disposition.
  Future<Map<String, dynamic>> approveDisposition({
    required String quarantineName,
    required String decision, // 'Approved' | 'Rejected'
    String? targetWarehouse,
    String? notes,
  }) async {
    final requestId = 'disp-app-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.approveReturnDisposition(
      quarantineName: quarantineName,
      decision: decision,
      targetWarehouse: targetWarehouse,
      notes: notes,
      requestId: requestId,
    );
  }

  /// Verifies whether a refurbished garment has passed post-refurbishment reinspection.
  bool isReinspectionCleared(ReturnQuarantineModel item) {
    return item.reinspectionStatus == 'Passed';
  }
}
