// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../tokens/colors.dart';

/// Semantic Status Badge Token Specs.
class StatusBadgeSpec {
  final String label;
  final int backgroundColor;
  final int textColor;

  const StatusBadgeSpec({
    required this.label,
    required this.backgroundColor,
    required this.textColor,
  });

  static const verified = StatusBadgeSpec(
    label: 'VERIFIED',
    backgroundColor: 0xFFDCFCE7,
    textColor: ClothingColors.success,
  );

  static const offlineQueued = StatusBadgeSpec(
    label: 'QUEUED OFFLINE',
    backgroundColor: 0xFFFEF3C7,
    textColor: ClothingColors.warning,
  );

  static const conflict = StatusBadgeSpec(
    label: 'SYNC CONFLICT',
    backgroundColor: 0xFFFEE2E2,
    textColor: ClothingColors.error,
  );
}
