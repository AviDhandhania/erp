// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:warehouse_app/warehouse_app.dart';

class MockReturnsApiService implements WarehouseApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final List<Map<String, dynamic>> recordedCalls = [];

  @override
  Future<Map<String, dynamic>> recordCustomerReturn({
    required String originalDeliveryNote,
    required String itemCode,
    required double returnQty,
    required String returnReason,
    required String quarantineWarehouse,
    String? conditionOnArrival,
    List<Map<String, dynamic>>? evidencePhotos,
    String? customer,
    String? batchNo,
    String? serialNo,
  }) async {
    recordedCalls.add({
      'call': 'recordCustomerReturn',
      'originalDeliveryNote': originalDeliveryNote,
      'itemCode': itemCode,
      'returnQty': returnQty,
      'returnReason': returnReason,
      'quarantineWarehouse': quarantineWarehouse,
    });
    return {
      'success': true,
      'return_id': 'RET-2026-0005',
      'quarantine_warehouse': quarantineWarehouse,
      'status': 'Quarantined',
    };
  }

  @override
  Future<Map<String, dynamic>> completeRefurbishment({
    required String taskId,
    required String operationType,
    String? notes,
  }) async {
    recordedCalls.add({
      'call': 'completeRefurbishment',
      'taskId': taskId,
      'operationType': operationType,
    });
    return {
      'success': true,
      'task_id': taskId,
      'status': 'Awaiting Reinspection',
      'reinspection_status': 'Pending Reinspection',
    };
  }

  @override
  Future<Map<String, dynamic>> restockToSaleable({
    required String taskId,
    required String saleableWarehouse,
  }) async {
    recordedCalls.add({
      'call': 'restockToSaleable',
      'taskId': taskId,
      'saleableWarehouse': saleableWarehouse,
    });
    return {
      'success': true,
      'task_id': taskId,
      'saleable_warehouse': saleableWarehouse,
      'status': 'Restocked',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Returns Intake, Quarantine Isolation, and Refurbishment Reinspection Gate Tests', () {
    late MockReturnsApiService mockApi;
    late WarehouseLocalCache localCache;
    late ReturnsManager returnsManager;

    setUp(() async {
      mockApi = MockReturnsApiService();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_warehouse_returns.db',
        secureStorage: secureStorage,
      );
      localCache = WarehouseLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      returnsManager = ReturnsManager(
        apiService: mockApi,
        localCache: localCache,
        photoManager: SafePhotoManager(),
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('ReturnIntakeModel calculates remaining returnable quantity accurately', () {
      final intake = ReturnIntakeModel(
        returnId: 'RET-001',
        originalDeliveryNote: 'DN-2026-00088',
        itemCode: 'SHIRT-BLUE-L',
        deliveredQty: 20.0,
        previouslyReturnedQty: 5.0,
        returnQty: 3.0,
        quarantineWarehouse: 'Quarantine - North Central',
        returnReason: 'Fabric Bleeding / Stitching Defect',
      );

      expect(intake.remainingReturnableQty, equals(15.0));
      expect(intake.canReturn(3.0), isTrue);
      expect(intake.canReturn(15.0), isTrue);
      expect(intake.canReturn(16.0), isFalse); // exceeds remaining
    });

    test('submitReturn validates remaining returnable quantity and enforces quarantine warehouse', () async {
      final validIntake = ReturnIntakeModel(
        returnId: 'RET-001',
        originalDeliveryNote: 'DN-2026-00088',
        itemCode: 'SHIRT-BLUE-L',
        deliveredQty: 20.0,
        previouslyReturnedQty: 5.0,
        returnQty: 2.0,
        quarantineWarehouse: 'Quarantine - North Central',
        returnReason: 'Defective Stitching',
      );

      final res = await returnsManager.submitReturn(validIntake);
      expect(res['success'], isTrue);
      expect(res['return_id'], equals('RET-2026-0005'));
      expect(res['quarantine_warehouse'], equals('Quarantine - North Central'));

      // Attempt return exceeding deliverable qty
      final excessiveIntake = validIntake.copyWith(returnQty: 25.0);
      expect(
        () async => await returnsManager.submitReturn(excessiveIntake),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('RefurbishmentModel evaluates post-refurbishment reinspection quality gate', () {
      final pendingTask = RefurbishmentModel(
        taskId: 'REFURB-001',
        itemCode: 'SHIRT-BLUE-L',
        quantity: 2.0,
        quarantineWarehouse: 'Quarantine - North Central',
        saleableWarehouse: 'Finished Goods - North Central',
        defectDescription: 'Loose button on collar',
        operationType: 'Button / Zipper Replacement',
        status: 'In Progress',
        reinspectionStatus: 'Pending Reinspection',
      );

      // Gate: canRestock MUST be false when reinspection is Pending or Failed
      expect(pendingTask.canRestock, isFalse);

      final failedTask = pendingTask.copyWith(
        status: 'Completed',
        reinspectionStatus: 'Failed',
      );
      expect(failedTask.canRestock, isFalse);

      final passedTask = pendingTask.copyWith(
        status: 'Completed',
        reinspectionStatus: 'Passed',
      );
      expect(passedTask.canRestock, isTrue);
    });

    test('restockToSaleable blocks restocking when post-refurbishment reinspection has not Passed', () async {
      final uninspectedTask = RefurbishmentModel(
        taskId: 'REFURB-001',
        itemCode: 'SHIRT-BLUE-L',
        quantity: 2.0,
        quarantineWarehouse: 'Quarantine - North Central',
        saleableWarehouse: 'Finished Goods - North Central',
        defectDescription: 'Loose button',
        operationType: 'Button / Zipper Replacement',
        status: 'Completed',
        reinspectionStatus: 'Pending Reinspection', // Not passed yet
      );

      expect(
        () async => await returnsManager.restockToSaleable(
          task: uninspectedTask,
          saleableWarehouse: 'Finished Goods - North Central',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('restockToSaleable succeeds when post-refurbishment reinspection has Passed', () async {
      final clearedTask = RefurbishmentModel(
        taskId: 'REFURB-001',
        itemCode: 'SHIRT-BLUE-L',
        quantity: 2.0,
        quarantineWarehouse: 'Quarantine - North Central',
        saleableWarehouse: 'Finished Goods - North Central',
        defectDescription: 'Loose button',
        operationType: 'Button / Zipper Replacement',
        status: 'Completed',
        reinspectionStatus: 'Passed', // Reinspection cleared
      );

      final res = await returnsManager.restockToSaleable(
        task: clearedTask,
        saleableWarehouse: 'Finished Goods - North Central',
      );

      expect(res['success'], isTrue);
      expect(res['status'], equals('Restocked'));
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'restockToSaleable'), isTrue);
    });
  });
}
