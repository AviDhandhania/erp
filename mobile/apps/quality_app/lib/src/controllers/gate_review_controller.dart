// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/gate_review_bundle_model.dart';
import '../services/gate_review_manager.dart';

/// State controller for Administrator high-risk gate reviews on mobile.
class GateReviewController {
  final GateReviewManager gateReviewManager;

  GateReviewBundleModel? activeBundle;
  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  GateReviewController({required this.gateReviewManager});

  /// Loads gate review bundle for a production cycle.
  Future<void> loadGateBundle({
    required String cycleName,
    required String gate, // 'Production Go Ahead' | 'Final Inspection'
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      if (gate == 'Production Go Ahead') {
        activeBundle = await gateReviewManager.loadProductionGoAheadBundle(cycleName);
      } else {
        activeBundle = await gateReviewManager.loadFinalInspectionBundle(cycleName);
      }
    } catch (e) {
      errorMessage = 'Failed to load gate review bundle: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Commits Administrator gate decision requiring strong reauthentication.
  Future<bool> commitGateDecision({
    required String decision, // 'Approved' | 'Rejected' | 'Conditional'
    required String reauthPassword,
    String? notes,
    bool isOnline = true,
  }) async {
    if (activeBundle == null) {
      errorMessage = 'No active gate review bundle loaded.';
      return false;
    }

    if (!isOnline) {
      errorMessage = 'Offline: High-risk gate reviews cannot be performed offline. Online connectivity is required.';
      return false;
    }

    if (reauthPassword.trim().isEmpty) {
      errorMessage = 'Reauthentication required: Please enter your password or credential token.';
      return false;
    }

    isLoading = true;
    errorMessage = null;

    try {
      if (activeBundle!.isProductionGoAhead) {
        await gateReviewManager.decideProductionGoAhead(
          bundle: activeBundle!,
          decision: decision,
          notes: notes,
          reauthPassword: reauthPassword,
          isOnline: isOnline,
        );
      } else {
        await gateReviewManager.decideFinalInspection(
          bundle: activeBundle!,
          decision: decision,
          notes: notes,
          reauthPassword: reauthPassword,
          isOnline: isOnline,
        );
      }

      statusMessage = 'Gate review decision ($decision) committed successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Gate decision failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }
}
