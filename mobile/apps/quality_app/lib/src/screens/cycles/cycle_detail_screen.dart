// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/cycles_controller.dart';
import '../../models/production_cycle_model.dart';

/// Screen presenting details, stage timeline, and gate status for a specific Production Cycle.
class CycleDetailScreen {
  final CyclesController controller;

  const CycleDetailScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    final cycle = controller.selectedCycle;

    if (cycle == null) {
      return {'state': 'empty', 'message': 'No production cycle selected.'};
    }

    final stagesTimeline = List.generate(qualityStages.length, (index) {
      final stageNum = index + 1;
      final stageName = qualityStages[index];
      final isCompleted = stageNum < cycle.currentStage;
      final isCurrent = stageNum == cycle.currentStage;
      final isUpcoming = stageNum > cycle.currentStage;

      return {
        'stage_number': stageNum,
        'stage_name': stageName,
        'status': isCompleted ? 'Completed' : (isCurrent ? 'Current' : 'Upcoming'),
        'is_gate_review': stageNum == 4 || stageNum == 7,
      };
    });

    return {
      'state': 'ready',
      'cycle_key': cycle.cycleKey,
      'supplier': cycle.supplier,
      'item_code': cycle.itemCode,
      'item_name': cycle.itemName,
      'purchase_order': cycle.purchaseOrder,
      'production_lot': cycle.productionLot,
      'season': cycle.season,
      'company': cycle.company,
      'current_stage': cycle.currentStage,
      'current_stage_name': cycle.currentStageName,
      'status': cycle.status,
      'gate_review_status': cycle.gateReviewStatus,
      'requires_gate_review': cycle.requiresGateReview,
      'is_blocked_for_gate': controller.cycleManager.isCycleBlockedForGate(cycle),
      'gate_block_notice': controller.cycleManager.isCycleBlockedForGate(cycle)
          ? 'Production progression is BLOCKED pending Administrator ${cycle.currentStageName} review.'
          : null,
      'stages_timeline': stagesTimeline,
      'actions': [
        'start_stage_inspection',
        'view_stage_reports',
        'view_controlled_pdf',
        if (cycle.requiresGateReview) 'open_gate_review',
      ],
    };
  }
}
