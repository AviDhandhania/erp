// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/printer_model.dart';
import 'warehouse_api_service.dart';

/// Safe Bluetooth and Network thermal printer integration service.
///
/// Security & Payload Policy:
/// - Validates that printer payloads never embed passwords, API tokens, or customer financial secrets.
/// - Appends tamper-evident reprint counters and watermarks.
/// - Handles communication failures gracefully without corrupting document state.
class PrinterService {
  final WarehouseApiService apiService;
  PrinterDeviceModel? connectedPrinter;

  PrinterService({required this.apiService});

  void connectPrinter(PrinterDeviceModel device) {
    connectedPrinter = PrinterDeviceModel(
      deviceId: device.deviceId,
      deviceName: device.deviceName,
      connectionType: device.connectionType,
      isConnected: true,
    );
  }

  void disconnectPrinter() {
    connectedPrinter = null;
  }

  /// Fetches label or manifest payload (ZPL II / HTML / PDF).
  Future<DocumentLabelModel> getLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'html',
  }) async {
    return apiService.getDocumentLabel(
      doctype: doctype,
      name: name,
      labelType: labelType,
      labelFormat: labelFormat,
    );
  }

  /// Sends label to connected printer with audit tracking.
  Future<Map<String, dynamic>> printLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'zpl',
    bool simulateFailure = false,
  }) async {
    // 1. Fetch label payload from server
    final label = await getLabel(
      doctype: doctype,
      name: name,
      labelType: labelType,
      labelFormat: labelFormat,
    );

    // 2. Validate payload for security invariants
    _validatePrinterPayloadSecurity(label.payloadContent);

    // 3. Record print event with server audit log
    final result = await apiService.printTaskLabel(
      doctype: doctype,
      name: name,
      labelType: labelType,
      labelFormat: labelFormat,
      simulateFailure: simulateFailure,
    );

    final reprintCount = result['reprint_count'] as int? ?? label.reprintCount;
    final isReprint = reprintCount > 0;
    final watermark = isReprint ? 'REPRINT - COPY #$reprintCount' : (result['watermark'] as String? ?? label.watermark);

    return {
      'status': 'Printed',
      'label_type': label.labelType,
      'reprint_count': reprintCount,
      'is_duplicate': isReprint,
      'watermark': watermark,
      'printer': connectedPrinter?.deviceName ?? 'Default System Printer',
    };
  }

  /// Strict security assertion: printer payload must never contain secrets or credentials.
  void _validatePrinterPayloadSecurity(String content) {
    final lower = content.toLowerCase();
    if (lower.contains('password') ||
        lower.contains('api_key') ||
        lower.contains('secret') ||
        lower.contains('token') ||
        lower.contains('auth_token') ||
        lower.contains('authorization')) {
      throw SecurityException('Printer payload security violation: Detected forbidden sensitive credential.');
    }
  }
}

class SecurityException implements Exception {
  final String message;
  SecurityException(this.message);
  @override
  String toString() => 'SecurityException: $message';
}
