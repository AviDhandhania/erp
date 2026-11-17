// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Scanner Viewfinder Visual Specification.
class ScannerViewfinderSpec {
  final double windowWidth;
  final double windowHeight;
  final double cornerLength;
  final double cornerThickness;
  final int laserColor;
  final int borderColor;
  final bool showLaserLine;

  const ScannerViewfinderSpec({
    this.windowWidth = 280.0,
    this.windowHeight = 180.0,
    this.cornerLength = 24.0,
    this.cornerThickness = 4.0,
    this.laserColor = 0xFFEF4444,
    this.borderColor = 0xFFFFFFFF,
    this.showLaserLine = true,
  });

  static const warehouse = ScannerViewfinderSpec(
    windowWidth: 320.0,
    windowHeight: 160.0,
  );

  static const qrCode = ScannerViewfinderSpec(
    windowWidth: 240.0,
    windowHeight: 240.0,
  );
}
