// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Package measurement and carton identity model for packing slips.
@immutable
class PackingPackageModel {
  final String? packingSlipName; // Created Packing Slip name (e.g. PS-2026-0001)
  final String deliveryNote;
  final int fromCaseNo;
  final int toCaseNo;
  final String packageBarcode;
  final double grossWeightPkg;
  final double netWeightPkg;
  final double? length;
  final double? width;
  final double? height;
  final String dimensionUom; // 'cm' | 'inch'
  final List<Map<String, dynamic>> items;

  const PackingPackageModel({
    this.packingSlipName,
    required this.deliveryNote,
    this.fromCaseNo = 1,
    this.toCaseNo = 1,
    required this.packageBarcode,
    this.grossWeightPkg = 0.0,
    this.netWeightPkg = 0.0,
    this.length,
    this.width,
    this.height,
    this.dimensionUom = 'cm',
    this.items = const [],
  });

  double get volumeCubicCm {
    if (length == null || width == null || height == null) return 0.0;
    return length! * width! * height!;
  }

  factory PackingPackageModel.fromJson(Map<String, dynamic> json) => PackingPackageModel(
    packingSlipName: json['name'] as String? ?? json['packing_slip'] as String?,
    deliveryNote: json['delivery_note'] as String? ?? '',
    fromCaseNo: json['from_case_no'] as int? ?? 1,
    toCaseNo: json['to_case_no'] as int? ?? 1,
    packageBarcode: json['package_barcode'] as String? ?? json['carton_barcode'] as String? ?? '',
    grossWeightPkg: (json['gross_weight_pkg'] as num?)?.toDouble() ?? 0.0,
    netWeightPkg: (json['net_weight_pkg'] as num?)?.toDouble() ?? 0.0,
    length: (json['length'] as num?)?.toDouble(),
    width: (json['width'] as num?)?.toDouble(),
    height: (json['height'] as num?)?.toDouble(),
    dimensionUom: json['dimension_uom'] as String? ?? 'cm',
    items: (json['items'] as List<dynamic>?)?.whereType<Map<String, dynamic>>().toList() ?? const [],
  );

  Map<String, dynamic> toJson() => {
    'name': packingSlipName,
    'delivery_note': deliveryNote,
    'from_case_no': fromCaseNo,
    'to_case_no': toCaseNo,
    'package_barcode': packageBarcode,
    'gross_weight_pkg': grossWeightPkg,
    'net_weight_pkg': netWeightPkg,
    'length': length,
    'width': width,
    'height': height,
    'dimension_uom': dimensionUom,
    'items': items,
  };
}
