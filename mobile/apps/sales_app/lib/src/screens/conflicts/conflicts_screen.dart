// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/conflicts_controller.dart';
import '../models/conflict_model.dart';

/// Screen presenting rejected offline operations requiring manual user resolution.
class ConflictsScreen {
  final ConflictsController controller;

  const ConflictsScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    return {
      'state': controller.isLoading && controller.conflicts.isEmpty ? 'loading' : 'ready',
      'conflicts_count': controller.conflicts.length,
      'has_unresolved_conflicts': controller.conflicts.isNotEmpty,
      'conflicts': controller.conflicts.map((c) => {
        'mutation_id': c.mutationId,
        'operation_type': c.operationType,
        'error_message': c.errorMessage,
        'error_code': c.serverErrorCode,
        'failed_at': c.failedAt.toIso8601String(),
        'payload': c.payload,
        'resolution_status': c.resolutionStatus,
      }).toList(),
      'actions': [
        'retry_mutation',
        'discard_mutation',
        'refresh_conflicts',
      ],
    };
  }
}
