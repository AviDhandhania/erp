// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Shared Design System Color Tokens.
class ClothingColors {
  // Brand Palettes
  static const int brandPrimary = 0xFF1E3A8A; // Deep Indigo (Enterprise authority)
  static const int brandSecondary = 0xFF0284C7; // Sky Blue
  static const int brandAccent = 0xFF0D9488; // Teal

  // Semantic Status Colors
  static const int success = 0xFF16A34A; // Verified Green (Valid scan, submitted order)
  static const int warning = 0xFFD97706; // Amber (Offline queued, pending review)
  static const int error = 0xFFDC2626; // Crimson Red (Scan mismatch, conflict)
  static const int info = 0xFF2563EB; // Royal Blue

  // Light Theme Neutrals
  static const int lightBackground = 0xFFF8FAFC;
  static const int lightSurface = 0xFFFFFFFF;
  static const int lightBorder = 0xFFE2E8F0;
  static const int lightTextPrimary = 0xFF0F172A;
  static const int lightTextSecondary = 0xFF64748B;

  // Dark Theme Neutrals (OLED friendly)
  static const int darkBackground = 0xFF090D16;
  static const int darkSurface = 0xFF131B2E;
  static const int darkBorder = 0xFF1E293B;
  static const int darkTextPrimary = 0xFFF1F5F9;
  static const int darkTextSecondary = 0xFF94A3B8;

  // Scanner Viewfinder Colors
  static const int scanLaser = 0xFFEF4444;
  static const int scanValidBox = 0xFF22C55E;
}
