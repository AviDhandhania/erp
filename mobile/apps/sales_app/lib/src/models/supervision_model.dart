// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Supervised Area Sales Manager (ASM) summary for an RSM's supervision view.
@immutable
class SupervisedAsmModel {
  final String username;
  final String fullName;
  final String assignedTerritory;
  final int activeRetailerCount;
  final int pendingVisitsCount;
  final int pendingOrdersCount;

  const SupervisedAsmModel({
    required this.username,
    required this.fullName,
    required this.assignedTerritory,
    required this.activeRetailerCount,
    this.pendingVisitsCount = 0,
    this.pendingOrdersCount = 0,
  });

  factory SupervisedAsmModel.fromJson(Map<String, dynamic> json) => SupervisedAsmModel(
    username: json['asm'] as String? ?? json['username'] as String? ?? '',
    fullName: json['full_name'] as String? ?? json['asm_name'] as String? ?? '',
    assignedTerritory: json['territory'] as String? ?? '',
    activeRetailerCount: json['retailer_count'] as int? ?? 0,
    pendingVisitsCount: json['pending_visits'] as int? ?? 0,
    pendingOrdersCount: json['pending_orders'] as int? ?? 0,
  );

  Map<String, dynamic> toJson() => {
    'asm': username,
    'full_name': fullName,
    'territory': assignedTerritory,
    'retailer_count': activeRetailerCount,
    'pending_visits': pendingVisitsCount,
    'pending_orders': pendingOrdersCount,
  };
}

/// Regional Sales Manager (RSM) operational supervision overview.
///
/// Security Boundary:
/// RSMs have supervision and approval authority over assigned ASMs and territory workflows,
/// but ZERO user-management privilege (cannot create, edit, or disable users).
@immutable
class RsmSupervisionOverviewModel {
  final String rsmUser;
  final List<SupervisedAsmModel> supervisedAsms;
  final int totalRetailersCount;
  final int maxRecommendedRetailers; // Standard guidance: ~200–250
  final int maxRecommendedAsms; // Standard guidance: ~3–4
  final bool isWithinCapacity;
  final String? capacityWarningMessage;

  // Review queues
  final int pendingApplicationReviews;
  final int pendingOrderApprovals;
  final int overdueRsmVisits;

  const RsmSupervisionOverviewModel({
    required this.rsmUser,
    required this.supervisedAsms,
    this.totalRetailersCount = 0,
    this.maxRecommendedRetailers = 250,
    this.maxRecommendedAsms = 4,
    this.isWithinCapacity = true,
    this.capacityWarningMessage,
    this.pendingApplicationReviews = 0,
    this.pendingOrderApprovals = 0,
    this.overdueRsmVisits = 0,
  });

  int get activeAsmCount => supervisedAsms.length;

  factory RsmSupervisionOverviewModel.fromJson(Map<String, dynamic> json) {
    final rawAsms = json['asms'] as List<dynamic>? ?? [];
    return RsmSupervisionOverviewModel(
      rsmUser: json['rsm'] as String? ?? '',
      supervisedAsms: rawAsms
          .whereType<Map<String, dynamic>>()
          .map((a) => SupervisedAsmModel.fromJson(a))
          .toList(),
      totalRetailersCount: json['total_retailers'] as int? ?? 0,
      maxRecommendedRetailers: json['max_retailers'] as int? ?? 250,
      maxRecommendedAsms: json['max_asms'] as int? ?? 4,
      isWithinCapacity: json['is_within_capacity'] as bool? ?? true,
      capacityWarningMessage: json['capacity_warning'] as String?,
      pendingApplicationReviews: json['pending_applications'] as int? ?? 0,
      pendingOrderApprovals: json['pending_orders'] as int? ?? 0,
      overdueRsmVisits: json['overdue_rsm_visits'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'rsm': rsmUser,
    'asms': supervisedAsms.map((a) => a.toJson()).toList(),
    'total_retailers': totalRetailersCount,
    'max_retailers': maxRecommendedRetailers,
    'max_asms': maxRecommendedAsms,
    'is_within_capacity': isWithinCapacity,
    'capacity_warning': capacityWarningMessage,
    'pending_applications': pendingApplicationReviews,
    'pending_orders': pendingOrderApprovals,
    'overdue_rsm_visits': overdueRsmVisits,
  };
}
