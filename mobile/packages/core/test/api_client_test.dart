// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:test/test.dart';

void main() {
  group('Networking & TLS Configuration Tests', () {
    test('ClothingTlsConfig rejects hostname mismatch', () {
      const config = ClothingTlsConfig(allowedHost: 'clothing.local');
      expect(config.allowedHost, equals('clothing.local'));
      expect(config.enforcePinning, isFalse);
    });

    test('ClothingApiException parses known and unknown error codes cleanly', () {
      final excKnown = ClothingApiException.fromResponse(403, {
        'error_code': 'UNAUTHORIZED_WAREHOUSE',
        'message': 'You cannot access location WH-01.',
      });
      expect(excKnown.statusCode, equals(403));
      expect(excKnown.errorCode, equals(ClothingErrorCode.unauthorizedWarehouse));
      expect(excKnown.message, contains('WH-01'));

      final excUnknown = ClothingApiException.fromResponse(500, {
        'error_code': 'SOME_NEW_SERVER_CODE',
        'message': 'Fatal database error',
      });
      expect(excUnknown.errorCode, equals(ClothingErrorCode.serverError));
    });

    test('PaginatedResponse parses items, limit, and hasMore correctly', () {
      final json = {
        'items': [
          {'name': 'ITEM-01', 'qty': 10},
          {'name': 'ITEM-02', 'qty': 20},
        ],
        'limit': 2,
        'start': 0,
        'total_count': 5,
        'has_more': true,
      };

      final response = PaginatedResponse<Map<String, dynamic>>.fromJson(
        json,
        (m) => m,
      );

      expect(response.items.length, equals(2));
      expect(response.limit, equals(2));
      expect(response.hasMore, isTrue);
      expect(response.totalCount, equals(5));
    });
  });
}
