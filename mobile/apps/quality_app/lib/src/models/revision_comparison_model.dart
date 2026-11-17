// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Side-by-side revision comparison diff model between two inspection revisions.
@immutable
class RevisionComparisonModel {
  final String originalName;
  final String revisionName;
  final int originalRevision;
  final int newRevision;
  final String originalResult;
  final String newResult;
  final String originalRecommendation;
  final String newRecommendation;
  final List<Map<String, dynamic>> checklistDiffs;
  final List<Map<String, dynamic>> readingDiffs;
  final List<Map<String, dynamic>> defectDiffs;
  final int newPhotosCount;

  const RevisionComparisonModel({
    required this.originalName,
    required this.revisionName,
    required this.originalRevision,
    required this.newRevision,
    required this.originalResult,
    required this.newResult,
    required this.originalRecommendation,
    required this.newRecommendation,
    this.checklistDiffs = const [],
    this.readingDiffs = const [],
    this.defectDiffs = const [],
    this.newPhotosCount = 0,
  });

  bool get hasResultChanged => originalResult != newResult;
  bool get hasRecommendationChanged => originalRecommendation != newRecommendation;

  factory RevisionComparisonModel.fromJson(Map<String, dynamic> json) {
    final rawChecklists = json['checklist_diffs'] as List<dynamic>? ?? [];
    final rawReadings = json['reading_diffs'] as List<dynamic>? ?? [];
    final rawDefects = json['defect_diffs'] as List<dynamic>? ?? [];

    return RevisionComparisonModel(
      originalName: json['original_name'] as String? ?? '',
      revisionName: json['revision_name'] as String? ?? '',
      originalRevision: (json['original_revision'] as num?)?.toInt() ?? 1,
      newRevision: (json['new_revision'] as num?)?.toInt() ?? 2,
      originalResult: json['original_result'] as String? ?? '',
      newResult: json['new_result'] as String? ?? '',
      originalRecommendation: json['original_recommendation'] as String? ?? '',
      newRecommendation: json['new_recommendation'] as String? ?? '',
      checklistDiffs: rawChecklists.whereType<Map<String, dynamic>>().toList(),
      readingDiffs: rawReadings.whereType<Map<String, dynamic>>().toList(),
      defectDiffs: rawDefects.whereType<Map<String, dynamic>>().toList(),
      newPhotosCount: (json['new_photos_count'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'original_name': originalName,
    'revision_name': revisionName,
    'original_revision': originalRevision,
    'new_revision': newRevision,
    'original_result': originalResult,
    'new_result': newResult,
    'original_recommendation': originalRecommendation,
    'new_recommendation': newRecommendation,
    'checklist_diffs': checklistDiffs,
    'reading_diffs': readingDiffs,
    'defect_diffs': defectDiffs,
    'new_photos_count': newPhotosCount,
  };
}
