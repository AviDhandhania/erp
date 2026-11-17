// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:quality_app/quality_app.dart';

class MockQualityApiServiceForCycles implements QualityApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final List<ProductionCycleModel> mockCycles = [
    ProductionCycleModel(
      name: 'PQC-2026-0001',
      cycleKey: 'PQC-SUP-01-SHIRT-PO1-LOT1',
      supplier: 'SUPPLIER-ALPHA',
      itemCode: 'SHIRT-BLUE-L',
      purchaseOrder: 'PO-2026-0010',
      productionLot: 'LOT-2026-A',
      company: 'TEST Company',
      status: 'Active',
      currentStage: 4,
      currentStageName: 'Production Go Ahead',
      gateReviewStatus: 'Pending',
    ),
    ProductionCycleModel(
      name: 'PQC-2026-0002',
      cycleKey: 'PQC-SUP-01-JEANS-PO2-LOT2',
      supplier: 'SUPPLIER-ALPHA',
      itemCode: 'JEANS-SLIM-32',
      purchaseOrder: 'PO-2026-0020',
      productionLot: 'LOT-2026-B',
      company: 'TEST Company',
      status: 'Active',
      currentStage: 5,
      currentStageName: 'Inline Visits',
      gateReviewStatus: 'Approved',
    ),
  ];

  @override
  Future<List<ProductionCycleModel>> getProductionCycles({
    String? supplier,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    var result = mockCycles;
    if (supplier != null) result = result.where((c) => c.supplier == supplier).toList();
    if (status != null) result = result.where((c) => c.status == status).toList();
    return result;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Production Quality Cycle & 7-Stage Progression Tests', () {
    late QualityLocalCache localCache;
    late QualityCycleManager cycleManager;
    late MockQualityApiServiceForCycles mockApi;

    setUp(() async {
      mockApi = MockQualityApiServiceForCycles();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_quality_cycles.db',
        secureStorage: secureStorage,
      );
      localCache = QualityLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      cycleManager = QualityCycleManager(
        apiService: mockApi,
        localCache: localCache,
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('validates 7-stage quality lifecycle ordering and gate flags', () {
      expect(qualityStages.length, equals(7));
      expect(qualityStages[0], equals('First Submission — Fit Sample'));
      expect(qualityStages[1], equals('Second Submission — Refit Sample'));
      expect(qualityStages[2], equals('Size Set Submission'));
      expect(qualityStages[3], equals('Production Go Ahead'));
      expect(qualityStages[4], equals('Inline Visits'));
      expect(qualityStages[5], equals('Mid-line Visits'));
      expect(qualityStages[6], equals('Final Inspection'));

      final pgaCycle = mockApi.mockCycles[0];
      expect(pgaCycle.currentStage, equals(4));
      expect(pgaCycle.isProductionGoAheadStage, isTrue);
      expect(pgaCycle.requiresGateReview, isTrue);
      expect(cycleManager.isCycleBlockedForGate(pgaCycle), isTrue);

      final inlineCycle = mockApi.mockCycles[1];
      expect(inlineCycle.currentStage, equals(5));
      expect(inlineCycle.isProductionGoAheadStage, isFalse);
      expect(inlineCycle.requiresGateReview, isFalse);
      expect(cycleManager.isCycleBlockedForGate(inlineCycle), isFalse);
    });

    test('supports multiple visits for Inline (Stage 5) and Mid-line (Stage 6)', () {
      final inlineCycle = mockApi.mockCycles[1];

      final nextVisit1 = cycleManager.getNextVisitNumber(
        cycle: inlineCycle,
        stage: 5,
        existingVisitsCount: 0,
      );
      expect(nextVisit1, equals(1));

      final nextVisit2 = cycleManager.getNextVisitNumber(
        cycle: inlineCycle,
        stage: 5,
        existingVisitsCount: 1,
      );
      expect(nextVisit2, equals(2));

      final nextVisit3 = cycleManager.getNextVisitNumber(
        cycle: inlineCycle,
        stage: 6, // Mid-line
        existingVisitsCount: 2,
      );
      expect(nextVisit3, equals(3));

      // Single-visit stage (Fit sample)
      final fitVisit = cycleManager.getNextVisitNumber(
        cycle: inlineCycle,
        stage: 1,
        existingVisitsCount: 5,
      );
      expect(fitVisit, equals(1));
    });

    test('caches cycles in SQLCipher encrypted database and falls back offline', () async {
      // 1. Online fetch populates cache
      final onlineCycles = await cycleManager.loadCycles(isOnline: true);
      expect(onlineCycles.length, equals(2));

      // 2. Offline fetch retrieves from SQLCipher cache
      final offlineCycles = await cycleManager.loadCycles(isOnline: false);
      expect(offlineCycles.length, equals(2));
      expect(offlineCycles.first.cycleKey, equals('PQC-SUP-01-SHIRT-PO1-LOT1'));
      expect(offlineCycles.first.currentStage, equals(4));
    });
  });
}
