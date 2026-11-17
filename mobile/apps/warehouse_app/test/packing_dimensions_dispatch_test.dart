// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:warehouse_app/warehouse_app.dart';

class MockFulfillmentManagerForPacking extends FulfillmentManager {
  MockFulfillmentManagerForPacking({
    required super.apiService,
    required super.localCache,
  });

  bool simulateOffline = false;

  @override
  Future<Map<String, dynamic>> createPackingSlip({
    required String deliveryNote,
    required List<PackingModel> packages,
  }) async {
    if (simulateOffline) {
      throw const NetworkException(message: 'Cannot create packing slip offline');
    }
    return {
      'success': true,
      'packing_slip_id': 'PS-2026-0001',
      'cartons_count': packages.length,
      'delivery_note': deliveryNote,
    };
  }

  @override
  Future<Map<String, dynamic>> dispatchDeliveryHandoff(DeliveryHandoffModel handoff) async {
    if (simulateOffline) {
      throw const NetworkException(message: 'Dispatch blocked: offline');
    }
    if (!handoff.isComplete) {
      throw StateError('Cannot dispatch incomplete handoff: carrier, vehicle, LR, and acceptance required.');
    }
    return {
      'success': true,
      'delivery_note': handoff.deliveryNote,
      'status': 'Dispatched',
      'manifest_id': 'MNF-2026-0088',
    };
  }
}

class MockApiServiceForPacking implements WarehouseApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Packing, Package Measurements, and Carrier Dispatch Tests', () {
    late WarehouseLocalCache localCache;
    late MockFulfillmentManagerForPacking fulfillmentManager;

    setUp(() async {
      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_warehouse_packing.db',
        secureStorage: secureStorage,
      );
      localCache = WarehouseLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
      fulfillmentManager = MockFulfillmentManagerForPacking(
        apiService: MockApiServiceForPacking(),
        localCache: localCache,
      );
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('PackingModel validates required measurements (L, W, H, UOM) and weights', () {
      final incompletePackage = PackingModel(
        packageId: 'PKG-001',
        cartonBarcode: 'CARTON-BOX-001',
        packageType: 'Carton Box',
        items: [
          const PackageItemModel(itemCode: 'TSHIRT-BLK-M', qty: 10.0),
        ],
      );

      expect(incompletePackage.hasValidDimensions, isFalse);
      expect(incompletePackage.hasValidWeights, isFalse);
      expect(incompletePackage.isComplete, isFalse);

      final completePackage = incompletePackage.copyWith(
        length: 40.0,
        width: 30.0,
        height: 25.0,
        dimensionUom: 'cm',
        grossWeight: 4.5,
        netWeight: 4.0,
        weightUom: 'kg',
      );

      expect(completePackage.hasValidDimensions, isTrue);
      expect(completePackage.hasValidWeights, isTrue);
      expect(completePackage.isComplete, isTrue);
      expect(completePackage.cartonBarcode, equals('CARTON-BOX-001'));
    });

    test('createPackingSlip calls server and assigns packing slip identifier', () async {
      final pkg = PackingModel(
        packageId: 'PKG-001',
        cartonBarcode: 'CARTON-BOX-001',
        packageType: 'Carton Box',
        length: 40.0,
        width: 30.0,
        height: 25.0,
        grossWeight: 4.5,
        netWeight: 4.0,
        items: [
          const PackageItemModel(itemCode: 'TSHIRT-BLK-M', qty: 10.0),
        ],
      );

      final res = await fulfillmentManager.createPackingSlip(
        deliveryNote: 'DN-2026-00088',
        packages: [pkg],
      );

      expect(res['success'], isTrue);
      expect(res['packing_slip_id'], equals('PS-2026-0001'));
      expect(res['cartons_count'], equals(1));
    });

    test('DeliveryHandoffModel enforces complete carrier, LR, and driver details', () {
      final incompleteHandoff = DeliveryHandoffModel(
        handoffId: 'HND-001',
        deliveryNote: 'DN-2026-00088',
        carrierName: 'SafeExpress Logistics',
        vehicleNumber: '', // missing
        lrNumber: null,    // missing
        packagesCount: 3,
        isHandlerAccepted: false,
      );

      expect(incompleteHandoff.isComplete, isFalse);

      final completeHandoff = incompleteHandoff.copyWith(
        vehicleNumber: 'DL01-AB-1234',
        lrNumber: 'LR-987654321',
        driverName: 'Ramesh Singh',
        driverPhone: '+919876543210',
        proofPhotoPath: '/app/cache/proof.jpg',
        isHandlerAccepted: true,
      );

      expect(completeHandoff.isComplete, isTrue);
      expect(completeHandoff.carrierName, equals('SafeExpress Logistics'));
      expect(completeHandoff.vehicleNumber, equals('DL01-AB-1234'));
      expect(completeHandoff.lrNumber, equals('LR-987654321'));
      expect(completeHandoff.isHandlerAccepted, isTrue);
    });

    test('dispatchDeliveryHandoff blocks when offline or incomplete', () async {
      final incompleteHandoff = DeliveryHandoffModel(
        handoffId: 'HND-001',
        deliveryNote: 'DN-2026-00088',
        carrierName: 'SafeExpress Logistics',
        vehicleNumber: 'DL01-AB-1234',
        isHandlerAccepted: false, // incomplete
      );

      expect(
        () async => await fulfillmentManager.dispatchDeliveryHandoff(incompleteHandoff),
        throwsA(isA<StateError>()),
      );

      final completeHandoff = incompleteHandoff.copyWith(
        lrNumber: 'LR-12345',
        isHandlerAccepted: true,
      );

      fulfillmentManager.simulateOffline = true;
      expect(
        () async => await fulfillmentManager.dispatchDeliveryHandoff(completeHandoff),
        throwsA(isA<NetworkException>()),
      );
    });

    test('dispatchDeliveryHandoff submits successfully and produces manifest', () async {
      final completeHandoff = DeliveryHandoffModel(
        handoffId: 'HND-001',
        deliveryNote: 'DN-2026-00088',
        carrierName: 'SafeExpress Logistics',
        vehicleNumber: 'DL01-AB-1234',
        lrNumber: 'LR-12345',
        isHandlerAccepted: true,
        packagesCount: 2,
      );

      final res = await fulfillmentManager.dispatchDeliveryHandoff(completeHandoff);
      expect(res['success'], isTrue);
      expect(res['status'], equals('Dispatched'));
      expect(res['manifest_id'], equals('MNF-2026-0088'));
    });
  });
}
