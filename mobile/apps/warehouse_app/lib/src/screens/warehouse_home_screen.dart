// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/warehouse_home_controller.dart';

/// Role-aware Home Dashboard screen for Clothing Warehouse Managers.
///
/// Features:
/// - Assigned warehouse scoping (only permitted warehouses).
/// - Manager-only verification banner.
/// - Work queue summary cards: Picking, Packing, Dispatch, Returns, Refurbishment.
/// - Prominent offline indicator asserting that stock transitions are blocked offline.
/// - Connected printer status and offline conflicts alert.
class WarehouseHomeScreen {
  final WarehouseHomeController controller;

  const WarehouseHomeScreen({required this.controller});

  /// Builds a structured view of the warehouse manager dashboard.
  Map<String, dynamic> buildViewData() {
    final boot = controller.bootContext;

    if (controller.isLoading) {
      return {'state': 'loading', 'message': 'Loading warehouse manager session...'};
    }

    if (controller.errorMessage != null && boot == null) {
      return {'state': 'error', 'error': controller.errorMessage};
    }

    if (boot == null) {
      return {'state': 'unauthorized', 'message': 'Warehouse Manager authorization required.'};
    }

    return {
      'state': 'ready',
      'user': boot.user,
      'role': boot.operationalRole,
      'is_manager': boot.isWarehouseManager,
      'assigned_warehouses': boot.assignedWarehouses,
      'selected_warehouse': controller.selectedWarehouse,
      'is_online': controller.isOnline,
      'offline_block_notice': controller.isOnline
          ? null
          : 'OFFLINE MODE: Scan verification is queued locally. Native Pick List, Delivery Note, and Stock Entries remain strictly BLOCKED until online server reconciliation succeeds.',
      'summary_cards': {
        'picking': {
          'title': 'Picking Queue',
          'pending_count': controller.pendingPickCount,
          'action': 'open_pick_queue',
        },
        'packing': {
          'title': 'Packing & Measurements',
          'pending_count': controller.pendingPackCount,
          'action': 'open_pack_queue',
        },
        'dispatch': {
          'title': 'Carrier Dispatch & Handoff',
          'pending_count': controller.pendingDispatchCount,
          'action': 'open_dispatch_queue',
        },
        'returns': {
          'title': 'Customer Returns Intake',
          'quarantined_count': controller.pendingReturnsCount,
          'action': 'open_returns_intake',
        },
        'refurbishment': {
          'title': 'Refurbishment & Reinspection',
          'active_wip_count': controller.activeRefurbishmentCount,
          'action': 'open_refurbishment_queue',
        },
      },
      'conflicts_count': controller.unresolvedConflictsCount,
      'quick_actions': [
        'start_picking',
        'carton_packing',
        'carrier_manifest',
        'intake_return',
        'manage_printer',
        if (controller.unresolvedConflictsCount > 0) 'resolve_conflicts',
      ],
    };
  }
}
