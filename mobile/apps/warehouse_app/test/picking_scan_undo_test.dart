// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:warehouse_app/warehouse_app.dart';

// Fake WarehouseApiService for testing
class MockWarehouseApiService implements WarehouseApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  final Map<String, dynamic> verifyScanResponses = {};
  final List<Map<String, dynamic>> recordedCalls = [];
  bool simulateOffline = false;

  @override
  Future<Map<String, dynamic>> verifyScan({
    required String barcode,
    required String pickList,
    required String locationId,
    int quantity = 1,
  }) async {
    if (simulateOffline) {
      throw const NetworkException(message: 'Connection refused: offline');
    }
    recordedCalls.add({
      'call': 'verifyScan',
      'barcode': barcode,
      'pickList': pickList,
      'locationId': locationId,
      'quantity': quantity,
    });
    return verifyScanResponses[barcode] ?? {
      'valid': true,
      'item_code': 'TSHIRT-BLK-M',
      'location_id': locationId,
      'picked_qty': quantity,
      'remaining_qty': 0,
      'batch_no': null,
      'serial_no': null,
    };
  }

  @override
  Future<Map<String, dynamic>> completePickList({
    required String pickList,
    String? warehouse,
  }) async {
    if (simulateOffline) {
      throw const NetworkException(message: 'Offline: cannot submit');
    }
    recordedCalls.add({'call': 'completePickList', 'pickList': pickList});
    return {'success': true, 'name': pickList, 'status': 'Completed'};
  }

  @override
  Future<Map<String, dynamic>> splitShortage({
    required String pickList,
    required String locationId,
    required double unpickedQty,
    String resolution = 'backorder',
  }) async {
    recordedCalls.add({
      'call': 'splitShortage',
      'pickList': pickList,
      'locationId': locationId,
      'unpickedQty': unpickedQty,
      'resolution': resolution,
    });
    return {'success': true, 'backorder_created': true, 'shortage_qty': unpickedQty};
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Pick List, Barcode Scanning, Undo, and Shortage Split Tests', () {
    late MockWarehouseApiService mockApi;
    late WarehouseLocalCache localCache;
    late FulfillmentManager fulfillmentManager;

    setUp(() async {
      mockApi = MockWarehouseApiService();
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_warehouse_picking.db',
        secureStorage: secureStorage,
      );
      localCache = WarehouseLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      fulfillmentManager = FulfillmentManager(
        apiService: mockApi,
        localCache: localCache,
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('PickItemModel correctly calculates remainingQty and isPicked', () {
      final item = PickItemModel(
        locationId: 'LOC-001',
        itemCode: 'JEANS-SLIM-32',
        itemName: 'Slim Fit Denim 32',
        warehouse: 'Finished Goods - North Central',
        qty: 5.0,
        pickedQty: 3.0,
        batchNo: 'BATCH-2026-A',
      );

      expect(item.remainingQty, equals(2.0));
      expect(item.isPicked, isFalse);

      final fullyPicked = item.copyWith(pickedQty: 5.0);
      expect(fullyPicked.remainingQty, equals(0.0));
      expect(fullyPicked.isPicked, isTrue);
    });

    test('FulfillmentTaskModel correctly tracks wave, total items, and progress', () {
      final task = FulfillmentTaskModel(
        name: 'PICK-2026-00042',
        warehouse: 'Finished Goods - North Central',
        status: 'Open',
        totalItems: 10,
        pickedItems: 7,
        wave: 'WAVE-MORNING-01',
        referenceDoc: 'SO-2026-00100',
      );

      expect(task.remainingItems, equals(3));
      expect(task.isComplete, isFalse);
    });

    test('Hardware keyboard-wedge burst timing (<50ms) processes scan stream accurately', () async {
      final scanner = MobileScannerController(
        debounceWindow: const Duration(milliseconds: 50),
        suppressDuplicates: true,
      );

      final receivedScans = <String>[];
      final sub = scanner.scanStream.listen(receivedScans.add);

      // Simulate keyboard wedge typing burst (<50ms inter-character)
      await scanner.handleHardwareWedgeBurst('BARCODE-TSHIRT-BLK-M\n');
      await Future<void>.delayed(const Duration(milliseconds: 60));

      expect(receivedScans, contains('BARCODE-TSHIRT-BLK-M'));
      await sub.cancel();
    });

    test('Online scan increments picked quantity and records undo entry', () async {
      final result = await fulfillmentManager.recordScan(
        pickList: 'PICK-2026-00042',
        locationId: 'LOC-001',
        barcode: 'BARCODE-TSHIRT-BLK-M',
        quantity: 1,
      );

      expect(result['success'], isTrue);
      expect(result['item_code'], equals('TSHIRT-BLK-M'));
      expect(fulfillmentManager.undoStack.length, equals(1));
      expect(fulfillmentManager.undoStack.first['barcode'], equals('BARCODE-TSHIRT-BLK-M'));
    });

    test('Undo unsubmitted scan reverts the last scan action successfully', () async {
      await fulfillmentManager.recordScan(
        pickList: 'PICK-2026-00042',
        locationId: 'LOC-001',
        barcode: 'BARCODE-TSHIRT-BLK-M',
        quantity: 1,
      );
      expect(fulfillmentManager.undoStack.length, equals(1));

      final undone = await fulfillmentManager.undoLastScan('PICK-2026-00042');
      expect(undone, isNotNull);
      expect(undone!['barcode'], equals('BARCODE-TSHIRT-BLK-M'));
      expect(fulfillmentManager.undoStack, isEmpty);
    });

    test('Shortage split calls native split and generates backorder record', () async {
      final res = await fulfillmentManager.splitShortage(
        pickList: 'PICK-2026-00042',
        locationId: 'LOC-001',
        unpickedQty: 2.0,
        resolution: 'backorder',
      );

      expect(res['success'], isTrue);
      expect(res['backorder_created'], isTrue);
      expect(res['shortage_qty'], equals(2.0));
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'splitShortage'), isTrue);
    });

    test('completePickList asserts online and blocks when pending offline scans exist', () async {
      // Record offline scan without reconciliation
      await localCache.recordOfflineScan(
        id: 'scan-offline-1',
        pickList: 'PICK-2026-00042',
        locationId: 'LOC-001',
        barcode: 'BARCODE-OFFLINE-01',
      );

      expect(
        () async => await fulfillmentManager.completePickList('PICK-2026-00042'),
        throwsA(isA<StateError>()),
      );
    });

    test('completePickList succeeds online when all scans are reconciled', () async {
      final res = await fulfillmentManager.completePickList('PICK-2026-00042');
      expect(res['success'], isTrue);
      expect(res['status'], equals('Completed'));
      expect(mockApi.recordedCalls.any((c) => c['call'] == 'completePickList'), isTrue);
    });
  });
}
