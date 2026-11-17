// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/collections_controller.dart';
import '../models/collection_model.dart';

/// Screen presenting the territory-scoped 90–120 day collection worklist based on native ERPNext
/// Accounts Receivable data.
///
/// Security:
/// Zero payment secrets, credit card credentials, or parallel ledgers.
class CollectionWorklistScreen {
  final CollectionsController controller;

  const CollectionWorklistScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? selectedFilter}) {
    final list = controller.invoices;

    return {
      'state': controller.isLoading && list.isEmpty ? 'loading' : 'ready',
      'total_invoices': list.length,
      'valid_outcomes': CollectionFollowUpOutcome.validOutcomes,
      'security_disclaimer': 'This worklist records supervisory visit outcomes only. Never request, collect, or store payment instruments or online banking credentials.',
      'invoices': list.map((i) => {
        'invoice_no': i.invoiceNo,
        'customer': i.customer,
        'customer_name': i.customerName,
        'territory': i.territory,
        'posting_date': i.postingDate.toIso8601String().substring(0, 10),
        'due_date': i.dueDate.toIso8601String().substring(0, 10),
        'grand_total': i.grandTotal,
        'outstanding_amount': i.outstandingAmount,
        'days_overdue': i.daysOverdue,
        'is_warning_window': i.isWarningWindow,
        'is_hard_blocked': i.isHardBlocked,
        'last_outcome': i.lastFollowUpOutcome,
        'last_follow_up_date': i.lastFollowUpDate?.toIso8601String(),
      }).toList(),
      'actions': [
        'record_follow_up_outcome',
        'refresh_worklist',
      ],
    };
  }
}
