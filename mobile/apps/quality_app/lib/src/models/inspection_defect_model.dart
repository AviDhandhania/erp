// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Defect observation item on a garment sample.
@immutable
class InspectionDefectModel {
  final String defectCode;
  final String description;
  final int count;
  final String severity; // 'Minor' | 'Major' | 'Critical'

  const InspectionDefectModel({
    required this.defectCode,
    required this.description,
    this.count = 1,
    this.severity = 'Minor',
  });

  bool get isCritical => severity == 'Critical';
  bool get isMajor => severity == 'Major';
  bool get isMinor => severity == 'Minor';

  factory InspectionDefectModel.fromJson(Map<String, dynamic> json) {
    return InspectionDefectModel(
      defectCode: json['defect_code'] as String? ?? '',
      description: json['description'] as String? ?? json['defect_description'] as String? ?? '',
      count: (json['count'] as num?)?.toInt() ?? 1,
      severity: json['severity'] as String? ?? 'Minor',
    );
  }

  Map<String, dynamic> toJson() => {
    'defect_code': defectCode,
    'description': description,
    'count': count,
    'severity': severity,
  };
}

/// AQL sampling plan metrics for a production lot inspection.
@immutable
class AqlSamplingPlanModel {
  final String aqlStandard; // e.g. 'AQL 2.5 General Level II'
  final int lotSize;
  final int sampleSize;
  final int maxAllowedCritical;
  final int maxAllowedMajor;
  final int maxAllowedMinor;
  final int passedQty;
  final int failedQty;

  const AqlSamplingPlanModel({
    this.aqlStandard = 'AQL 2.5 General Level II',
    required this.lotSize,
    required this.sampleSize,
    this.maxAllowedCritical = 0,
    this.maxAllowedMajor = 3,
    this.maxAllowedMinor = 7,
    this.passedQty = 0,
    this.failedQty = 0,
  });

  bool isLotAccepted({
    required int criticalCount,
    required int majorCount,
    required int minorCount,
  }) {
    if (criticalCount > maxAllowedCritical) return false;
    if (majorCount > maxAllowedMajor) return false;
    if (minorCount > maxAllowedMinor) return false;
    return true;
  }

  factory AqlSamplingPlanModel.fromJson(Map<String, dynamic> json) {
    return AqlSamplingPlanModel(
      aqlStandard: json['aql_standard'] as String? ?? 'AQL 2.5 General Level II',
      lotSize: (json['lot_size'] as num?)?.toInt() ?? 0,
      sampleSize: (json['sample_size'] as num?)?.toInt() ?? 0,
      maxAllowedCritical: (json['max_allowed_critical'] as num?)?.toInt() ?? 0,
      maxAllowedMajor: (json['max_allowed_major'] as num?)?.toInt() ?? 3,
      maxAllowedMinor: (json['max_allowed_minor'] as num?)?.toInt() ?? 7,
      passedQty: (json['passed_qty'] as num?)?.toInt() ?? 0,
      failedQty: (json['failed_qty'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'aql_standard': aqlStandard,
    'lot_size': lotSize,
    'sample_size': sampleSize,
    'max_allowed_critical': maxAllowedCritical,
    'max_allowed_major': maxAllowedMajor,
    'max_allowed_minor': maxAllowedMinor,
    'passed_qty': passedQty,
    'failed_qty': failedQty,
  };
}
