// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Territory-scoped retailer entity representing an authorized boutique or store.
@immutable
class RetailerModel {
  final String id; // Customer.name
  final String customerName;
  final String territory;
  final String operatingType; // Buy & Sell | Buy & Sell — Stock Correction | SIS | EBOC
  final String? mobileNo;
  final String? emailId;
  final String? primaryAddress;
  final double? latitude;
  final double? longitude;

  // Commercial exposure metrics (Server-calculated, strictly non-authoritative on client)
  final double approvedExposureLimit;
  final double totalExposure;
  final double availableExposure;
  final bool exceedsLimit;

  // Operational cadence & blocking states
  final String cadenceStatus; // OK | Approaching | Grace | Overdue
  final bool orderBlocked;
  final String? blockReason;

  const RetailerModel({
    required this.id,
    required this.customerName,
    required this.territory,
    required this.operatingType,
    this.mobileNo,
    this.emailId,
    this.primaryAddress,
    this.latitude,
    this.longitude,
    this.approvedExposureLimit = 0.0,
    this.totalExposure = 0.0,
    this.availableExposure = 0.0,
    this.exceedsLimit = false,
    this.cadenceStatus = 'OK',
    this.orderBlocked = false,
    this.blockReason,
  });

  bool get isSIS => operatingType.toUpperCase().contains('SIS');
  bool get isBuyAndSell => operatingType.toUpperCase().contains('BUY & SELL');
  bool get isEBOC => operatingType.toUpperCase().contains('EBOC') || operatingType.toUpperCase().contains('EBO');

  factory RetailerModel.fromJson(Map<String, dynamic> json) {
    return RetailerModel(
      id: json['name'] as String? ?? json['id'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      territory: json['territory'] as String? ?? '',
      operatingType: json['customer_group'] as String? ?? json['operating_type'] as String? ?? 'Buy & Sell',
      mobileNo: json['mobile_no'] as String?,
      emailId: json['email_id'] as String?,
      primaryAddress: json['primary_address'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      approvedExposureLimit: (json['approved_limit'] as num?)?.toDouble() ?? 0.0,
      totalExposure: (json['total_exposure'] as num?)?.toDouble() ?? 0.0,
      availableExposure: (json['available_exposure'] as num?)?.toDouble() ?? 0.0,
      exceedsLimit: json['exceeds_limit'] as bool? ?? false,
      cadenceStatus: json['cadence_status'] as String? ?? 'OK',
      orderBlocked: json['order_blocked'] as bool? ?? false,
      blockReason: json['block_reason'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': id,
    'customer_name': customerName,
    'territory': territory,
    'customer_group': operatingType,
    'mobile_no': mobileNo,
    'email_id': emailId,
    'primary_address': primaryAddress,
    'latitude': latitude,
    'longitude': longitude,
    'approved_limit': approvedExposureLimit,
    'total_exposure': totalExposure,
    'available_exposure': availableExposure,
    'exceeds_limit': exceedsLimit,
    'cadence_status': cadenceStatus,
    'order_blocked': orderBlocked,
    'block_reason': blockReason,
  };
}
