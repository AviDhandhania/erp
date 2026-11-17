// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';
import 'fulfillment_task_model.dart';

/// Summary counts of active work queues for the manager's assigned warehouses.
@immutable
class WorkQueueSummaryModel {
  final int pendingPick;
  final int pendingPack;
  final int pendingDispatch;
  final int pendingReturns;
  final int activeRefurbishment;

  const WorkQueueSummaryModel({
    this.pendingPick = 0,
    this.pendingPack = 0,
    this.pendingDispatch = 0,
    this.pendingReturns = 0,
    this.activeRefurbishment = 0,
  });

  factory WorkQueueSummaryModel.fromJson(Map<String, dynamic> json) {
    return WorkQueueSummaryModel(
      pendingPick: (json['pending_pick'] as num?)?.toInt() ?? 0,
      pendingPack: (json['pending_pack'] as num?)?.toInt() ?? 0,
      pendingDispatch: (json['pending_dispatch'] as num?)?.toInt() ?? 0,
      pendingReturns: (json['pending_returns'] as num?)?.toInt() ?? 0,
      activeRefurbishment: (json['active_refurbishment'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'pending_pick': pendingPick,
    'pending_pack': pendingPack,
    'pending_dispatch': pendingDispatch,
    'pending_returns': pendingReturns,
    'active_refurbishment': activeRefurbishment,
  };
}

/// Wave or route work queue grouping fulfillment tasks for an assigned warehouse.
@immutable
class WorkQueueModel {
  final String queueId; // e.g. WAVE-2026-11-17-01 or ROUTE-DELHI-NORTH
  final String queueType; // 'wave' | 'route' | 'priority'
  final String warehouse;
  final int totalTasks;
  final int openTasks;
  final int completedTasks;
  final List<FulfillmentTaskModel> tasks;

  const WorkQueueModel({
    required this.queueId,
    required this.queueType,
    required this.warehouse,
    required this.totalTasks,
    required this.openTasks,
    this.completedTasks = 0,
    this.tasks = const [],
  });

  bool get isCompleted => openTasks == 0 && totalTasks > 0;

  factory WorkQueueModel.fromJson(Map<String, dynamic> json) {
    final rawTasks = json['tasks'] as List<dynamic>? ?? [];
    return WorkQueueModel(
      queueId: json['queue_id'] as String? ?? json['name'] as String? ?? '',
      queueType: json['queue_type'] as String? ?? 'wave',
      warehouse: json['warehouse'] as String? ?? '',
      totalTasks: (json['total_tasks'] as num?)?.toInt() ?? 0,
      openTasks: (json['open_tasks'] as num?)?.toInt() ?? 0,
      completedTasks: (json['completed_tasks'] as num?)?.toInt() ?? 0,
      tasks: rawTasks
          .whereType<Map<String, dynamic>>()
          .map((t) => FulfillmentTaskModel.fromJson(t))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'queue_id': queueId,
    'queue_type': queueType,
    'warehouse': warehouse,
    'total_tasks': totalTasks,
    'open_tasks': openTasks,
    'completed_tasks': completedTasks,
    'tasks': tasks.map((t) => t.toJson()).toList(),
  };
}
