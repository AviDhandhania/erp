// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:quality_app/quality_app.dart';

class MockQualityApiServiceForRevisions implements QualityApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final List<Map<String, dynamic>> recordedCalls = [];

  @override
  Future<Map<String, dynamic>> reviseQualityInspection({
    required String originalInspection,
    required List<Map<String, dynamic>> checklistItems,
    required List<Map<String, dynamic>> readings,
    required List<Map<String, dynamic>> defects,
    required List<Map<String, dynamic>> evidencePhotos,
    required String recommendation,
    required String result,
    String? revisionNotes,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'reviseQualityInspection',
      'originalInspection': originalInspection,
      'result': result,
    });
    return {
      'success': true,
      'name': '$originalInspection-REV2',
      'supersedes': originalInspection,
      'revision': 2,
    };
  }

  @override
  Future<RevisionComparisonModel> compareRevisions({
    required String originalName,
    required String revisionName,
  }) async {
    return RevisionComparisonModel(
      originalName: originalName,
      revisionName: revisionName,
      originalRevision: 1,
      newRevision: 2,
      originalResult: 'Failed',
      newResult: 'Passed',
      originalRecommendation: 'Reject Lot',
      newRecommendation: 'Accept Lot',
      checklistDiffs: [
        {
          'checkpoint': 'Collar symmetry',
          'original_status': 'Failed',
          'new_status': 'Passed',
          'changed': true,
        }
      ],
      readingDiffs: [
        {
          'parameter': 'Chest Width',
          'original_actual': 51.5,
          'new_actual': 50.2,
          'original_status': 'Out of Spec',
          'new_status': 'In Spec',
        }
      ],
      defectDiffs: [
        {
          'defect_code': 'DEF-STITCH-01',
          'original_count': 3,
          'new_count': 0,
        }
      ],
      newPhotosCount: 2,
    );
  }

  @override
  Future<Map<String, dynamic>> requestInspectionCorrection({
    required String inspectionName,
    required String requestedCorrections,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'requestInspectionCorrection',
      'inspectionName': inspectionName,
      'requestedCorrections': requestedCorrections,
    });
    return {'success': true, 'status': 'Correction Requested'};
  }

  @override
  Future<Map<String, dynamic>> resubmitCorrection({
    required String inspectionName,
    required String correctionNotes,
    List<Map<String, dynamic>>? updatedChecklist,
    List<Map<String, dynamic>>? updatedReadings,
    List<Map<String, dynamic>>? updatedDefects,
    List<Map<String, dynamic>>? newEvidencePhotos,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'resubmitCorrection',
      'inspectionName': inspectionName,
      'correctionNotes': correctionNotes,
    });
    return {'success': true, 'status': 'Resubmitted'};
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Revisions, Side-by-Side Comparison, and Corrections Flow Tests', () {
    late QualityLocalCache localCache;
    late QualityInspectionManager inspectionManager;
    late RevisionController revisionController;
    late MockQualityApiServiceForRevisions mockApi;

    setUp(() async {
      mockApi = MockQualityApiServiceForRevisions();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_quality_revisions.db',
        secureStorage: secureStorage,
      );
      localCache = QualityLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      inspectionManager = QualityInspectionManager(
        apiService: mockApi,
        localCache: localCache,
        photoManager: SafePhotoManager(),
      );
      revisionController = RevisionController(
        inspectionManager: inspectionManager,
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('revises inspection and tracks superseding revision relationship', () async {
      final res = await inspectionManager.reviseInspection(
        originalInspection: 'SQI-2026-00010',
        checklistItems: [],
        readings: [],
        defects: [],
        evidencePhotos: [],
        recommendation: 'Accept Lot',
        result: 'Passed',
        revisionNotes: 'Corrected collar symmetry and resewed hem',
      );

      expect(res['success'], isTrue);
      expect(res['revision'], equals(2));
      expect(res['supersedes'], equals('SQI-2026-00010'));
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'reviseQualityInspection'), isTrue);
    });

    test('RevisionComparisonModel calculates side-by-side differences accurately', () async {
      await revisionController.loadComparison(
        originalName: 'SQI-2026-00010',
        revisionName: 'SQI-2026-00010-REV2',
      );

      final diff = revisionController.activeComparison;
      expect(diff, isNotNull);
      expect(diff!.originalRevision, equals(1));
      expect(diff.newRevision, equals(2));
      expect(diff.hasResultChanged, isTrue); // Failed -> Passed
      expect(diff.originalResult, equals('Failed'));
      expect(diff.newResult, equals('Passed'));
      expect(diff.hasRecommendationChanged, isTrue); // Reject Lot -> Accept Lot
      expect(diff.checklistDiffs.length, equals(1));
      expect(diff.readingDiffs.length, equals(1));
      expect(diff.defectDiffs.length, equals(1));
      expect(diff.newPhotosCount, equals(2));
    });

    test('Quality Manager requests corrections and Inspector resubmits correction', () async {
      // 1. Manager requests correction
      final reqSuccess = await revisionController.requestCorrection(
        inspectionName: 'SQI-2026-00010',
        requestedCorrections: 'Collar puckering observed on 3 samples; re-press and verify stitch density.',
      );
      expect(reqSuccess, isTrue);
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'requestInspectionCorrection'), isTrue);

      // 2. Inspector resubmits correction
      final resubSuccess = await revisionController.resubmitCorrection(
        inspectionName: 'SQI-2026-00010',
        correctionNotes: 'Steam pressed and verified 12 stitches per inch across entire lot.',
      );
      expect(resubSuccess, isTrue);
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'resubmitCorrection'), isTrue);
    });
  });
}
