// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/revision_comparison_model.dart';
import '../services/quality_inspection_manager.dart';

/// State controller for revision comparison diffs, correction requests, and resubmission.
class RevisionController {
  final QualityInspectionManager inspectionManager;

  RevisionComparisonModel? activeComparison;
  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  RevisionController({required this.inspectionManager});

  /// Loads side-by-side comparison between original and revised inspection.
  Future<void> loadComparison({
    required String originalName,
    required String revisionName,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      activeComparison = await inspectionManager.compareRevisions(
        originalName: originalName,
        revisionName: revisionName,
      );
    } catch (e) {
      errorMessage = 'Failed to load revision comparison: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Requests corrections on an inspection report.
  Future<bool> requestCorrection({
    required String inspectionName,
    required String requestedCorrections,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      await inspectionManager.requestCorrection(
        inspectionName: inspectionName,
        requestedCorrections: requestedCorrections,
      );
      statusMessage = 'Correction requested successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Failed to request correction: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  /// Resubmits corrected inspection report.
  Future<bool> resubmitCorrection({
    required String inspectionName,
    required String correctionNotes,
    List<Map<String, dynamic>>? updatedChecklist,
    List<Map<String, dynamic>>? updatedReadings,
    List<Map<String, dynamic>>? updatedDefects,
    List<Map<String, dynamic>>? newEvidencePhotos,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      await inspectionManager.resubmitCorrection(
        inspectionName: inspectionName,
        correctionNotes: correctionNotes,
        updatedChecklist: updatedChecklist,
        updatedReadings: updatedReadings,
        updatedDefects: updatedDefects,
        newEvidencePhotos: newEvidencePhotos,
      );
      statusMessage = 'Correction resubmitted successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Resubmission failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
