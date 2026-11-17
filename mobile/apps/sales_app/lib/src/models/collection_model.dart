// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// 90–120 day overdue invoice representation from native ERPNext Accounts Receivable.
///
/// Security & Accounting Invariant:
/// This model is strictly an operational worklist view. It never creates parallel ledgers
/// and MUST NEVER store or collect payment card numbers, CVVs, or online banking secrets.
@immutable
class CollectionInvoiceModel {
  final String invoiceNo; // Sales Invoice name
  final String customer;
  final String customerName;
  final String territory;
  final DateTime postingDate;
  final DateTime dueDate;
  final double grandTotal;
  final double outstandingAmount;
  final int daysOverdue;
  final String? paymentTerms;
  final String? lastFollowUpOutcome;
  final DateTime? lastFollowUpDate;

  const CollectionInvoiceModel({
    required this.invoiceNo,
    required this.customer,
    required this.customerName,
    required this.territory,
    required this.postingDate,
    required this.dueDate,
    required this.grandTotal,
    required this.outstandingAmount,
    required this.daysOverdue,
    this.paymentTerms,
    this.lastFollowUpOutcome,
    this.lastFollowUpDate,
  });

  /// Invoices in 90–120 day window trigger operational reminders and escalated ASM contact.
  bool get isWarningWindow => daysOverdue >= 90 && daysOverdue < 120;

  /// Invoices exceeding 120 days trigger native order blocking according to settings.
  bool get isHardBlocked => daysOverdue >= 120;

  factory CollectionInvoiceModel.fromJson(Map<String, dynamic> json) => CollectionInvoiceModel(
    invoiceNo: json['name'] as String? ?? json['invoice_no'] as String? ?? '',
    customer: json['customer'] as String? ?? '',
    customerName: json['customer_name'] as String? ?? '',
    territory: json['territory'] as String? ?? '',
    postingDate: DateTime.tryParse(json['posting_date'] as String? ?? '') ?? DateTime.now(),
    dueDate: DateTime.tryParse(json['due_date'] as String? ?? '') ?? DateTime.now(),
    grandTotal: (json['grand_total'] as num?)?.toDouble() ?? 0.0,
    outstandingAmount: (json['outstanding_amount'] as num?)?.toDouble() ?? 0.0,
    daysOverdue: json['days_overdue'] as int? ?? (json['age_days'] as num?)?.toInt() ?? 0,
    paymentTerms: json['payment_terms_template'] as String?,
    lastFollowUpOutcome: json['last_outcome'] as String?,
    lastFollowUpDate: DateTime.tryParse(json['last_follow_up_date'] as String? ?? ''),
  );

  Map<String, dynamic> toJson() => {
    'name': invoiceNo,
    'customer': customer,
    'customer_name': customerName,
    'territory': territory,
    'posting_date': postingDate.toIso8601String().substring(0, 10),
    'due_date': dueDate.toIso8601String().substring(0, 10),
    'grand_total': grandTotal,
    'outstanding_amount': outstandingAmount,
    'days_overdue': daysOverdue,
    'payment_terms_template': paymentTerms,
    'last_outcome': lastFollowUpOutcome,
    'last_follow_up_date': lastFollowUpDate?.toIso8601String(),
  };
}

/// Operational collection follow-up outcome payload.
@immutable
class CollectionFollowUpOutcome {
  static const validOutcomes = <String>[
    'Payment Promised',
    'Cheque Collected',
    'Dispute / Reconciliation Needed',
    'Retailer Unavailable',
    'Escalated to RSM',
  ];

  final String invoiceNo;
  final String customer;
  final String outcome; // One of validOutcomes
  final String? notes;
  final DateTime? expectedPaymentDate;

  const CollectionFollowUpOutcome({
    required this.invoiceNo,
    required this.customer,
    required this.outcome,
    this.notes,
    this.expectedPaymentDate,
  });

  Map<String, dynamic> toJson() => {
    'invoice': invoiceNo,
    'customer': customer,
    'outcome': outcome,
    'notes': notes,
    'expected_payment_date': expectedPaymentDate?.toIso8601String().substring(0, 10),
  };
}
