// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Immutable OAuth2 Bearer Token Representation.
class ClothingTokenModel {
  final String accessToken;
  final String? refreshToken;
  final String tokenType;
  final DateTime expiresAt;
  final String? scope;
  final String userId;
  final int rotationCount;

  const ClothingTokenModel({
    required this.accessToken,
    this.refreshToken,
    this.tokenType = 'Bearer',
    required this.expiresAt,
    this.scope,
    required this.userId,
    this.rotationCount = 0,
  });

  /// Check if the token is expired or within a safety buffer window (e.g., 60 seconds).
  bool isExpired({Duration buffer = const Duration(seconds: 60)}) {
    return DateTime.now().toUtc().add(buffer).isAfter(expiresAt);
  }

  ClothingTokenModel copyWith({
    String? accessToken,
    String? refreshToken,
    DateTime? expiresAt,
    int? rotationCount,
  }) {
    return ClothingTokenModel(
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
      tokenType: tokenType,
      expiresAt: expiresAt ?? this.expiresAt,
      scope: scope,
      userId: userId,
      rotationCount: rotationCount ?? this.rotationCount,
    );
  }

  factory ClothingTokenModel.fromJson(Map<String, dynamic> json, String userId) {
    final expiresIn = (json['expires_in'] as num?)?.toInt() ?? 3600;
    final expiresAt = json['expires_at'] != null
        ? DateTime.parse(json['expires_at'] as String).toUtc()
        : DateTime.now().toUtc().add(Duration(seconds: expiresIn));

    return ClothingTokenModel(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String?,
      tokenType: json['token_type'] as String? ?? 'Bearer',
      expiresAt: expiresAt,
      scope: json['scope'] as String?,
      userId: userId,
      rotationCount: (json['rotation_count'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'access_token': accessToken,
      'refresh_token': refreshToken,
      'token_type': tokenType,
      'expires_at': expiresAt.toIso8601String(),
      'scope': scope,
      'user_id': userId,
      'rotation_count': rotationCount,
    };
  }
}
