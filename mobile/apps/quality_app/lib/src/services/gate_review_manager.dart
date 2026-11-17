// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/gate_review_bundle_model.dart';
import 'quality_api_service.dart';

/// Manages high-risk Administrator gate reviews on mobile.
///
/// Security & Architectural Invariants:
/// - Administrator gate decisions on mobile strictly require online connectivity;
///   offline gate decisions are strictly BLOCKED.
/// - Requires an exact immutable review bundle with SHA-256 fingerprint validation.
/// - Requires strong online reauthentication before committing high-risk gate approvals.
class GateReviewManager {
  final QualityApiService apiService;

  GateReviewManager({required this.apiService});

  /// Fetches immutable review bundle for Production Go Ahead gate.
  Future<GateReviewBundleModel> loadProductionGoAheadBundle(String cycleName) async {
    return apiService.getProductionGoAheadBundle(cycleName: cycleName);
  }

  /// Fetches immutable review bundle for Final Inspection gate.
  Future<GateReviewBundleModel> loadFinalInspectionBundle(String cycleName) async {
    return apiService.getFinalInspectionBundle(cycleName: cycleName);
  }

  /// Commits Administrator decision for Production Go Ahead gate.
  ///
  /// Invariants:
  /// - Strictly BLOCKED if offline.
  /// - Strictly BLOCKED if reauthPassword is empty or invalid.
  /// - Validates bundleHash to detect revision changes during review.
  Future<Map<String, dynamic>> decideProductionGoAhead({
    required GateReviewBundleModel bundle,
    required String decision, // 'Approved' | 'Rejected' | 'Conditional'
    String? notes,
    required String reauthPassword,
    bool isOnline = true,
  }) async {
    if (!isOnline) {
      throw StateError(
        'Offline: High-risk gate reviews strictly require online connectivity and cannot be approved offline.',
      );
    }

    if (reauthPassword.trim().isEmpty) {
      throw ArgumentError(
        'Strong reauthentication required: Password or security token must be supplied for gate decisions.',
      );
    }

    final requestId = 'pga-dec-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.decideProductionGoAhead(
      cycleName: bundle.cycleName,
      decision: decision,
      bundleHash: bundle.bundleHash,
      notes: notes,
      reauthPassword: reauthPassword,
      requestId: requestId,
    );
  }

  /// Commits Administrator decision for Final Inspection gate.
  Future<Map<String, dynamic>> decideFinalInspection({
    required GateReviewBundleModel bundle,
    required String decision,
    String? notes,
    required String reauthPassword,
    bool isOnline = true,
  }) async {
    if (!isOnline) {
      throw StateError(
        'Offline: Final Inspection gate decisions strictly require online connectivity.',
      );
    }

    if (reauthPassword.trim().isEmpty) {
      throw ArgumentError(
        'Strong reauthentication required: Password or security token must be supplied for gate decisions.',
      );
    }

    final requestId = 'fi-dec-${DateTime.now().microsecondsSinceEpoch}';
    return apiService.decideFinalInspection(
      cycleName: bundle.cycleName,
      decision: decision,
      bundleHash: bundle.bundleHash,
      notes: notes,
      reauthPassword: reauthPassword,
      requestId: requestId,
    );
  }
}
