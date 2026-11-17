// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:clothing_core/clothing_core.dart';
import '../models/stage_inspection_model.dart';
import '../models/checklist_template_model.dart';
import '../models/inspection_reading_model.dart';
import '../models/inspection_defect_model.dart';
import '../models/inspection_evidence_photo.dart';
import '../models/revision_comparison_model.dart';
import 'quality_api_service.dart';
import 'quality_local_cache.dart';

/// Manages stage inspection execution, checklists, measurements, defects,
/// private photos via SafePhotoManager, revisions, and corrections.
class QualityInspectionManager {
  final QualityApiService apiService;
  final QualityLocalCache localCache;
  final SafePhotoManager photoManager;

  QualityInspectionManager({
    required this.apiService,
    required this.localCache,
    required this.photoManager,
  });

  /// Captures, sanitizes, and checksums an evidence photo:
  /// - Strips EXIF/GPS
  /// - Enforces 2MB size ceiling
  /// - Computes SHA-256 checksum to prevent duplicate uploads
  Future<InspectionEvidencePhoto> captureEvidencePhoto({
    required File rawPhotoFile,
    required String caption,
    String evidenceType = 'Defect Observation',
    int displayOrder = 1,
    int revision = 1,
  }) async {
    final sanitized = await photoManager.processAndSanitize(
      sourceFile: rawPhotoFile,
      tag: 'quality_evidence',
    );

    return InspectionEvidencePhoto(
      photoId: 'photo-${DateTime.now().microsecondsSinceEpoch}',
      localSanitizedPath: sanitized.sanitizedPath,
      caption: caption,
      evidenceType: evidenceType,
      sha256Checksum: sanitized.sha256Hash,
      displayOrder: displayOrder,
      revision: revision,
      capturedAt: DateTime.now(),
    );
  }

  /// Loads checklist template for garment item group.
  Future<ChecklistTemplateModel> loadChecklistTemplate(String itemGroup) async {
    try {
      final template = await apiService.getChecklistTemplate(itemGroup: itemGroup);
      await localCache.cacheChecklistTemplate(template);
      return template;
    } catch (_) {
      final cached = await localCache.getCachedChecklistTemplate(itemGroup);
      if (cached != null) return cached;
      rethrow;
    }
  }

  /// Saves in-progress inspection draft locally to encrypted SQLCipher cache.
  Future<void> saveDraft(StageInspectionModel inspection) async {
    await localCache.saveDraftInspection(inspection);
  }

  /// Restores saved draft from encrypted SQLCipher cache.
  Future<StageInspectionModel?> getDraft(String cycleKey, int stage) async {
    return localCache.getCachedDraftInspection(cycleKey, stage);
  }

  /// Submits completed stage inspection report to the server.
  Future<Map<String, dynamic>> submitInspection(
    StageInspectionModel inspection, {
    bool isOnline = true,
  }) async {
    if (!isOnline) {
      throw StateError(
        'Cannot submit quality inspection while offline. Quality decisions and stage transitions require online server validation.',
      );
    }

    final requestId = 'insp-req-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.submitQualityInspection(inspection, requestId: requestId);
  }

  /// Revises an unapproved stage inspection, maintaining immutable historical trail.
  Future<Map<String, dynamic>> reviseInspection({
    required String originalInspection,
    required List<Map<String, dynamic>> checklistItems,
    required List<Map<String, dynamic>> readings,
    required List<Map<String, dynamic>> defects,
    required List<Map<String, dynamic>> evidencePhotos,
    required String recommendation,
    required String result,
    String? revisionNotes,
  }) async {
    final requestId = 'rev-req-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.reviseQualityInspection(
      originalInspection: originalInspection,
      checklistItems: checklistItems,
      readings: readings,
      defects: defects,
      evidencePhotos: evidencePhotos,
      recommendation: recommendation,
      result: result,
      revisionNotes: revisionNotes,
      requestId: requestId,
    );
  }

  /// Fetches side-by-side comparison between inspection revisions.
  Future<RevisionComparisonModel> compareRevisions({
    required String originalName,
    required String revisionName,
  }) async {
    return apiService.compareRevisions(
      originalName: originalName,
      revisionName: revisionName,
    );
  }

  /// Requests corrections from inspector with specific guidance.
  Future<Map<String, dynamic>> requestCorrection({
    required String inspectionName,
    required String requestedCorrections,
  }) async {
    final requestId = 'corr-req-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.requestInspectionCorrection(
      inspectionName: inspectionName,
      requestedCorrections: requestedCorrections,
      requestId: requestId,
    );
  }

  /// Resubmits corrected report with resolution trail.
  Future<Map<String, dynamic>> resubmitCorrection({
    required String inspectionName,
    required String correctionNotes,
    List<Map<String, dynamic>>? updatedChecklist,
    List<Map<String, dynamic>>? updatedReadings,
    List<Map<String, dynamic>>? updatedDefects,
    List<Map<String, dynamic>>? newEvidencePhotos,
  }) async {
    final requestId = 'resub-req-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.resubmitCorrection(
      inspectionName: inspectionName,
      correctionNotes: correctionNotes,
      updatedChecklist: updatedChecklist,
      updatedReadings: updatedReadings,
      updatedDefects: updatedDefects,
      newEvidencePhotos: newEvidencePhotos,
      requestId: requestId,
    );
  }
}
