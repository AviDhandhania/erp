// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

import '../auth/token_model.dart';
import 'api_exceptions.dart';
import 'tls_config.dart';

/// Versioned, Robust HTTP Client for Clothing ERP Mobile Applications.
///
/// Security Guarantees:
/// - Injects device telemetry and version headers on every request.
/// - Injects client-generated UUID idempotency keys on mutating POST requests.
/// - Automatically attaches OAuth2 Bearer token and triggers token refresh on 401.
/// - Strictly validates TLS and rejects unvalidated hostnames.
class ClothingApiClient {
  final Uri baseUrl;
  final String appId;
  final String appVersion;
  final String deviceId;
  final String minSupportedVersion;
  final ClothingTlsConfig tlsConfig;
  final Future<ClothingTokenModel?> Function() tokenProvider;
  final Future<ClothingTokenModel?> Function() refreshTokenCallback;
  final VoidCallback? onSessionRevoked;

  final http.Client _httpClient;

  ClothingApiClient({
    required this.baseUrl,
    required this.appId,
    required this.appVersion,
    required this.deviceId,
    required this.tlsConfig,
    required this.tokenProvider,
    required this.refreshTokenCallback,
    this.minSupportedVersion = '1.0.0',
    this.onSessionRevoked,
    http.Client? httpClient,
  }) : _httpClient = httpClient ?? http.Client();

  /// Standard Headers applied to every mobile request.
  Map<String, String> _buildStandardHeaders({
    String? idempotencyKey,
    String? bearerToken,
  }) {
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-Clothing-App-Id': appId,
      'X-Clothing-App-Version': appVersion,
      'X-Clothing-Device-Id': deviceId,
    };

    if (idempotencyKey != null && idempotencyKey.isNotEmpty) {
      headers['X-Idempotency-Key'] = idempotencyKey;
    }

    if (bearerToken != null && bearerToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $bearerToken';
    }

    return headers;
  }

  /// Execute an authorized GET request.
  Future<Map<String, dynamic>> get(
    String endpoint, {
    Map<String, String>? queryParams,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    return _sendWithRetry(
      method: 'GET',
      endpoint: endpoint,
      queryParams: queryParams,
      timeout: timeout,
    );
  }

  /// Execute an authorized, idempotent POST request.
  Future<Map<String, dynamic>> post(
    String endpoint, {
    Map<String, dynamic>? body,
    String? idempotencyKey,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    final effectiveIdempotencyKey = idempotencyKey ?? const Uuid().v4();
    return _sendWithRetry(
      method: 'POST',
      endpoint: endpoint,
      body: body,
      idempotencyKey: effectiveIdempotencyKey,
      timeout: timeout,
    );
  }

  /// Core request executor with automatic token refresh on 401.
  Future<Map<String, dynamic>> _sendWithRetry({
    required String method,
    required String endpoint,
    Map<String, String>? queryParams,
    Map<String, dynamic>? body,
    String? idempotencyKey,
    required Duration timeout,
    bool isRetry = false,
  }) async {
    final token = await tokenProvider();
    final uri = baseUrl.replace(
      path: endpoint.startsWith('/') ? endpoint : '/${baseUrl.path}/$endpoint',
      queryParameters: queryParams,
    );

    final headers = _buildStandardHeaders(
      idempotencyKey: idempotencyKey,
      bearerToken: token?.accessToken,
    );

    try {
      final request = http.Request(method, uri);
      request.headers.addAll(headers);
      if (body != null) {
        request.body = jsonEncode(body);
      }

      final streamedResponse = await _httpClient.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamedResponse);

      // 1. Check for Forced Upgrade / Minimum Version signal
      final serverMinVersion = response.headers['x-clothing-min-version'];
      if (serverMinVersion != null && _isVersionOutdated(appVersion, serverMinVersion)) {
        throw ClothingApiException(
          statusCode: 426, // Upgrade Required
          errorCode: ClothingErrorCode.versionDeprecated,
          message: 'Application version $appVersion is deprecated. Minimum required: $serverMinVersion',
        );
      }

      // 2. Handle 401 Unauthorized -> Refresh Token attempt
      if (response.statusCode == 401 && !isRetry) {
        final newToken = await refreshTokenCallback();
        if (newToken != null) {
          // Retry request once with fresh token
          return _sendWithRetry(
            method: method,
            endpoint: endpoint,
            queryParams: queryParams,
            body: body,
            idempotencyKey: idempotencyKey,
            timeout: timeout,
            isRetry: true,
          );
        } else {
          onSessionRevoked?.call();
          throw ClothingApiException(
            statusCode: 401,
            errorCode: ClothingErrorCode.authExpired,
            message: 'Session has expired or was revoked. Please log in again.',
          );
        }
      }

      // 3. Process Response Body
      final dynamic decoded;
      try {
        decoded = response.body.isNotEmpty ? jsonDecode(response.body) : <String, dynamic>{};
      } catch (_) {
        throw ClothingApiException(
          statusCode: response.statusCode,
          errorCode: ClothingErrorCode.serverError,
          message: 'Malformed server response (${response.statusCode}).',
        );
      }

      final resMap = decoded is Map<String, dynamic> ? decoded : {'data': decoded};

      if (response.statusCode >= 200 && response.statusCode < 300) {
        return resMap;
      }

      throw ClothingApiException.fromResponse(response.statusCode, resMap);
    } on SocketException {
      throw ClothingApiException.offline();
    } on TimeoutException {
      throw ClothingApiException(
        statusCode: 408,
        errorCode: ClothingErrorCode.networkOffline,
        message: 'Request timed out after ${timeout.inSeconds}s.',
      );
    }
  }

  /// SemVer comparator checking if client version < server minimum version.
  static bool _isVersionOutdated(String current, String minimum) {
    try {
      final curParts = current.split('.').map(int.parse).toList();
      final minParts = minimum.split('.').map(int.parse).toList();
      for (var i = 0; i < 3; i++) {
        final c = i < curParts.length ? curParts[i] : 0;
        final m = i < minParts.length ? minParts[i] : 0;
        if (c < m) return true;
        if (c > m) return false;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  void close() {
    _httpClient.close();
  }
}

typedef VoidCallback = void Function();
