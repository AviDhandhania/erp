// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../tokens/colors.dart';

/// Application Theme Definitions (Light, Dark, High-Contrast).
class ClothingThemeData {
  final bool isDark;
  final bool isHighContrast;
  final int backgroundColor;
  final int surfaceColor;
  final int textPrimaryColor;
  final int textSecondaryColor;
  final int borderColor;
  final int primaryColor;

  const ClothingThemeData({
    required this.isDark,
    required this.isHighContrast,
    required this.backgroundColor,
    required this.surfaceColor,
    required this.textPrimaryColor,
    required this.textSecondaryColor,
    required this.borderColor,
    required this.primaryColor,
  });

  static const light = ClothingThemeData(
    isDark: false,
    isHighContrast: false,
    backgroundColor: ClothingColors.lightBackground,
    surfaceColor: ClothingColors.lightSurface,
    textPrimaryColor: ClothingColors.lightTextPrimary,
    textSecondaryColor: ClothingColors.lightTextSecondary,
    borderColor: ClothingColors.lightBorder,
    primaryColor: ClothingColors.brandPrimary,
  );

  static const dark = ClothingThemeData(
    isDark: true,
    isHighContrast: false,
    backgroundColor: ClothingColors.darkBackground,
    surfaceColor: ClothingColors.darkSurface,
    textPrimaryColor: ClothingColors.darkTextPrimary,
    textSecondaryColor: ClothingColors.darkTextSecondary,
    borderColor: ClothingColors.darkBorder,
    primaryColor: ClothingColors.brandSecondary,
  );

  static const highContrast = ClothingThemeData(
    isDark: true,
    isHighContrast: true,
    backgroundColor: 0xFF000000,
    surfaceColor: 0xFF121212,
    textPrimaryColor: 0xFFFFFFFF,
    textSecondaryColor: 0xFFE0E0E0,
    borderColor: 0xFFFFFFFF,
    primaryColor: 0xFFFFD700,
  );
}
