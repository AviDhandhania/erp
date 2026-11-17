// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:test/test.dart';

void main() {
  group('ClothingAuthManager & PKCE Tests', () {
    test('generateCodeVerifier produces RFC 7636 compliant high-entropy string', () {
      final verifier1 = ClothingAuthManager.generateCodeVerifier();
      final verifier2 = ClothingAuthManager.generateCodeVerifier();

      expect(verifier1, isNotEmpty);
      expect(verifier1.length, greaterThanOrEqualTo(43));
      expect(verifier1.contains('='), isFalse); // Stripped padding
      expect(verifier1, isNot(equals(verifier2))); // High entropy
    });

    test('generateCodeChallenge derives deterministic SHA-256 S256 challenge', () {
      // Known PKCE test vector (RFC 7636 Appendix B)
      const testVerifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
      final challenge = ClothingAuthManager.generateCodeChallenge(testVerifier);

      expect(challenge, equals('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'));
    });

    test('buildAuthorizationUri constructs strict Frappe OAuth2 authorize URL', () {
      final storage = InMemorySecureStorage();
      final auth = ClothingAuthManager(
        serverBaseUrl: Uri.parse('https://clothing.local'),
        clientId: 'test_client_id',
        redirectUri: 'com.clothingerp.sales://oauth/callback',
        secureStorage: storage,
      );

      final uri = auth.buildAuthorizationUri(
        codeChallenge: 'challenge_123',
        state: 'state_xyz',
      );

      expect(uri.scheme, equals('https'));
      expect(uri.host, equals('clothing.local'));
      expect(uri.path, equals('/api/method/frappe.integrations.oauth2.authorize'));
      expect(uri.queryParameters['response_type'], equals('code'));
      expect(uri.queryParameters['client_id'], equals('test_client_id'));
      expect(uri.queryParameters['redirect_uri'], equals('com.clothingerp.sales://oauth/callback'));
      expect(uri.queryParameters['code_challenge'], equals('challenge_123'));
      expect(uri.queryParameters['code_challenge_method'], equals('S256'));
      expect(uri.queryParameters['state'], equals('state_xyz'));
    });

    test('TokenModel tracks expiration and rotation count correctly', () {
      final token = ClothingTokenModel(
        accessToken: 'access_abc',
        refreshToken: 'refresh_xyz',
        expiresAt: DateTime.now().toUtc().add(const Duration(seconds: 30)),
        userId: 'test_user@example.invalid',
        rotationCount: 1,
      );

      // Within 60s buffer -> considers expired
      expect(token.isExpired(buffer: const Duration(seconds: 60)), isTrue);
      // Within 10s buffer -> not yet expired
      expect(token.isExpired(buffer: const Duration(seconds: 10)), isFalse);

      final json = token.toJson();
      final parsed = ClothingTokenModel.fromJson(json, 'test_user@example.invalid');
      expect(parsed.accessToken, equals('access_abc'));
      expect(parsed.rotationCount, equals(1));
    });
  });
}
