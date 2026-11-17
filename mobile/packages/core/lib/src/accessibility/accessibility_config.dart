// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Accessibility Guidelines and Metrics for Mobile Suite.
///
/// Follows WCAG 2.1 AA and Section 508 standards:
/// - Minimum interactive touch target: 48x48 dp.
/// - Text contrast ratio: at least 4.5:1 for normal text, 3:1 for large text.
/// - High-contrast mode: at least 7:1 contrast ratio.
/// - Screen reader accessibility labels and ARIA live regions.
class ClothingAccessibilityConfig {
  /// Minimum recommended interactive touch target dimension (in density-independent pixels).
  static const double minTouchTargetSize = 48.0;

  /// High Contrast Color Palette.
  static const int highContrastBackground = 0xFF000000;
  static const int highContrastSurface = 0xFF121212;
  static const int highContrastText = 0xFFFFFFFF;
  static const int highContrastAccent = 0xFFFFD700; // Gold for maximum contrast against black
  static const int highContrastError = 0xFFFF3B30;

  /// Semantic role announcements for screen readers.
  static String formatBarcodeAnnouncement(String barcode, String itemDescription) {
    return 'Barcode $barcode scanned for item $itemDescription.';
  }

  static String formatErrorAnnouncement(String errorMessage) {
    return 'Error alert: $errorMessage';
  }
}
