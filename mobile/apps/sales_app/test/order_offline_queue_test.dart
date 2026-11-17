// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:sales_app/sales_app.dart';

void main() {
  group('Order Offline Queue & Conflict Model Tests', () {
    test('sales order model parses draft, submitted, and rejected states', () {
      final json = {
        'name': 'SO-2026-0042',
        'customer': 'CUST-002',
        'customer_name': 'Royal Garments',
        'transaction_date': '2026-11-17',
        'delivery_date': '2026-11-20',
        'total_qty': 50,
        'currency': 'INR',
        'grand_total': 65000.0,
        'docstatus': 0,
        'status': 'Draft',
        'custom_clothing_rejection_reason': 'Credit limit exceeded on server review.',
        'custom_clothing_request_id': 'idemp-uuid-445566',
      };

      final order = SalesOrderModel.fromJson(json);

      expect(order.id, equals('SO-2026-0042'));
      expect(order.isDraft, isTrue);
      expect(order.isRejected, isTrue);
      expect(order.rejectionReason, contains('Credit limit exceeded'));
      expect(order.requestId, equals('idemp-uuid-445566'));
    });

    test('conflict model manages offline sync rejection details and resolution state', () {
      final conflict = ConflictModel(
        mutationId: 'uuid-mut-001',
        operationType: 'create_mobile_order',
        payload: {
          'customer': 'CUST-003',
          'items': [{'item_code': 'JEANS-SLIM-32', 'qty': 100}],
        },
        errorMessage: 'Overdue invoice exceeds 120-day collection escalation threshold.',
        serverErrorCode: 'COLLECTION_HARD_BLOCK',
        failedAt: DateTime.now(),
      );

      expect(conflict.isUnresolved, isTrue);
      expect(conflict.serverErrorCode, equals('COLLECTION_HARD_BLOCK'));

      final retried = conflict.copyWith(resolutionStatus: 'Retried');
      expect(retried.isUnresolved, isFalse);
      expect(retried.resolutionStatus, equals('Retried'));
    });
  });
}
