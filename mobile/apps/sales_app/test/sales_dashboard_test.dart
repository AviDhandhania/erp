// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:sales_app/sales_app.dart';

void main() {
  group('SalesDashboardModel Tests', () {
    test('parses ASM dashboard correctly with territorial scope', () {
      final json = {
        'user': 'asm@example.invalid',
        'role': 'Clothing Area Sales Manager',
        'territories': ['North Zone - Delhi', 'North Zone - Punjab'],
        'server_time': '2026-11-17T12:00:00Z',
        'applications': {
          'pending': 3,
          'rfi': 1,
          'approved_this_month': 5,
        },
        'visits': {
          'completed_this_month': 18,
        },
        'cadence': {
          'rsm_overdue': 0,
          'rsm_grace': 1,
          'upcoming_obligations': 12,
        },
        'orders': {
          'draft_count': 4,
          'submitted_count': 14,
          'submitted_value': 450000.0,
        },
        'exposure': {
          'total_retailers': 42,
          'total_approved_limit': 5000000.0,
          'total_current_exposure': 3200000.0,
          'over_limit_count': 2,
        },
        'collections': {
          'count_90_120': 5,
          'total_amount': 280000.0,
          'blocked_retailers_count': 1,
        },
        'deliveries': {
          'pending_count': 3,
          'escalated_count': 0,
        },
      };

      final model = SalesDashboardModel.fromJson(json);

      expect(model.user, equals('asm@example.invalid'));
      expect(model.isASM, isTrue);
      expect(model.isRSM, isFalse);
      expect(model.assignedTerritories, contains('North Zone - Delhi'));
      expect(model.pendingApplications, equals(3));
      expect(model.rfiApplications, equals(1));
      expect(model.completedVisitsThisMonth, equals(18));
      expect(model.draftOrdersCount, equals(4));
      expect(model.submittedOrdersValue, equals(450000.0));
      expect(model.overdueInvoices90To120Days, equals(5));
      expect(model.hardBlockedRetailersCount, equals(1));
    });

    test('differentiates RSM supervisory role', () {
      final json = {
        'user': 'rsm@example.invalid',
        'role': 'Clothing Regional Sales Manager',
        'territories': ['North Zone'],
        'server_time': '2026-11-17T12:00:00Z',
      };

      final model = SalesDashboardModel.fromJson(json);
      expect(model.isRSM, isTrue);
      expect(model.isASM, isFalse);
    });
  });
}
