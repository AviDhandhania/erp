// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/printer_controller.dart';
import '../../models/printer_model.dart';

/// Screen for managing safe thermal label printers (Bluetooth & Network) and label generation.
///
/// Features:
/// - Thermal printer discovery and connection status.
/// - Safe payload validation: asserts zero user passwords, tokens, or customer financial secrets.
/// - Format selection (ZPL II, HTML, PDF).
/// - Reprint tracking with tamper-evident watermark.
class PrinterScreen {
  final PrinterController controller;

  const PrinterScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final connected = controller.connectedPrinter;

    return {
      'state': controller.isScanning ? 'scanning' : (controller.isPrinting ? 'printing' : 'ready'),
      'is_scanning': controller.isScanning,
      'is_printing': controller.isPrinting,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'connected_printer': connected == null
          ? null
          : {
              'device_id': connected.deviceId,
              'device_name': connected.deviceName,
              'connection_type': connected.connectionType,
              'ip_address': connected.ipAddress,
              'mac_address': connected.macAddress,
              'is_connected': connected.isConnected,
            },
      'available_printers': controller.availablePrinters.map((p) => {
        'device_id': p.deviceId,
        'device_name': p.deviceName,
        'connection_type': p.connectionType,
        'ip_address': p.ipAddress,
        'mac_address': p.macAddress,
        'is_connected': p.deviceId == connected?.deviceId,
      }).toList(),
      'security_policy': {
        'sanitization_rule': 'Printer payloads are strictly sanitized: zero passwords, tokens, or financial secrets are permitted.',
        'reprint_policy': 'Reprints append a visible "REPRINT" watermark and increment the tamper-evident counter.',
      },
      'supported_formats': ['zpl', 'html', 'pdf'],
      'actions': [
        'scan_printers',
        'connect_printer',
        'disconnect_printer',
        'preview_label',
        'test_print_label',
      ],
    };
  }
}
