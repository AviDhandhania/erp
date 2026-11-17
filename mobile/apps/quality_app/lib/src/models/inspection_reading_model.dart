// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Measurement parameter reading with server-verified tolerances and variance.
@immutable
class InspectionReadingModel {
  final String parameter;
  final String? size;
  final double specTarget;
  final double tolerancePlus;
  final double toleranceMinus;
  final double actualReading;
  final String uom; // 'cm' | 'inch'

  const InspectionReadingModel({
    required this.parameter,
    this.size,
    required this.specTarget,
    this.tolerancePlus = 1.0,
    this.toleranceMinus = 1.0,
    required this.actualReading,
    this.uom = 'cm',
  });

  /// Computed variance: actual reading minus target specification.
  double get variance => actualReading - specTarget;

  /// In-spec classification: reading falls within allowed bounds.
  bool get isInSpec =>
      actualReading >= (specTarget - toleranceMinus) &&
      actualReading <= (specTarget + tolerancePlus);

  String get status => isInSpec ? 'In Spec' : 'Out of Spec';

  InspectionReadingModel copyWith({
    double? actualReading,
  }) {
    return InspectionReadingModel(
      parameter: parameter,
      size: size,
      specTarget: specTarget,
      tolerancePlus: tolerancePlus,
      toleranceMinus: toleranceMinus,
      actualReading: actualReading ?? this.actualReading,
      uom: uom,
    );
  }

  factory InspectionReadingModel.fromJson(Map<String, dynamic> json) {
    return InspectionReadingModel(
      parameter: json['parameter'] as String? ?? json['reading_parameter'] as String? ?? '',
      size: json['size'] as String?,
      specTarget: (json['spec_target'] as num?)?.toDouble() ?? 0.0,
      tolerancePlus: (json['tolerance_plus'] as num?)?.toDouble() ?? 1.0,
      toleranceMinus: (json['tolerance_minus'] as num?)?.toDouble() ?? 1.0,
      actualReading: (json['actual_reading'] as num?)?.toDouble() ?? 0.0,
      uom: json['uom'] as String? ?? 'cm',
    );
  }

  Map<String, dynamic> toJson() => {
    'parameter': parameter,
    'size': size,
    'spec_target': specTarget,
    'tolerance_plus': tolerancePlus,
    'tolerance_minus': toleranceMinus,
    'actual_reading': actualReading,
    'variance': variance,
    'status': status,
    'uom': uom,
  };
}
