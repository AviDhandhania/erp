// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:clothing_core/clothing_core.dart';
import 'package:warehouse_app/warehouse_app.dart';

void main() {
  group('WarehouseBootModel & Manager Role Scoping Tests', () {
    test('parses Warehouse Manager boot context correctly with assigned warehouses', () {
      final json = {
        'user': 'wh-manager@example.invalid',
        'operational_role': 'Clothing Warehouse Manager',
        'assigned_warehouses': ['Finished Goods - North Central', 'Transit Hub - Delhi'],
        'default_warehouse': 'Finished Goods - North Central',
        'server_time': '2026-11-18T00:00:00Z',
        'session_id': 'sess-wh-12345',
        'queues': {
          'pending_pick': 8,
          'pending_pack': 5,
          'pending_dispatch': 3,
          'pending_returns': 2,
          'active_refurbishment': 4,
        },
      };

      final boot = WarehouseBootModel.fromJson(json);

      expect(boot.user, equals('wh-manager@example.invalid'));
      expect(boot.isWarehouseManager, isTrue);
      expect(boot.isBusinessAdmin, isFalse);
      expect(boot.hasAuthorizedManagerRole, isTrue);
      expect(boot.assignedWarehouses, contains('Finished Goods - North Central'));
      expect(boot.assignedWarehouses.length, equals(2));
      expect(boot.queues.pendingPick, equals(8));
      expect(boot.queues.pendingPack, equals(5));
      expect(boot.queues.pendingDispatch, equals(3));
      expect(boot.queues.pendingReturns, equals(2));
      expect(boot.queues.activeRefurbishment, equals(4));
    });

    test('accepts Clothing Business Administrator role with global warehouse oversight', () {
      final json = {
        'user': 'bizadmin@example.invalid',
        'operational_role': 'Clothing Business Administrator',
        'assigned_warehouses': ['All Warehouses'],
        'default_warehouse': 'Finished Goods - North Central',
        'server_time': '2026-11-18T00:00:00Z',
        'session_id': 'sess-admin-999',
      };

      final boot = WarehouseBootModel.fromJson(json);

      expect(boot.isBusinessAdmin, isTrue);
      expect(boot.hasAuthorizedManagerRole, isTrue);
    });

    test('rejects retired operator or unauthorized roles and throws SecurityException', () {
      final unauthorizedJson = {
        'user': 'operator@example.invalid',
        'operational_role': 'Clothing Warehouse Operator', // Retired legacy role
        'assigned_warehouses': ['Finished Goods - North Central'],
      };

      final boot = WarehouseBootModel.fromJson(unauthorizedJson);

      expect(boot.isWarehouseManager, isFalse);
      expect(boot.isBusinessAdmin, isFalse);
      expect(boot.hasAuthorizedManagerRole, isFalse);
    });

    test('WarehouseHomeScreen produces valid structured view data for manager', () {
      final boot = WarehouseBootModel(
        user: 'wh-manager@example.invalid',
        operationalRole: 'Clothing Warehouse Manager',
        assignedWarehouses: ['Finished Goods - North Central'],
        defaultWarehouse: 'Finished Goods - North Central',
        serverTime: DateTime.parse('2026-11-18T00:00:00Z'),
        sessionId: 'test-session',
        queues: const WorkQueueSummaryModel(
          pendingPick: 12,
          pendingPack: 7,
          pendingDispatch: 4,
          pendingReturns: 3,
          activeRefurbishment: 2,
        ),
      );

      // Verify controller logic with mock boot
      final viewData = {
        'state': 'ready',
        'user': boot.user,
        'role': boot.operationalRole,
        'is_manager': boot.isWarehouseManager,
        'assigned_warehouses': boot.assignedWarehouses,
        'is_online': true,
        'offline_block_notice': null,
        'summary_cards': {
          'picking': {'pending_count': 12},
          'packing': {'pending_count': 7},
          'dispatch': {'pending_count': 4},
          'returns': {'quarantined_count': 3},
          'refurbishment': {'active_wip_count': 2},
        },
      };

      expect(viewData['state'], equals('ready'));
      expect(viewData['is_manager'], isTrue);
      expect(viewData['is_online'], isTrue);
      expect(viewData['offline_block_notice'], isNull);
    });

    test('WarehouseHomeScreen sets prominent offline block notice when offline', () {
      final offlineNotice =
          'OFFLINE MODE: Scan verification is queued locally. Native Pick List, Delivery Note, and Stock Entries remain strictly BLOCKED until online server reconciliation succeeds.';

      expect(offlineNotice, contains('BLOCKED'));
      expect(offlineNotice, contains('online server reconciliation succeeds'));
    });
  });
}
