// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Visit obligation representing a scheduled cadence target.
@immutable
class VisitObligationModel {
  final String id;
  final String obligationType; // 'RSM 80-Day' | 'SIS Quarterly Stock Review' | 'SIS Monthly' | 'Buy & Sell Monthly' | 'Seasonal Prebooking'
  final String customer;
  final String customerName;
  final String retailerType;
  final String territory;
  final String? assignedAsm;
  final String? supervisingRsm;
  final DateTime dueDate;
  final DateTime? graceEndDate;
  final String status; // 'Upcoming' | 'Due' | 'Grace' | 'Overdue' | 'Satisfied'
  final String? escalationState;

  const VisitObligationModel({
    required this.id,
    required this.obligationType,
    required this.customer,
    required this.customerName,
    required this.retailerType,
    required this.territory,
    this.assignedAsm,
    this.supervisingRsm,
    required this.dueDate,
    this.graceEndDate,
    this.status = 'Upcoming',
    this.escalationState,
  });

  bool get isOverdue => status == 'Overdue';
  bool get isInGrace => status == 'Grace';
  bool get isDue => status == 'Due';
  bool get isSatisfied => status == 'Satisfied';

  factory VisitObligationModel.fromJson(Map<String, dynamic> json) => VisitObligationModel(
    id: json['name'] as String? ?? '',
    obligationType: json['obligation_type'] as String? ?? 'General Visit',
    customer: json['customer'] as String? ?? '',
    customerName: json['customer_name'] as String? ?? '',
    retailerType: json['retailer_type'] as String? ?? 'Buy & Sell',
    territory: json['territory'] as String? ?? '',
    assignedAsm: json['assigned_asm'] as String?,
    supervisingRsm: json['supervising_rsm'] as String? ?? json['rsm'] as String?,
    dueDate: DateTime.tryParse(json['due_date'] as String? ?? '') ?? DateTime.now(),
    graceEndDate: DateTime.tryParse(json['grace_end_date'] as String? ?? ''),
    status: json['status'] as String? ?? 'Upcoming',
    escalationState: json['escalation_state'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'name': id,
    'obligation_type': obligationType,
    'customer': customer,
    'customer_name': customerName,
    'retailer_type': retailerType,
    'territory': territory,
    'assigned_asm': assignedAsm,
    'supervising_rsm': supervisingRsm,
    'due_date': dueDate.toIso8601String().substring(0, 10),
    'grace_end_date': graceEndDate?.toIso8601String().substring(0, 10),
    'status': status,
    'escalation_state': escalationState,
  };
}

/// Executed visit report with geolocation check-in and operational findings.
@immutable
class RetailerVisitReportModel {
  final String? id;
  final String customer;
  final String customerName;
  final DateTime visitDate;
  final String outcome; // Order Taken | Samples Shown | Stock Reviewed | Follow-Up Needed | Retailer Unavailable
  final String? notes;

  // Geolocation check-in verification
  final double? latitude;
  final double? longitude;
  final double? accuracyMeters;
  final DateTime? checkinTimestamp;
  final String checkinStatus; // Verified | Out of Range | Offline Recorded | Skipped
  final bool consentGiven;
  final String? checkinPhotoUrl;

  // Specialist review fields
  final int? footfall;
  final String? financialSituationReview;
  final int? sisStockAuditQuantity;
  final String? exposureReviewNotes;
  final String? followUpAction;
  final DateTime? followUpDueDate;

  const RetailerVisitReportModel({
    this.id,
    required this.customer,
    required this.customerName,
    required this.visitDate,
    required this.outcome,
    this.notes,
    this.latitude,
    this.longitude,
    this.accuracyMeters,
    this.checkinTimestamp,
    this.checkinStatus = 'Pending',
    this.consentGiven = false,
    this.checkinPhotoUrl,
    this.footfall,
    this.financialSituationReview,
    this.sisStockAuditQuantity,
    this.exposureReviewNotes,
    this.followUpAction,
    this.followUpDueDate,
  });

  factory RetailerVisitReportModel.fromJson(Map<String, dynamic> json) => RetailerVisitReportModel(
    id: json['name'] as String?,
    customer: json['customer'] as String? ?? '',
    customerName: json['customer_name'] as String? ?? '',
    visitDate: DateTime.tryParse(json['visit_date'] as String? ?? '') ?? DateTime.now(),
    outcome: json['outcome'] as String? ?? 'General Visit',
    notes: json['notes'] as String?,
    latitude: (json['checkin_latitude'] as num?)?.toDouble() ?? (json['latitude'] as num?)?.toDouble(),
    longitude: (json['checkin_longitude'] as num?)?.toDouble() ?? (json['longitude'] as num?)?.toDouble(),
    accuracyMeters: (json['checkin_accuracy_meters'] as num?)?.toDouble(),
    checkinTimestamp: DateTime.tryParse(json['checkin_timestamp'] as String? ?? ''),
    checkinStatus: json['checkin_status'] as String? ?? 'Pending',
    consentGiven: json['checkin_consent'] == 1 || json['checkin_consent'] == true,
    checkinPhotoUrl: json['checkin_photo'] as String?,
    footfall: json['footfall'] as int?,
    financialSituationReview: json['financial_situation_review'] as String?,
    sisStockAuditQuantity: json['sis_stock_audit_quantity'] as int?,
    exposureReviewNotes: json['exposure_review_notes'] as String?,
    followUpAction: json['follow_up_action'] as String?,
    followUpDueDate: DateTime.tryParse(json['follow_up_due_date'] as String? ?? ''),
  );

  Map<String, dynamic> toJson() => {
    'name': id,
    'customer': customer,
    'customer_name': customerName,
    'visit_date': visitDate.toIso8601String().substring(0, 10),
    'outcome': outcome,
    'notes': notes,
    'checkin_latitude': latitude,
    'checkin_longitude': longitude,
    'checkin_accuracy_meters': accuracyMeters,
    'checkin_timestamp': checkinTimestamp?.toIso8601String(),
    'checkin_status': checkinStatus,
    'checkin_consent': consentGiven ? 1 : 0,
    'checkin_photo': checkinPhotoUrl,
    'footfall': footfall,
    'financial_situation_review': financialSituationReview,
    'sis_stock_audit_quantity': sisStockAuditQuantity,
    'exposure_review_notes': exposureReviewNotes,
    'follow_up_action': followUpAction,
    'follow_up_due_date': followUpDueDate?.toIso8601String().substring(0, 10),
  };
}
