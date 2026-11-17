// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:typed_data';
import 'package:clothing_core/clothing_core.dart';
import 'package:test/test.dart';

void main() {
  group('Mobile Scanner Controller Tests', () {
    test('Scanner suppresses duplicate barcodes within debounce window', () async {
      final controller = MobileScannerController(
        debounceWindow: const Duration(milliseconds: 500),
        suppressDuplicates: true,
      );

      final receivedEvents = <MobileScanEvent>[];
      final subscription = controller.scanStream.listen(receivedEvents.add);

      // First scan
      controller.ingestScan('SKU-1001');
      // Rapid identical scan within debounce window
      controller.ingestScan('SKU-1001');

      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(receivedEvents.length, equals(1));
      expect(receivedEvents.first.normalizedText, equals('SKU-1001'));

      await subscription.cancel();
      controller.dispose();
    });

    test('Scanner captures keyboard wedge rapid character buffer', () async {
      final controller = MobileScannerController();
      final receivedEvents = <MobileScanEvent>[];
      final subscription = controller.scanStream.listen(receivedEvents.add);

      // Simulate fast laser scanner pulses (<10ms apart)
      for (final char in 'SKU-FAST-99\n'.split('')) {
        controller.handleRawKeyInput(char);
      }

      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(receivedEvents.length, equals(1));
      expect(receivedEvents.first.normalizedText, equals('SKU-FAST-99'));
      expect(receivedEvents.first.source, equals(ScannerSource.keyboardWedge));

      await subscription.cancel();
      controller.dispose();
    });
  });

  group('Safe Photo Manager Tests', () {
    test('SafePhotoManager computes SHA-256 and validates byte size', () async {
      final dummyBytes = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0xFF, 0xD9]);
      final evidence = await SafePhotoManager.processImageBytes(dummyBytes, fileName: 'test.jpg');

      expect(evidence.fileName, equals('test.jpg'));
      expect(evidence.mimeType, equals('image/jpeg'));
      expect(evidence.sha256Checksum, isNotEmpty);
      expect(evidence.sha256Checksum.length, equals(64));
    });

    test('SafePhotoManager rejects oversized photos > 2MB', () async {
      final oversizedBytes = Uint8List(2 * 1024 * 1024 + 1);
      expect(
        () => SafePhotoManager.processImageBytes(oversizedBytes),
        throwsA(isA<ClothingApiException>()),
      );
    });
  });
}
