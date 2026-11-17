// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';
import 'work_queue_model.dart';

/// Manager context and assigned warehouse scopes returned on bootstrap.
///
/// Security Boundary:
/// Restricted strictly to `Clothing Warehouse Manager` and `Clothing Business Administrator`.
/// Common operators are completely retired; zero operator access.
@immutable
class WarehouseBootModel {
  final String apiVersion;
  final String appVersion;
  final String user;
  final String role; // 'Clothing Warehouse Manager' | 'Clothing Business Administrator'
  final List<String> assignedWarehouses; // Allowed leaf warehouses or ['*'] for admin
  final DateTime serverTime;
  final Map<String, bool> featureFlags;
  final String? defaultWarehouse;
  final String? sessionId;
  final WorkQueueSummaryModel queues;

  const WarehouseBootModel({
    this.apiVersion = 'v1',
    this.appVersion = '1.0.0',
    required this.user,
    required this.role,
    required this.assignedWarehouses,
    required this.serverTime,
    this.featureFlags = const {},
    this.defaultWarehouse,
    this.sessionId,
    this.queues = const WorkQueueSummaryModel(),
  });

  bool get isWarehouseManager => role == 'Clothing Warehouse Manager';
  bool get isBusinessAdmin => role == 'Clothing Business Administrator' || role == 'System Manager';
  bool get isManager => isWarehouseManager;
  bool get isAdmin => isBusinessAdmin;
  bool get hasAuthorizedManagerRole => isWarehouseManager || isBusinessAdmin;
  String get operationalRole => role;

  bool isWarehouseAllowed(String warehouse) {
    if (isAdmin || assignedWarehouses.contains('*') || assignedWarehouses.contains('All Warehouses')) return true;
    return assignedWarehouses.contains(warehouse);
  }

  factory WarehouseBootModel.fromJson(Map<String, dynamic> json) {
    final rawWh = json['assigned_warehouses'] as List<dynamic>? ?? [];
    final rawFlags = json['features'] as Map<String, dynamic>? ?? {};
    final queuesJson = json['queues'] as Map<String, dynamic>? ?? {};

    return WarehouseBootModel(
      apiVersion: json['api_version'] as String? ?? 'v1',
      appVersion: json['app_version'] as String? ?? '1.0.0',
      user: json['user'] as String? ?? '',
      role: json['operational_role'] as String? ?? json['role'] as String? ?? 'Clothing Warehouse Manager',
      assignedWarehouses: rawWh.map((w) => w.toString()).toList(),
      serverTime: DateTime.tryParse(json['server_time'] as String? ?? '') ?? DateTime.now(),
      featureFlags: rawFlags.map((k, v) => MapEntry(k, v == true)),
      defaultWarehouse: json['default_warehouse'] as String?,
      sessionId: json['session_id'] as String?,
      queues: WorkQueueSummaryModel.fromJson(queuesJson),
    );
  }

  Map<String, dynamic> toJson() => {
    'api_version': apiVersion,
    'app_version': appVersion,
    'user': user,
    'role': role,
    'operational_role': role,
    'assigned_warehouses': assignedWarehouses,
    'default_warehouse': defaultWarehouse,
    'session_id': sessionId,
    'server_time': serverTime.toIso8601String(),
    'features': featureFlags,
    'queues': queues.toJson(),
  };
}
