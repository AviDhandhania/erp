// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Thermal label format and printer connection configuration.
///
/// Security & Privacy:
/// Printer payloads must never embed user passwords, API credentials, or customer PII.
@immutable
class PrinterDeviceModel {
  final String deviceId; // MAC address or IP address
  final String deviceName;
  final String connectionType; // 'bluetooth' | 'network' | 'usb'
  final bool isConnected;

  const PrinterDeviceModel({
    required this.deviceId,
    required this.deviceName,
    required this.connectionType,
    this.isConnected = false,
  });

  Map<String, dynamic> toJson() => {
    'device_id': deviceId,
    'device_name': deviceName,
    'connection_type': connectionType,
    'is_connected': isConnected,
  };
}

/// Printable document label payload including ZPL II commands, HTML preview, and reprint watermark.
@immutable
class DocumentLabelModel {
  static const validLabelTypes = <String>[
    'Pick Slip',
    'Shipping Carton',
    'Delivery Manifest',
    'Return Quarantine Tag',
    'Refurbishment Work Ticket',
  ];

  final String documentType; // 'Pick List' | 'Delivery Note' | 'Delivery Handoff' | 'Return Quarantine'
  final String documentName;
  final String labelType;
  final String labelFormat; // 'zpl' | 'pdf' | 'html'
  final String payloadContent; // ZPL II script or HTML markup
  final int reprintCount;
  final String? watermark;
  final String? printedBy;
  final DateTime? printedAt;

  const DocumentLabelModel({
    required this.documentType,
    required this.documentName,
    required this.labelType,
    this.labelFormat = 'html',
    required this.payloadContent,
    this.reprintCount = 0,
    this.watermark,
    this.printedBy,
    this.printedAt,
  });

  bool get isReprint => reprintCount > 0;

  factory DocumentLabelModel.fromJson(Map<String, dynamic> json) => DocumentLabelModel(
    documentType: json['doctype'] as String? ?? json['document_type'] as String? ?? '',
    documentName: json['name'] as String? ?? json['document_name'] as String? ?? '',
    labelType: json['label_type'] as String? ?? 'Shipping Carton',
    labelFormat: json['label_format'] as String? ?? json['format'] as String? ?? 'html',
    payloadContent: json['template'] as String? ?? json['payload'] as String? ?? json['content'] as String? ?? '',
    reprintCount: (json['reprint_count'] as num?)?.toInt() ?? 0,
    watermark: json['watermark'] as String?,
    printedBy: json['printed_by'] as String?,
    printedAt: DateTime.tryParse(json['printed_at'] as String? ?? ''),
  );

  Map<String, dynamic> toJson() => {
    'doctype': documentType,
    'name': documentName,
    'label_type': labelType,
    'label_format': labelFormat,
    'template': payloadContent,
    'reprint_count': reprintCount,
    'watermark': watermark,
    'printed_by': printedBy,
    'printed_at': printedAt?.toIso8601String(),
  };
}
