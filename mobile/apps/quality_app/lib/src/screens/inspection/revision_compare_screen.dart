// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/revision_controller.dart';
import '../../models/revision_comparison_model.dart';

/// Screen presenting side-by-side diff between inspection report revisions.
class RevisionCompareScreen {
  final RevisionController controller;

  const RevisionCompareScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final comparison = controller.activeComparison;

    if (comparison == null) {
      return {'state': 'empty', 'message': 'No revision comparison loaded.'};
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'original_name': comparison.originalName,
      'revision_name': comparison.revisionName,
      'original_revision': comparison.originalRevision,
      'new_revision': comparison.newRevision,
      'result_comparison': {
        'original': comparison.originalResult,
        'new': comparison.newResult,
        'has_changed': comparison.hasResultChanged,
      },
      'recommendation_comparison': {
        'original': comparison.originalRecommendation,
        'new': comparison.newRecommendation,
        'has_changed': comparison.hasRecommendationChanged,
      },
      'checklist_diffs': comparison.checklistDiffs,
      'reading_diffs': comparison.readingDiffs,
      'defect_diffs': comparison.defectDiffs,
      'new_photos_count': comparison.newPhotosCount,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'actions': [
        'request_further_corrections',
        'approve_revision',
      ],
    };
  }
}
