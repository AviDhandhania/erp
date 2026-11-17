// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:warehouse_app/warehouse_app.dart';

class MockPrinterApiService implements WarehouseApiService {
  @override
  ClothingApiClient get apiClient => throw UnimplementedError();

  String payloadContent = '^XA^FO50,50^ADN,36,20^FDCarton Label: CARTON-001^FS^XZ';

  @override
  Future<DocumentLabelModel> getDocumentLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'html',
  }) async {
    return DocumentLabelModel(
      doctype: doctype,
      name: name,
      labelFormat: labelFormat,
      payload: payloadContent,
      reprintCount: 0,
      timestamp: DateTime.parse('2026-11-18T00:00:00Z'),
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Safe Thermal Printer & Conflict Resolution Tests', () {
    late MockPrinterApiService mockApi;
    late PrinterService printerService;
    late PrinterController printerController;
    late WarehouseLocalCache localCache;

    setUp(() async {
      mockApi = MockPrinterApiService();
      printerService = PrinterService(apiService: mockApi);
      printerController = PrinterController(printerService: printerService);

      final secureStorage = KeyStoreSecureStorage();
      final encryptedDb = ClothingEncryptedDb(
        dbName: 'test_warehouse_conflicts.db',
        secureStorage: secureStorage,
      );
      localCache = WarehouseLocalCache(encryptedDb: encryptedDb);
      await localCache.initializeSchema();
    });

    tearDown(() async {
      await localCache.wipeAllCaches();
    });

    test('PrinterDeviceModel handles Bluetooth and Network printer profiles', () {
      final btPrinter = PrinterDeviceModel(
        deviceId: 'BT-ZEBRA-01',
        deviceName: 'Zebra ZD421 (Bay 1)',
        connectionType: 'Bluetooth',
        macAddress: '00:11:22:33:44:55',
      );
      expect(btPrinter.isBluetooth, isTrue);
      expect(btPrinter.isNetwork, isFalse);

      final netPrinter = PrinterDeviceModel(
        deviceId: 'NET-ZEBRA-02',
        deviceName: 'Zebra ZT411 (Dock)',
        connectionType: 'Network',
        ipAddress: '192.168.1.150',
        port: 9100,
      );
      expect(netPrinter.isNetwork, isTrue);
      expect(netPrinter.isBluetooth, isFalse);
    });

    test('PrinterService connects and disconnects thermal devices', () {
      final printer = PrinterDeviceModel(
        deviceId: 'BT-ZEBRA-01',
        deviceName: 'Zebra ZD421',
        connectionType: 'Bluetooth',
      );

      expect(printerController.connectedPrinter, isNull);
      printerController.connect(printer);
      expect(printerController.connectedPrinter, isNotNull);
      expect(printerController.connectedPrinter!.deviceId, equals('BT-ZEBRA-01'));
      expect(printerController.connectedPrinter!.isConnected, isTrue);

      printerController.disconnect();
      expect(printerController.connectedPrinter, isNull);
    });

    test('PrinterService prints label with reprint counter tracking', () async {
      final printer = PrinterDeviceModel(
        deviceId: 'BT-ZEBRA-01',
        deviceName: 'Zebra ZD421',
        connectionType: 'Bluetooth',
      );
      printerController.connect(printer);

      final printed = await printerController.printDocumentLabel(
        doctype: 'Pick List',
        name: 'PICK-2026-00042',
        labelFormat: 'zpl',
      );

      expect(printed, isTrue);
      expect(printerController.statusMessage, contains('Label printed successfully'));
    });

    test('PrinterService detects and rejects payloads containing sensitive credentials', () async {
      final printer = PrinterDeviceModel(
        deviceId: 'BT-ZEBRA-01',
        deviceName: 'Zebra ZD421',
        connectionType: 'Bluetooth',
      );
      printerController.connect(printer);

      // Inject prohibited credential in label payload
      mockApi.payloadContent = '^XA^FDAuthorization: Bearer secret_token_12345^FS^XZ';

      final printed = await printerController.printDocumentLabel(
        doctype: 'Pick List',
        name: 'PICK-2026-00042',
        labelFormat: 'zpl',
      );

      expect(printed, isFalse);
      expect(printerController.errorMessage, contains('SecurityException: Label payload contains sensitive credentials'));
    });

    test('WarehouseConflictModel correctly stores and manages multi-device race conflicts', () async {
      final conflict = WarehouseConflictModel(
        mutationId: 'mut-race-001',
        operationType: 'scan_barcode',
        documentReference: 'PICK-2026-00042',
        scannedBarcode: 'BARCODE-TSHIRT-BLK-M',
        errorMessage: 'Conflict: Item already picked by another terminal (User: manager-b)',
        serverErrorCode: 'CONCURRENT_PICK_ERROR',
        failedAt: DateTime.parse('2026-11-18T00:00:00Z'),
        resolutionStatus: 'Unresolved',
      );

      await localCache.recordConflict(conflict);

      final unresolved = await localCache.getUnresolvedConflicts();
      expect(unresolved.length, equals(1));
      expect(unresolved.first.mutationId, equals('mut-race-001'));
      expect(unresolved.first.serverErrorCode, equals('CONCURRENT_PICK_ERROR'));

      // Discard conflict
      await localCache.updateConflictResolution('mut-race-001', 'Discarded');
      final updated = await localCache.getUnresolvedConflicts();
      expect(updated, isEmpty);
    });
  });
}
