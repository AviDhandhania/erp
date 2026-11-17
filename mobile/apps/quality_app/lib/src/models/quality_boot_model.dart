// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Summary metrics of active quality queues.
@immutable
class QualityQueueSummaryModel {
  final int activeCycles;
  final int stageDue;
  final int pendingCorrections;
  final int returnsAwaitingInspection;
  final int pendingGateReviews;

  const QualityQueueSummaryModel({
    this.activeCycles = 0,
    this.stageDue = 0,
    this.pendingCorrections = 0,
    this.returnsAwaitingInspection = 0,
    this.pendingGateReviews = 0,
  });

  factory QualityQueueSummaryModel.fromJson(Map<String, dynamic> json) {
    return QualityQueueSummaryModel(
      activeCycles: (json['active_cycles'] as num?)?.toInt() ?? 0,
      stageDue: (json['stage_due'] as num?)?.toInt() ?? 0,
      pendingCorrections: (json['pending_corrections'] as num?)?.toInt() ?? 0,
      returnsAwaitingInspection: (json['returns_awaiting_inspection'] as num?)?.toInt() ?? 0,
      pendingGateReviews: (json['pending_gate_reviews'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'active_cycles': activeCycles,
    'stage_due': stageDue,
    'pending_corrections': pendingCorrections,
    'returns_awaiting_inspection': returnsAwaitingInspection,
    'pending_gate_reviews': pendingGateReviews,
  };
}

/// Boot context and role scoping for Clothing Quality Mobile.
///
/// Roles:
/// - `Clothing Quality Inspector`: Field inspections, stage reports, readings, photo evidence.
/// - `Clothing Quality Manager`: Checklist templates, correction requests, gate reviews.
/// - `Clothing Business Administrator`: Global oversight and high-risk gate decisions.
@immutable
class QualityBootModel {
  final String apiVersion;
  final String appVersion;
  final String user;
  final String role;
  final List<String> assignedSuppliers; // Allowed suppliers or ['*'] for manager/admin
  final List<String> assignedCompanies;
  final DateTime serverTime;
  final QualityQueueSummaryModel queues;
  final Map<String, bool> featureFlags;

  const QualityBootModel({
    this.apiVersion = 'v1',
    this.appVersion = '1.0.0',
    required this.user,
    required this.role,
    required this.assignedSuppliers,
    required this.assignedCompanies,
    required this.serverTime,
    this.queues = const QualityQueueSummaryModel(),
    this.featureFlags = const {},
  });

  bool get isInspector => role == 'Clothing Quality Inspector';
  bool get isQualityManager => role == 'Clothing Quality Manager';
  bool get isBusinessAdmin => role == 'Clothing Business Administrator' || role == 'System Manager';
  bool get hasAuthorizedQualityRole => isInspector || isQualityManager || isBusinessAdmin;
  bool get canDecideCriticalGates => isQualityManager || isBusinessAdmin;

  bool isSupplierAllowed(String supplier) {
    if (isBusinessAdmin || isQualityManager || assignedSuppliers.contains('*')) return true;
    return assignedSuppliers.contains(supplier);
  }

  factory QualityBootModel.fromJson(Map<String, dynamic> json) {
    final rawSuppliers = json['assigned_suppliers'] as List<dynamic>? ?? [];
    final rawCompanies = json['assigned_companies'] as List<dynamic>? ?? [];
    final rawFlags = json['features'] as Map<String, dynamic>? ?? {};
    final queuesJson = json['queues'] as Map<String, dynamic>? ?? {};

    return QualityBootModel(
      apiVersion: json['api_version'] as String? ?? 'v1',
      appVersion: json['app_version'] as String? ?? '1.0.0',
      user: json['user'] as String? ?? '',
      role: json['operational_role'] as String? ?? json['role'] as String? ?? 'Clothing Quality Inspector',
      assignedSuppliers: rawSuppliers.map((s) => s.toString()).toList(),
      assignedCompanies: rawCompanies.map((c) => c.toString()).toList(),
      serverTime: DateTime.tryParse(json['server_time'] as String? ?? '') ?? DateTime.now(),
      queues: QualityQueueSummaryModel.fromJson(queuesJson),
      featureFlags: rawFlags.map((k, v) => MapEntry(k, v == true)),
    );
  }

  Map<String, dynamic> toJson() => {
    'api_version': apiVersion,
    'app_version': appVersion,
    'user': user,
    'role': role,
    'operational_role': role,
    'assigned_suppliers': assignedSuppliers,
    'assigned_companies': assignedCompanies,
    'server_time': serverTime.toIso8601String(),
    'queues': queues.toJson(),
    'features': featureFlags,
  };
}
