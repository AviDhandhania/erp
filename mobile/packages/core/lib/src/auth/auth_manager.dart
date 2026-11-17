// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;

import '../network/api_exceptions.dart';
import 'secure_storage.dart';
import 'token_model.dart';

/// Production OAuth 2.0 Authorization Code with PKCE (RFC 7636) Client.
///
/// Designed strictly for the pinned Frappe v16 release.
/// Under NO circumstances are user passwords or Administrator secrets stored in the client.
class ClothingAuthManager {
  final Uri serverBaseUrl;
  final String clientId;
  final String redirectUri;
  final List<String> scopes;
  final ClothingSecureStorage secureStorage;
  final http.Client _httpClient;

  ClothingAuthManager({
    required this.serverBaseUrl,
    required this.clientId,
    required this.redirectUri,
    this.scopes = const ['all', 'openid'],
    required this.secureStorage,
    http.Client? httpClient,
  }) : _httpClient = httpClient ?? http.Client();

  /// Generates a cryptographically secure, high-entropy Code Verifier (RFC 7636 §4.1).
  static String generateCodeVerifier() {
    final random = Random.secure();
    final values = List<int>.generate(32, (i) => random.nextInt(256));
    return base64UrlEncode(values).replaceAll('=', '');
  }

  /// Derives SHA-256 Code Challenge from the Verifier (RFC 7636 §4.2).
  static String generateCodeChallenge(String codeVerifier) {
    final bytes = ascii.encode(codeVerifier);
    final digest = sha256.convert(bytes);
    return base64UrlEncode(digest.bytes).replaceAll('=', '');
  }

  /// Generates a random cryptographic state string to prevent CSRF attacks.
  static String generateState() {
    final random = Random.secure();
    final values = List<int>.generate(16, (i) => random.nextInt(256));
    return base64UrlEncode(values).replaceAll('=', '');
  }

  /// Construct the OAuth 2.0 Authorization URL for initiating the browser/system web view flow.
  Uri buildAuthorizationUri({
    required String codeChallenge,
    required String state,
  }) {
    return serverBaseUrl.replace(
      path: '/api/method/frappe.integrations.oauth2.authorize',
      queryParameters: {
        'response_type': 'code',
        'client_id': clientId,
        'redirect_uri': redirectUri,
        'scope': scopes.join(' '),
        'state': state,
        'code_challenge': codeChallenge,
        'code_challenge_method': 'S256',
      },
    );
  }

  /// Exchange Authorization Code for Access & Refresh Tokens.
  Future<ClothingTokenModel> exchangeCodeForToken({
    required String authorizationCode,
    required String codeVerifier,
    required String userId,
  }) async {
    final tokenUri = serverBaseUrl.replace(
      path: '/api/method/frappe.integrations.oauth2.get_token',
    );

    final response = await _httpClient.post(
      tokenUri,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: {
        'grant_type': 'authorization_code',
        'client_id': clientId,
        'code': authorizationCode,
        'redirect_uri': redirectUri,
        'code_verifier': codeVerifier,
      },
    );

    if (response.statusCode != 200) {
      throw ClothingApiException(
        statusCode: response.statusCode,
        errorCode: ClothingErrorCode.authInvalid,
        message: 'Failed to exchange authorization code: ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final token = ClothingTokenModel.fromJson(data, userId);
    await secureStorage.saveToken(token);
    return token;
  }

  /// Rotate and refresh an expired Access Token using the Refresh Token.
  Future<ClothingTokenModel?> refreshAccessToken() async {
    final currentToken = await secureStorage.getToken();
    if (currentToken == null || currentToken.refreshToken == null) {
      return null;
    }

    final tokenUri = serverBaseUrl.replace(
      path: '/api/method/frappe.integrations.oauth2.get_token',
    );

    final response = await _httpClient.post(
      tokenUri,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: {
        'grant_type': 'refresh_token',
        'client_id': clientId,
        'refresh_token': currentToken.refreshToken!,
      },
    );

    if (response.statusCode != 200) {
      // Refresh token revoked or expired on server -> force re-login
      await secureStorage.clearToken();
      return null;
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final newToken = currentToken.copyWith(
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String? ?? currentToken.refreshToken,
      expiresAt: DateTime.now().toUtc().add(
            Duration(seconds: (data['expires_in'] as num?)?.toInt() ?? 3600),
          ),
      rotationCount: currentToken.rotationCount + 1,
    );

    await secureStorage.saveToken(newToken);
    return newToken;
  }

  /// Remotely revoke the active token and purge local secure storage.
  Future<void> revokeAndLogout() async {
    final token = await secureStorage.getToken();
    if (token != null) {
      final revokeUri = serverBaseUrl.replace(
        path: '/api/method/frappe.integrations.oauth2.revoke_token',
      );
      try {
        await _httpClient.post(
          revokeUri,
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: {
            'client_id': clientId,
            'token': token.refreshToken ?? token.accessToken,
          },
        );
      } catch (_) {
        // Best effort remote revocation; local wipe proceeds unconditionally.
      }
    }
    await secureStorage.deleteAll();
  }
}
