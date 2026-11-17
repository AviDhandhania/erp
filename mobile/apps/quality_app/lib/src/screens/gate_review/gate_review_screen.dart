// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/gate_review_controller.dart';
import '../../models/gate_review_bundle_model.dart';

/// Screen presenting high-risk Administrator gate review and strong reauthentication.
class GateReviewScreen {
  final GateReviewController controller;

  const GateReviewScreen({required this.controller});

  Map<String, dynamic> buildViewData({bool isOnline = true}) {
    final bundle = controller.activeBundle;

    if (bundle == null) {
      return {'state': 'empty', 'message': 'No gate review bundle loaded.'};
    }

    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'cycle_name': bundle.cycleName,
      'cycle_key': bundle.cycleKey,
      'gate': bundle.gate,
      'bundle_hash': bundle.bundleHash,
      'supplier': bundle.supplier,
      'item_code': bundle.itemCode,
      'item_name': bundle.itemName,
      'purchase_order': bundle.purchaseOrder,
      'reviewed_revisions': bundle.reviewedRevisions,
      'stage_summaries': bundle.stageSummaries,
      'is_online': isOnline,
      'status_message': controller.statusMessage,
      'error_message': controller.errorMessage,
      'security_invariants': {
        'online_required': true,
        'strong_reauth_required': true,
        'bundle_immutability': 'Bundle hash locks reviewed stage revisions against concurrent tampering.',
        'offline_block_notice': !isOnline
            ? 'OFFLINE: Administrator gate reviews are strictly BLOCKED while offline.'
            : null,
      },
      'supported_decisions': ['Approved', 'Rejected', 'Conditional'],
      'actions': [
        'enter_reauth_password',
        'set_decision_notes',
        'commit_gate_decision',
      ],
    };
  }
}
