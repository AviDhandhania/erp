// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/quality_home_controller.dart';

/// Role-aware Home Dashboard screen for Quality Inspectors, Managers, and Administrators.
class QualityHomeScreen {
  final QualityHomeController controller;

  const QualityHomeScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final boot = controller.bootContext;

    if (controller.isLoading) {
      return {'state': 'loading', 'message': 'Loading quality inspector session...'};
    }

    if (controller.errorMessage != null && boot == null) {
      return {'state': 'error', 'error': controller.errorMessage};
    }

    if (boot == null) {
      return {'state': 'unauthorized', 'message': 'Quality authorization required.'};
    }

    return {
      'state': 'ready',
      'user': boot.user,
      'role': boot.role,
      'is_inspector': boot.isInspector,
      'is_quality_manager': boot.isQualityManager,
      'is_business_admin': boot.isBusinessAdmin,
      'can_decide_gates': boot.canDecideCriticalGates,
      'assigned_suppliers': boot.assignedSuppliers,
      'assigned_companies': boot.assignedCompanies,
      'is_online': controller.isOnline,
      'summary_cards': {
        'production_cycles': {
          'title': 'Active Production Cycles',
          'active_count': controller.activeCyclesCount,
          'action': 'open_cycles_queue',
        },
        'stage_due': {
          'title': 'Stages Due for Inspection',
          'stage_due_count': controller.stageDueCount,
          'action': 'open_stage_due_queue',
        },
        'corrections': {
          'title': 'Pending Corrections & Resubmissions',
          'pending_count': controller.pendingCorrectionsCount,
          'action': 'open_corrections_queue',
        },
        'return_quarantine': {
          'title': 'Customer Returns Awaiting Quality',
          'quarantined_count': controller.returnsAwaitingInspectionCount,
          'action': 'open_quarantine_queue',
        },
        'gate_reviews': {
          'title': 'Administrator Gate Reviews',
          'pending_count': controller.pendingGateReviewsCount,
          'action': 'open_gate_reviews',
          'enabled': boot.canDecideCriticalGates,
        },
      },
      'quick_actions': [
        'start_stage_inspection',
        'browse_cycles',
        'quarantine_dispositions',
        if (boot.canDecideCriticalGates) 'review_gates',
      ],
    };
  }
}
