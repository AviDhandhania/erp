// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Accessible Button Specifications adhering to 48x48 dp minimum touch target.
class ButtonSpec {
  final double minHeight;
  final double minWidth;
  final double cornerRadius;
  final double paddingHorizontal;

  const ButtonSpec({
    this.minHeight = 48.0,
    this.minWidth = 48.0,
    this.cornerRadius = 8.0,
    this.paddingHorizontal = 16.0,
  });

  static const primary = ButtonSpec(minHeight: 52.0, cornerRadius: 10.0);
  static const compact = ButtonSpec(minHeight: 48.0, cornerRadius: 6.0);
}
