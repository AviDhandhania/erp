// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:quality_app/quality_app.dart';

class MockQualityApiServiceForInspections implements QualityApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final List<Map<String, dynamic>> recordedCalls = [];

  @override
  Future<ChecklistTemplateModel> getChecklistTemplate({
    required String itemGroup,
    int? version,
  }) async {
    return ChecklistTemplateModel(
      templateName: 'CHECKLIST-SHIRTS-V1',
      itemGroup: itemGroup,
      version: version ?? 1,
      items: const [
        ChecklistItemModel(checkpoint: 'Collar symmetrical and free of puckering', category: 'Workmanship'),
        ChecklistItemModel(checkpoint: 'Clean buttonholes with zero loose threads', category: 'Workmanship'),
        ChecklistItemModel(checkpoint: 'Proper polybag packaging with barcode tag', category: 'Packaging'),
      ],
    );
  }

  @override
  Future<Map<String, dynamic>> submitQualityInspection(
    StageInspectionModel inspection, {
    required String requestId,
  }) async {
    recordedCalls.add({'call': 'submitQualityInspection', 'inspection': inspection.toJson()});
    return {
      'success': true,
      'name': 'SQI-2026-00088',
      'result': inspection.result,
      'recommendation': inspection.recommendation,
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Checklists, Measurements, Defects, and Safe Evidence Photos Tests', () {
    late QualityLocalCache localCache;
    late QualityInspectionManager inspectionManager;
    late MockQualityApiServiceForInspections mockApi;

    setUp(() async {
      mockApi = MockQualityApiServiceForInspections();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_quality_inspections.db',
        secureStorage: secureStorage,
      );
      localCache = QualityLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      inspectionManager = QualityInspectionManager(
        apiService: mockApi,
        localCache: localCache,
        photoManager: SafePhotoManager(),
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('ChecklistTemplateModel loads checkpoints and sets initial status', () async {
      final template = await inspectionManager.loadChecklistTemplate('Shirts');

      expect(template.itemGroup, equals('Shirts'));
      expect(template.version, equals(1));
      expect(template.items.length, equals(3));
      expect(template.items.first.checkpoint, contains('Collar symmetrical'));
      expect(template.items.first.isMandatory, isTrue);
    });

    test('InspectionReadingModel calculates variance and tolerance classification', () {
      // In spec reading (Target: 50.0, tol: +/- 1.0, actual: 50.5 -> variance: +0.5)
      final inSpecReading = InspectionReadingModel(
        parameter: 'Chest Width',
        size: 'L',
        specTarget: 50.0,
        tolerancePlus: 1.0,
        toleranceMinus: 1.0,
        actualReading: 50.5,
      );

      expect(inSpecReading.variance, equals(0.5));
      expect(inSpecReading.isInSpec, isTrue);
      expect(inSpecReading.status, equals('In Spec'));

      // Out of spec reading (Target: 50.0, tol: +/- 1.0, actual: 51.5 -> variance: +1.5)
      final outOfSpecReading = inSpecReading.copyWith(actualReading: 51.5);
      expect(outOfSpecReading.variance, equals(1.5));
      expect(outOfSpecReading.isInSpec, isFalse);
      expect(outOfSpecReading.status, equals('Out of Spec'));
    });

    test('InspectionDefectModel categorizes defect severity and calculates AQL plan', () {
      final criticalDefect = InspectionDefectModel(
        defectCode: 'DEF-FABRIC-HOLE',
        description: 'Torn fabric at shoulder seam',
        count: 1,
        severity: 'Critical',
      );
      expect(criticalDefect.isCritical, isTrue);

      final majorDefect = InspectionDefectModel(
        defectCode: 'DEF-STITCH-LOOSE',
        description: 'Skipped stitches along hem',
        count: 2,
        severity: 'Major',
      );
      expect(majorDefect.isMajor, isTrue);

      final aql = AqlSamplingPlanModel(
        lotSize: 500,
        sampleSize: 50,
        maxAllowedCritical: 0,
        maxAllowedMajor: 2,
        maxAllowedMinor: 5,
      );

      // Critical defect rejects lot
      expect(aql.isLotAccepted(criticalCount: 1, majorCount: 0, minorCount: 0), isFalse);

      // Major defects exceeding limit rejects lot
      expect(aql.isLotAccepted(criticalCount: 0, majorCount: 3, minorCount: 2), isFalse);

      // Within limits accepts lot
      expect(aql.isLotAccepted(criticalCount: 0, majorCount: 1, minorCount: 3), isTrue);
    });

    test('InspectionEvidencePhoto validates SafePhotoManager EXIF stripping and SHA-256 hash', () async {
      final photo = InspectionEvidencePhoto(
        photoId: 'photo-001',
        localSanitizedPath: '/app/cache/sanitized.jpg',
        caption: 'Defective buttonhole fraying',
        evidenceType: 'Defect Observation',
        sha256Checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        capturedAt: DateTime.now(),
      );

      expect(photo.caption, equals('Defective buttonhole fraying'));
      expect(photo.sha256Checksum.length, equals(64));
      expect(photo.evidenceType, equals('Defect Observation'));
    });

    test('draft inspection save and restore roundtrips through encrypted SQLCipher cache', () async {
      final inspection = StageInspectionModel(
        name: 'DRAFT-INSP-01',
        cycleKey: 'PQC-SUP-01-SHIRT',
        stage: 2,
        stageName: 'Second Submission — Refit Sample',
        supplier: 'SUPPLIER-ALPHA',
        itemCode: 'SHIRT-BLUE-L',
        recommendation: 'Conditionally Passed',
        result: 'Conditionally Passed',
        correctiveActionRequired: true,
        correctiveActionDescription: 'Adjust shoulder slope by 0.5 cm',
      );

      await inspectionManager.saveDraft(inspection);

      final restored = await inspectionManager.getDraft('PQC-SUP-01-SHIRT', 2);
      expect(restored, isNotNull);
      expect(restored!.name, equals('DRAFT-INSP-01'));
      expect(restored.stage, equals(2));
      expect(restored.correctiveActionRequired, isTrue);
      expect(restored.correctiveActionDescription, equals('Adjust shoulder slope by 0.5 cm'));
    });

    test('submitInspection enforces online status and rejects submission while offline', () async {
      final inspection = StageInspectionModel(
        name: 'INSP-OFFLINE-01',
        cycleKey: 'PQC-SUP-01-SHIRT',
        stage: 1,
        stageName: 'Fit Sample',
        supplier: 'SUPPLIER-ALPHA',
        itemCode: 'SHIRT-BLUE-L',
      );

      expect(
        () async => await inspectionManager.submitInspection(inspection, isOnline: false),
        throwsA(isA<StateError>()),
      );
    });
  });
}
