// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:async';
import 'auth_manager.dart';
import 'secure_storage.dart';

/// Session State Transitions.
enum SessionState {
  unauthenticated,
  authenticated,
  lockedDueToInactivity,
  revoked,
}

/// Orchestrates Session Inactivity, Token Rotation, and Remote Wipe.
class SessionLifecycleManager {
  final ClothingAuthManager authManager;
  final ClothingSecureStorage secureStorage;
  final Duration inactivityTimeout;
  final Future<void> Function()? onLocalDataWipeRequested;

  DateTime _lastInteractionTime;
  Timer? _inactivityCheckTimer;
  SessionState _currentState = SessionState.unauthenticated;

  final _stateController = StreamController<SessionState>.broadcast();
  Stream<SessionState> get stateStream => _stateController.stream;
  SessionState get currentState => _currentState;

  SessionLifecycleManager({
    required this.authManager,
    required this.secureStorage,
    this.inactivityTimeout = const Duration(minutes: 15),
    this.onLocalDataWipeRequested,
  }) : _lastInteractionTime = DateTime.now().toUtc() {
    _startInactivityTimer();
  }

  void _startInactivityTimer() {
    _inactivityCheckTimer?.cancel();
    _inactivityCheckTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      checkInactivity();
    });
  }

  /// Record user interaction (tap, scan, keypress) to reset the inactivity timer.
  void recordUserActivity() {
    _lastInteractionTime = DateTime.now().toUtc();
    if (_currentState == SessionState.lockedDueToInactivity) {
      // Transitioning out of lock requires authentication re-verification
    }
  }

  /// Evaluate if current session exceeded inactivity boundary.
  void checkInactivity() {
    if (_currentState != SessionState.authenticated) return;

    final elapsed = DateTime.now().toUtc().difference(_lastInteractionTime);
    if (elapsed > inactivityTimeout) {
      _currentState = SessionState.lockedDueToInactivity;
      _stateController.add(_currentState);
    }
  }

  /// Set the active session state to authenticated.
  void markAuthenticated() {
    _lastInteractionTime = DateTime.now().toUtc();
    _currentState = SessionState.authenticated;
    _stateController.add(_currentState);
  }

  /// Wipe all credentials, encrypted databases, and temporary artifacts.
  ///
  /// Executed on:
  /// 1. User manual logout.
  /// 2. Remote administrator revocation (401 with revocation signal).
  /// 3. Exceeded PIN/Biometric unlock failure threshold.
  Future<void> wipeSessionAndCache() async {
    _inactivityCheckTimer?.cancel();
    _currentState = SessionState.unauthenticated;
    _stateController.add(_currentState);

    // 1. Revoke on server & wipe Keychain/Keystore
    await authManager.revokeAndLogout();

    // 2. Invoke local encrypted database & photo cache wipe callback
    if (onLocalDataWipeRequested != null) {
      try {
        await onLocalDataWipeRequested!();
      } catch (_) {
        // Continue even if local file removal throws
      }
    }
  }

  void dispose() {
    _inactivityCheckTimer?.cancel();
    _stateController.close();
  }
}
