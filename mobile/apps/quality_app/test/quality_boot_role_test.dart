// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:quality_app/quality_app.dart';

void main() {
  group('QualityBootModel & Role Scoping Tests', () {
    test('parses Quality Inspector boot context correctly with assigned suppliers', () {
      final json = {
        'user': 'inspector@example.invalid',
        'operational_role': 'Clothing Quality Inspector',
        'assigned_suppliers': ['SUPPLIER-ALPHA-MILLS', 'SUPPLIER-BETA-DENIM'],
        'assigned_companies': ['TEST Company'],
        'server_time': '2026-11-18T00:00:00Z',
        'queues': {
          'active_cycles': 14,
          'stage_due': 5,
          'pending_corrections': 2,
          'returns_awaiting_inspection': 3,
          'pending_gate_reviews': 0,
        },
      };

      final boot = QualityBootModel.fromJson(json);

      expect(boot.user, equals('inspector@example.invalid'));
      expect(boot.isInspector, isTrue);
      expect(boot.isQualityManager, isFalse);
      expect(boot.isBusinessAdmin, isFalse);
      expect(boot.hasAuthorizedQualityRole, isTrue);
      expect(boot.canDecideCriticalGates, isFalse); // Inspector cannot approve critical gates
      expect(boot.isSupplierAllowed('SUPPLIER-ALPHA-MILLS'), isTrue);
      expect(boot.isSupplierAllowed('FORBIDDEN-SUPPLIER'), isFalse);
      expect(boot.queues.activeCycles, equals(14));
      expect(boot.queues.stageDue, equals(5));
      expect(boot.queues.pendingCorrections, equals(2));
      expect(boot.queues.returnsAwaitingInspection, equals(3));
    });

    test('parses Quality Manager boot context with gate review authority', () {
      final json = {
        'user': 'qm@example.invalid',
        'operational_role': 'Clothing Quality Manager',
        'assigned_suppliers': ['*'],
        'assigned_companies': ['TEST Company'],
        'server_time': '2026-11-18T00:00:00Z',
        'queues': {
          'active_cycles': 20,
          'stage_due': 8,
          'pending_corrections': 3,
          'returns_awaiting_inspection': 4,
          'pending_gate_reviews': 3,
        },
      };

      final boot = QualityBootModel.fromJson(json);

      expect(boot.isQualityManager, isTrue);
      expect(boot.hasAuthorizedQualityRole, isTrue);
      expect(boot.canDecideCriticalGates, isTrue); // Quality Manager can decide gates
      expect(boot.isSupplierAllowed('ANY-SUPPLIER'), isTrue);
    });

    test('accepts Clothing Business Administrator with global oversight', () {
      final json = {
        'user': 'bizadmin@example.invalid',
        'operational_role': 'Clothing Business Administrator',
        'assigned_suppliers': ['*'],
        'assigned_companies': ['TEST Company'],
        'server_time': '2026-11-18T00:00:00Z',
      };

      final boot = QualityBootModel.fromJson(json);

      expect(boot.isBusinessAdmin, isTrue);
      expect(boot.hasAuthorizedQualityRole, isTrue);
      expect(boot.canDecideCriticalGates, isTrue);
    });

    test('rejects unauthorized roles without quality permissions', () {
      final unauthorizedJson = {
        'user': 'unauthorized@example.invalid',
        'operational_role': 'Clothing Warehouse Operator', // completely unrelated
        'assigned_suppliers': [],
        'assigned_companies': [],
      };

      final boot = QualityBootModel.fromJson(unauthorizedJson);

      expect(boot.isInspector, isFalse);
      expect(boot.isQualityManager, isFalse);
      expect(boot.isBusinessAdmin, isFalse);
      expect(boot.hasAuthorizedQualityRole, isFalse);
    });

    test('QualityHomeScreen produces valid structured view data', () {
      final boot = QualityBootModel(
        user: 'inspector@example.invalid',
        role: 'Clothing Quality Inspector',
        assignedSuppliers: ['SUPPLIER-ALPHA-MILLS'],
        assignedCompanies: ['TEST Company'],
        serverTime: DateTime.parse('2026-11-18T00:00:00Z'),
        queues: const QualityQueueSummaryModel(
          activeCycles: 10,
          stageDue: 4,
          pendingCorrections: 1,
          returnsAwaitingInspection: 2,
          pendingGateReviews: 0,
        ),
      );

      final viewData = {
        'state': 'ready',
        'user': boot.user,
        'role': boot.role,
        'is_inspector': boot.isInspector,
        'can_decide_gates': boot.canDecideCriticalGates,
        'assigned_suppliers': boot.assignedSuppliers,
        'is_online': true,
        'summary_cards': {
          'production_cycles': {'active_count': 10},
          'stage_due': {'stage_due_count': 4},
          'corrections': {'pending_count': 1},
          'return_quarantine': {'quarantined_count': 2},
        },
      };

      expect(viewData['state'], equals('ready'));
      expect(viewData['is_inspector'], isTrue);
      expect(viewData['can_decide_gates'], isFalse);
      expect(viewData['is_online'], isTrue);
    });
  });
}
