// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:quality_app/quality_app.dart';

class MockQualityApiServiceForGateAndQuarantine implements QualityApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final List<Map<String, dynamic>> recordedCalls = [];

  @override
  Future<GateReviewBundleModel> getProductionGoAheadBundle({required String cycleName}) async {
    return GateReviewBundleModel(
      cycleName: cycleName,
      cycleKey: 'PQC-SUP-01-SHIRT-PO1-LOT1',
      gate: 'Production Go Ahead',
      bundleHash: 'b5a2c75a4b60de321d279cf44d039f50e8f73f8a486f059f3d9f1092a543d2c1',
      supplier: 'SUPPLIER-ALPHA',
      itemCode: 'SHIRT-BLUE-L',
      purchaseOrder: 'PO-2026-0010',
      reviewedRevisions: {
        'First Submission — Fit Sample': 'SQI-2026-00001',
        'Second Submission — Refit Sample': 'SQI-2026-00002',
        'Size Set Submission': 'SQI-2026-00003',
      },
      stageSummaries: [
        {'stage': 1, 'result': 'Passed'},
        {'stage': 2, 'result': 'Passed'},
        {'stage': 3, 'result': 'Passed'},
      ],
      generatedAt: DateTime.parse('2026-11-18T00:00:00Z'),
    );
  }

  @override
  Future<Map<String, dynamic>> decideProductionGoAhead({
    required String cycleName,
    required String decision,
    required String bundleHash,
    String? notes,
    required String reauthPassword,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'decideProductionGoAhead',
      'cycleName': cycleName,
      'decision': decision,
      'bundleHash': bundleHash,
    });
    return {'success': true, 'decision': decision, 'cycle': cycleName};
  }

  @override
  Future<Map<String, dynamic>> recommendReturnDisposition({
    required String quarantineName,
    required String disposition,
    String? notes,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'recommendReturnDisposition',
      'quarantineName': quarantineName,
      'disposition': disposition,
    });
    return {'success': true, 'disposition': disposition};
  }

  @override
  Future<Map<String, dynamic>> approveReturnDisposition({
    required String quarantineName,
    required String decision,
    String? targetWarehouse,
    String? notes,
    required String requestId,
  }) async {
    recordedCalls.add({
      'call': 'approveReturnDisposition',
      'quarantineName': quarantineName,
      'decision': decision,
      'targetWarehouse': targetWarehouse,
    });
    return {'success': true, 'decision': decision};
  }

  @override
  Future<ControlledReportModel> exportQualityReportBundle({
    required String cycleName,
    String? stageReport,
  }) async {
    return ControlledReportModel(
      reportToken: 'hmac-token-valid-15m',
      cycleKey: 'PQC-SUP-01-SHIRT',
      watermarkText: 'CONFIDENTIAL - INSPECTOR avi - 2026-11-18T00:00:00Z',
      bundleHash: 'hash-abc-123',
      expiresAt: DateTime.now().add(const Duration(minutes: 15)),
      fileSizeBytes: 245000,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Gate Reviews, Return Quarantine Dispositions, and Controlled Reports Tests', () {
    late QualityLocalCache localCache;
    late GateReviewManager gateManager;
    late GateReviewController gateController;
    late QuarantineDispositionManager dispositionManager;
    late ReturnQuarantineController quarantineController;
    late ControlledReportManager reportManager;
    late MockQualityApiServiceForGateAndQuarantine mockApi;

    setUp(() async {
      mockApi = MockQualityApiServiceForGateAndQuarantine();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_quality_security.db',
        secureStorage: secureStorage,
      );
      localCache = QualityLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();

      gateManager = GateReviewManager(apiService: mockApi);
      gateController = GateReviewController(gateReviewManager: gateManager);

      dispositionManager = QuarantineDispositionManager(
        apiService: mockApi,
        localCache: localCache,
        photoManager: SafePhotoManager(),
      );
      quarantineController = ReturnQuarantineController(
        dispositionManager: dispositionManager,
      );

      reportManager = ControlledReportManager(apiService: mockApi);
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
      await reportManager.wipeAllReports();
    });

    test('Return quarantine disposition follows two-step recommendation and approval governance', () async {
      // 1. Inspector recommends disposition
      final recSuccess = await quarantineController.recommendDisposition(
        quarantineName: 'RQ-2026-0001',
        disposition: 'Scrap',
        notes: 'Unrepairable tear in main body fabric',
      );
      expect(recSuccess, isTrue);
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'recommendReturnDisposition'), isTrue);

      // 2. Business Administrator approves disposition with target scrap warehouse
      final appSuccess = await quarantineController.approveDisposition(
        quarantineName: 'RQ-2026-0001',
        decision: 'Approved',
        targetWarehouse: 'Scrap Warehouse - North',
        notes: 'Approved write-off',
      );
      expect(appSuccess, isTrue);
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'approveReturnDisposition'), isTrue);
    });

    test('Post-refurbishment reinspection clearance gate blocks restock unless Passed', () {
      final pendingItem = ReturnQuarantineModel(
        name: 'RQ-2026-0002',
        itemCode: 'SHIRT-BLUE-L',
        customer: 'Retailer Alpha',
        originalDeliveryNote: 'DN-2026-00010',
        quarantineWarehouse: 'Quarantine - North',
        returnQty: 1.0,
        reinspectionStatus: 'Pending Reinspection',
      );
      expect(dispositionManager.isReinspectionCleared(pendingItem), isFalse);

      final failedItem = ReturnQuarantineModel(
        name: 'RQ-2026-0002',
        itemCode: 'SHIRT-BLUE-L',
        customer: 'Retailer Alpha',
        originalDeliveryNote: 'DN-2026-00010',
        quarantineWarehouse: 'Quarantine - North',
        returnQty: 1.0,
        reinspectionStatus: 'Failed',
      );
      expect(dispositionManager.isReinspectionCleared(failedItem), isFalse);

      final clearedItem = ReturnQuarantineModel(
        name: 'RQ-2026-0002',
        itemCode: 'SHIRT-BLUE-L',
        customer: 'Retailer Alpha',
        originalDeliveryNote: 'DN-2026-00010',
        quarantineWarehouse: 'Quarantine - North',
        returnQty: 1.0,
        reinspectionStatus: 'Passed',
      );
      expect(dispositionManager.isReinspectionCleared(clearedItem), isTrue);
    });

    test('High-risk Administrator gate review strictly BLOCKS offline approvals', () async {
      await gateController.loadGateBundle(
        cycleName: 'PQC-2026-0001',
        gate: 'Production Go Ahead',
      );
      expect(gateController.activeBundle, isNotNull);

      // Offline approval attempt must be blocked
      final success = await gateController.commitGateDecision(
        decision: 'Approved',
        reauthPassword: 'test-only-password',
        isOnline: false, // OFFLINE
      );

      expect(success, isFalse);
      expect(gateController.errorMessage, contains('Offline: High-risk gate reviews cannot be performed offline'));
    });

    test('High-risk Administrator gate review requires strong online reauthentication', () async {
      await gateController.loadGateBundle(
        cycleName: 'PQC-2026-0001',
        gate: 'Production Go Ahead',
      );

      // Empty reauthentication credential must be blocked
      final successEmptyReauth = await gateController.commitGateDecision(
        decision: 'Approved',
        reauthPassword: '', // EMPTY
        isOnline: true,
      );
      expect(successEmptyReauth, isFalse);
      expect(gateController.errorMessage, contains('Reauthentication required'));

      // Valid reauth commits successfully online
      final successValid = await gateController.commitGateDecision(
        decision: 'Approved',
        reauthPassword: 'test-only-password',
        isOnline: true,
      );
      expect(successValid, isTrue);
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'decideProductionGoAhead'), isTrue);
    });

    test('ControlledReportModel enforces HMAC token expiry and watermark text', () async {
      final report = await reportManager.loadControlledReport(cycleName: 'PQC-2026-0001');

      expect(report.reportToken, equals('hmac-token-valid-15m'));
      expect(report.watermarkText, contains('CONFIDENTIAL'));
      expect(report.isExpired, isFalse);
      expect(reportManager.isReportValid(report), isTrue);
    });

    test('SessionLifecycleManager wipes all encrypted caches and reports on revocation', () async {
      await localCache.cacheCycles([]);
      await reportManager.loadControlledReport(cycleName: 'PQC-2026-0001');
      expect(reportManager.activeReports.length, equals(1));

      // Trigger full wipe
      await localCache.wipeAllCaches();
      await reportManager.wipeAllReports();

      expect(reportManager.activeReports, isEmpty);
      final cyclesAfterWipe = await localCache.getCachedCycles();
      expect(cyclesAfterWipe, isEmpty);
    });
  });
}
