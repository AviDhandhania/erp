// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/visits_controller.dart';
import '../models/retailer_visit_model.dart';

/// Screen presenting the scheduled visit queues across Monthly, SIS, Seasonal, and RSM 80-day obligations.
class VisitQueueScreen {
  final VisitsController controller;

  const VisitQueueScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? selectedType}) {
    final filtered = selectedType == null
        ? controller.obligations
        : controller.obligations.where((o) => o.obligationType == selectedType).toList();

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'total_obligations': controller.obligations.length,
      'filtered_count': filtered.length,
      'selected_type': selectedType ?? 'All',
      'obligation_types': [
        'All',
        'Buy & Sell Monthly',
        'SIS Monthly',
        'SIS Quarterly Stock Review',
        'RSM 80-Day',
        'Seasonal Prebooking',
      ],
      'obligations': filtered.map((o) => {
        'id': o.id,
        'type': o.obligationType,
        'customer': o.customer,
        'customer_name': o.customerName,
        'territory': o.territory,
        'due_date': o.dueDate.toIso8601String().substring(0, 10),
        'status': o.status,
        'is_overdue': o.isOverdue,
        'is_grace': o.isInGrace,
      }).toList(),
    };
  }
}
