// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:async';

/// Supported Scanner Sources.
enum ScannerSource {
  camera('camera'),
  keyboardWedge('keyboard_wedge'),
  broadcastIntent('broadcast_intent'),
  manual('manual');

  final String value;
  const ScannerSource(this.value);
}

/// Normalized Scan Event payload.
class MobileScanEvent {
  final String rawText;
  final String normalizedText;
  final ScannerSource source;
  final DateTime timestamp;

  MobileScanEvent({
    required this.rawText,
    required this.normalizedText,
    required this.source,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now().toUtc();
}

/// Abstract Hardware Feedback Delegate (Audio, Haptic, Flash).
abstract class ScannerFeedbackDelegate {
  Future<void> onScanSuccess();
  Future<void> onScanError();
}

/// Unified Mobile Scanner Controller.
///
/// Features:
/// - Fast keyboard-wedge hardware scanner buffer detection (<50ms inter-character interval).
/// - Configurable debounce (1500ms default) and duplicate suppression.
/// - Continuous scanning mode.
/// - Multi-sensory feedback integration.
class MobileScannerController {
  final Duration debounceWindow;
  final bool suppressDuplicates;
  final ScannerFeedbackDelegate? feedbackDelegate;

  bool _isTorchOn = false;
  bool _isContinuous = false;
  String? _lastScannedBarcode;
  DateTime? _lastScanTime;

  // Keyboard wedge buffer state
  final StringBuffer _keyBuffer = StringBuffer();
  DateTime _lastKeyTime = DateTime.fromMillisecondsSinceEpoch(0);
  static const int _wedgeMaxInterCharMs = 50;

  final _scanEventController = StreamController<MobileScanEvent>.broadcast();
  Stream<MobileScanEvent> get scanStream => _scanEventController.stream;

  bool get isTorchOn => _isTorchOn;
  bool get isContinuous => _isContinuous;

  MobileScannerController({
    this.debounceWindow = const Duration(milliseconds: 1500),
    this.suppressDuplicates = true,
    this.feedbackDelegate,
  });

  /// Ingest raw text from camera or manual entry.
  void ingestScan(String rawText, {ScannerSource source = ScannerSource.camera}) {
    final clean = rawText.trim();
    if (clean.isEmpty) return;

    final now = DateTime.now().toUtc();

    // 1. Debounce and Duplicate Suppression
    if (_lastScanTime != null) {
      final elapsed = now.difference(_lastScanTime!);
      if (elapsed < debounceWindow) {
        if (suppressDuplicates && clean == _lastScannedBarcode) {
          // Suppress duplicate within debounce window
          return;
        }
      }
    }

    _lastScannedBarcode = clean;
    _lastScanTime = now;

    // Trigger success feedback
    feedbackDelegate?.onScanSuccess();

    final event = MobileScanEvent(
      rawText: rawText,
      normalizedText: clean,
      source: source,
      timestamp: now,
    );

    _scanEventController.add(event);
  }

  /// Ingest individual key characters from physical keyboard wedge scanner.
  void handleRawKeyInput(String character) {
    final now = DateTime.now().toUtc();
    final elapsedMs = now.difference(_lastKeyTime).inMilliseconds;
    _lastKeyTime = now;

    // If typing was too slow (>50ms between keys), reset buffer
    if (elapsedMs > _wedgeMaxInterCharMs && _keyBuffer.isNotEmpty) {
      _keyBuffer.clear();
    }

    if (character == '\n' || character == '\r') {
      // End-of-scan delimiter received from wedge
      final barcode = _keyBuffer.toString().trim();
      _keyBuffer.clear();
      if (barcode.isNotEmpty) {
        ingestScan(barcode, source: ScannerSource.keyboardWedge);
      }
    } else {
      _keyBuffer.write(character);
    }
  }

  /// Ingest OEM broadcast intent (Zebra DataWedge, Honeywell Edge).
  void handleBroadcastIntentBarcode(String barcode) {
    ingestScan(barcode, source: ScannerSource.broadcastIntent);
  }

  void toggleTorch() {
    _isTorchOn = !_isTorchOn;
  }

  void setContinuousMode(bool continuous) {
    _isContinuous = continuous;
  }

  void triggerErrorFeedback() {
    feedbackDelegate?.onScanError();
  }

  void dispose() {
    _scanEventController.close();
  }
}
