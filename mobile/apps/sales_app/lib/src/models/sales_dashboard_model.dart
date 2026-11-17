// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Role-aware dashboard model representing territorial metrics and pending obligations
/// for Area Sales Managers (ASM) and Regional Sales Managers (RSM).
@immutable
class SalesDashboardModel {
  final String user;
  final String operationalRole; // 'ASM' | 'RSM' | 'Admin'
  final List<String> assignedTerritories;
  final DateTime serverTime;

  // Applications metrics
  final int pendingApplications;
  final int rfiApplications; // More Information Requested
  final int approvedApplicationsThisMonth;

  // Visit & Cadence metrics
  final int completedVisitsThisMonth;
  final int rsmOverdueVisits;
  final int rsmGraceVisits;
  final int upcomingObligations;

  // Order metrics
  final int draftOrdersCount;
  final int submittedOrdersCount;
  final double submittedOrdersValue;

  // Exposure & Retailer metrics
  final int totalAssignedRetailers;
  final double totalApprovedExposureLimit;
  final double totalCurrentExposure;
  final int retailersOverExposureLimit;

  // Collection metrics
  final int overdueInvoices90To120Days;
  final double totalOverdueCollectionAmount;
  final int hardBlockedRetailersCount;

  // Delivery Follow-Up metrics
  final int pendingDeliveryFollowUps;
  final int escalatedDeliveryFollowUps;

  const SalesDashboardModel({
    required this.user,
    required this.operationalRole,
    required this.assignedTerritories,
    required this.serverTime,
    this.pendingApplications = 0,
    this.rfiApplications = 0,
    this.approvedApplicationsThisMonth = 0,
    this.completedVisitsThisMonth = 0,
    this.rsmOverdueVisits = 0,
    this.rsmGraceVisits = 0,
    this.upcomingObligations = 0,
    this.draftOrdersCount = 0,
    this.submittedOrdersCount = 0,
    this.submittedOrdersValue = 0.0,
    this.totalAssignedRetailers = 0,
    this.totalApprovedExposureLimit = 0.0,
    this.totalCurrentExposure = 0.0,
    this.retailersOverExposureLimit = 0,
    this.overdueInvoices90To120Days = 0,
    this.totalOverdueCollectionAmount = 0.0,
    this.hardBlockedRetailersCount = 0,
    this.pendingDeliveryFollowUps = 0,
    this.escalatedDeliveryFollowUps = 0,
  });

  bool get isRSM => operationalRole == 'RSM' || operationalRole == 'Clothing Regional Sales Manager';
  bool get isASM => operationalRole == 'ASM' || operationalRole == 'Clothing Area Sales Manager' || operationalRole == 'Clothing Sales Representative';
  bool get isAdmin => operationalRole == 'Admin' || operationalRole == 'System Manager';

  factory SalesDashboardModel.fromJson(Map<String, dynamic> json) {
    final applications = json['applications'] as Map<String, dynamic>? ?? {};
    final visits = json['visits'] as Map<String, dynamic>? ?? {};
    final cadence = json['cadence'] as Map<String, dynamic>? ?? {};
    final orders = json['orders'] as Map<String, dynamic>? ?? {};
    final exposure = json['exposure'] as Map<String, dynamic>? ?? {};
    final collections = json['collections'] as Map<String, dynamic>? ?? {};
    final deliveries = json['deliveries'] as Map<String, dynamic>? ?? {};

    return SalesDashboardModel(
      user: json['user'] as String? ?? '',
      operationalRole: json['role'] as String? ?? 'ASM',
      assignedTerritories: (json['territories'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      serverTime: DateTime.tryParse(json['server_time'] as String? ?? '') ?? DateTime.now(),
      pendingApplications: applications['pending'] as int? ?? 0,
      rfiApplications: applications['rfi'] as int? ?? 0,
      approvedApplicationsThisMonth: applications['approved_this_month'] as int? ?? 0,
      completedVisitsThisMonth: visits['completed_this_month'] as int? ?? 0,
      rsmOverdueVisits: cadence['rsm_overdue'] as int? ?? 0,
      rsmGraceVisits: cadence['rsm_grace'] as int? ?? 0,
      upcomingObligations: cadence['upcoming_obligations'] as int? ?? 0,
      draftOrdersCount: orders['draft_count'] as int? ?? 0,
      submittedOrdersCount: orders['submitted_count'] as int? ?? 0,
      submittedOrdersValue: (orders['submitted_value'] as num?)?.toDouble() ?? 0.0,
      totalAssignedRetailers: exposure['total_retailers'] as int? ?? 0,
      totalApprovedExposureLimit: (exposure['total_approved_limit'] as num?)?.toDouble() ?? 0.0,
      totalCurrentExposure: (exposure['total_current_exposure'] as num?)?.toDouble() ?? 0.0,
      retailersOverExposureLimit: exposure['over_limit_count'] as int? ?? 0,
      overdueInvoices90To120Days: collections['count_90_120'] as int? ?? 0,
      totalOverdueCollectionAmount: (collections['total_amount'] as num?)?.toDouble() ?? 0.0,
      hardBlockedRetailersCount: collections['blocked_retailers_count'] as int? ?? 0,
      pendingDeliveryFollowUps: deliveries['pending_count'] as int? ?? 0,
      escalatedDeliveryFollowUps: deliveries['escalated_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'user': user,
    'role': operationalRole,
    'territories': assignedTerritories,
    'server_time': serverTime.toIso8601String(),
    'applications': {
      'pending': pendingApplications,
      'rfi': rfiApplications,
      'approved_this_month': approvedApplicationsThisMonth,
    },
    'visits': {
      'completed_this_month': completedVisitsThisMonth,
    },
    'cadence': {
      'rsm_overdue': rsmOverdueVisits,
      'rsm_grace': rsmGraceVisits,
      'upcoming_obligations': upcomingObligations,
    },
    'orders': {
      'draft_count': draftOrdersCount,
      'submitted_count': submittedOrdersCount,
      'submitted_value': submittedOrdersValue,
    },
    'exposure': {
      'total_retailers': totalAssignedRetailers,
      'total_approved_limit': totalApprovedExposureLimit,
      'total_current_exposure': totalCurrentExposure,
      'over_limit_count': retailersOverExposureLimit,
    },
    'collections': {
      'count_90_120': overdueInvoices90To120Days,
      'total_amount': totalOverdueCollectionAmount,
      'blocked_retailers_count': hardBlockedRetailersCount,
    },
    'deliveries': {
      'pending_count': pendingDeliveryFollowUps,
      'escalated_count': escalatedDeliveryFollowUps,
    },
  };
}
