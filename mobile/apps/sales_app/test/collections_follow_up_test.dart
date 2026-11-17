// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:sales_app/sales_app.dart';

void main() {
  group('Collections & Delivery Follow-Up Tests', () {
    test('collection invoice correctly computes 90-120 day warning and 120-day hard block', () {
      final invoice95Days = CollectionInvoiceModel(
        invoiceNo: 'ACC-SINV-2026-0010',
        customer: 'CUST-004',
        customerName: 'Trendz Apparel',
        territory: 'Bangalore Central',
        postingDate: DateTime(2026, 8, 14),
        dueDate: DateTime(2026, 9, 14),
        grandTotal: 150000.0,
        outstandingAmount: 150000.0,
        daysOverdue: 95,
      );

      expect(invoice95Days.isWarningWindow, isTrue);
      expect(invoice95Days.isHardBlocked, isFalse);

      final invoice125Days = CollectionInvoiceModel(
        invoiceNo: 'ACC-SINV-2026-0005',
        customer: 'CUST-005',
        customerName: 'Elite Fashion',
        territory: 'Bangalore West',
        postingDate: DateTime(2026, 7, 10),
        dueDate: DateTime(2026, 8, 10),
        grandTotal: 300000.0,
        outstandingAmount: 200000.0,
        daysOverdue: 125,
      );

      expect(invoice125Days.isWarningWindow, isFalse);
      expect(invoice125Days.isHardBlocked, isTrue);
    });

    test('validates collection follow up outcome choices', () {
      expect(CollectionFollowUpOutcome.validOutcomes, contains('Payment Promised'));
      expect(CollectionFollowUpOutcome.validOutcomes, contains('Cheque Collected'));
      expect(CollectionFollowUpOutcome.validOutcomes, contains('Dispute / Reconciliation Needed'));
      expect(CollectionFollowUpOutcome.validOutcomes, contains('Retailer Unavailable'));
      expect(CollectionFollowUpOutcome.validOutcomes, contains('Escalated to RSM'));
    });

    test('delivery follow up parses package barcodes and models outcome escalation', () {
      final json = {
        'name': 'DFU-2026-0001',
        'delivery_note': 'MAT-DN-2026-0012',
        'sales_order': 'SO-2026-0033',
        'customer': 'CUST-006',
        'customer_name': 'Urban Wear',
        'territory': 'Chennai North',
        'delivery_date': '2026-11-15',
        'carrier': 'BlueDart',
        'tracking_no': 'BD123456789',
        'carton_count': 3,
        'status': 'Pending Contact',
        'package_barcodes': ['PKG-DN0012-01', 'PKG-DN0012-02', 'PKG-DN0012-03'],
      };

      final delivery = DeliveryFollowUpModel.fromJson(json);

      expect(delivery.id, equals('DFU-2026-0001'));
      expect(delivery.cartonCount, equals(3));
      expect(delivery.packageBarcodes.length, equals(3));
      expect(delivery.packageBarcodes, contains('PKG-DN0012-02'));
      expect(delivery.isPending, isTrue);
    });
  });
}
