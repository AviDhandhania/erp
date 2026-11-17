// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/printer_model.dart';
import '../services/printer_service.dart';

/// State controller for hardware/network thermal printer management and label output.
class PrinterController {
  final PrinterService printerService;

  List<PrinterDeviceModel> availablePrinters = [];
  PrinterDeviceModel? get connectedPrinter => printerService.connectedPrinter;
  bool isScanning = false;
  bool isPrinting = false;
  String? statusMessage;
  String? errorMessage;

  PrinterController({required this.printerService});

  /// Discovers nearby Bluetooth thermal printers and networked label printers.
  Future<void> scanForPrinters() async {
    isScanning = true;
    errorMessage = null;
    statusMessage = 'Searching for thermal label printers...';

    try {
      // Hardware emulation / discovery probe:
      await Future<void>.delayed(const Duration(milliseconds: 500));
      availablePrinters = [
        PrinterDeviceModel(
          deviceId: 'BT-ZEBRA-ZD421-01',
          deviceName: 'Zebra ZD421 (Warehouse Floor)',
          connectionType: 'Bluetooth',
          ipAddress: null,
          port: null,
          macAddress: '00:11:22:33:44:55',
          isConnected: false,
        ),
        PrinterDeviceModel(
          deviceId: 'NET-ZEBRA-ZT411-02',
          deviceName: 'Zebra ZT411 (Shipping Dock)',
          connectionType: 'Network',
          ipAddress: '192.168.1.150',
          port: 9100,
          macAddress: null,
          isConnected: false,
        ),
        PrinterDeviceModel(
          deviceId: 'BT-TSCDA210-03',
          deviceName: 'TSC DA210 (Returns Bay)',
          connectionType: 'Bluetooth',
          ipAddress: null,
          port: null,
          macAddress: 'AA:BB:CC:DD:EE:FF',
          isConnected: false,
        ),
      ];
      statusMessage = 'Found ${availablePrinters.length} thermal printers.';
    } catch (e) {
      errorMessage = 'Printer discovery failed: $e';
    } finally {
      isScanning = false;
    }
  }

  /// Connects to a selected printer device.
  void connect(PrinterDeviceModel device) {
    printerService.connectPrinter(device);
    statusMessage = 'Connected to ${device.deviceName}';
    errorMessage = null;
  }

  /// Disconnects from current printer.
  void disconnect() {
    printerService.disconnectPrinter();
    statusMessage = 'Printer disconnected';
  }

  /// Previews label payload in safe format (HTML / text).
  Future<DocumentLabelModel?> previewLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'html',
  }) async {
    errorMessage = null;
    try {
      return await printerService.getLabel(
        doctype: doctype,
        name: name,
        labelType: labelType,
        labelFormat: labelFormat,
      );
    } catch (e) {
      errorMessage = 'Failed to load label preview: $e';
      return null;
    }
  }

  /// Prints a document label (Pick List / Package / Carton / Delivery Note) to connected printer.
  Future<bool> printDocumentLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'zpl',
  }) async {
    if (connectedPrinter == null) {
      errorMessage = 'No printer connected. Please connect a thermal printer first.';
      return false;
    }

    isPrinting = true;
    errorMessage = null;
    statusMessage = 'Dispatching payload to ${connectedPrinter!.deviceName}...';

    try {
      final res = await printerService.printLabel(
        doctype: doctype,
        name: name,
        labelType: labelType,
        labelFormat: labelFormat,
      );

      final reprintCount = res['reprint_count'] as int? ?? 1;
      statusMessage = 'Label printed successfully. (Print #$reprintCount)';
      return true;
    } catch (e) {
      errorMessage = 'Print job failed: $e';
      return false;
    } finally {
      isPrinting = false;
    }
  }
}
