// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:sales_app/sales_app.dart';

void main() {
  group('Catalogue & Cart Management Tests', () {
    test('catalogue template accurately models size variant matrix and stale cache status', () {
      final json = {
        'name': 'SHIRT-OXFORD-BLU',
        'item_name': 'Classic Oxford Blue Shirt',
        'colour': 'Blue',
        'collection': 'Spring/Summer 2026',
        'category': 'Shirts',
        'variants': [
          {'item_code': 'SHIRT-OXFORD-BLU-S', 'size': 'S', 'standard_rate': 1200.0, 'actual_qty': 45.0, 'barcode': '890123400101'},
          {'item_code': 'SHIRT-OXFORD-BLU-M', 'size': 'M', 'standard_rate': 1200.0, 'actual_qty': 60.0, 'barcode': '890123400102'},
          {'item_code': 'SHIRT-OXFORD-BLU-L', 'size': 'L', 'standard_rate': 1200.0, 'actual_qty': 30.0, 'barcode': '890123400103'},
        ],
      };

      final template = CatalogueTemplateModel.fromJson(json, isStale: true);

      expect(template.templateCode, equals('SHIRT-OXFORD-BLU'));
      expect(template.variants.length, equals(3));
      expect(template.isStale, isTrue); // Clearly marked stale when served from cache
      expect(template.hasAuthoritativeData, isFalse);
    });

    test('cart correctly calculates indicative totals and stores UUID client request ID', () {
      final items = [
        const CartLineItem(
          templateCode: 'SHIRT-OXFORD-BLU',
          itemName: 'Oxford Shirt Blue',
          colour: 'Blue',
          size: 'M',
          itemCode: 'SHIRT-OXFORD-BLU-M',
          quantity: 10,
          indicativeRate: 1200.0,
        ),
        const CartLineItem(
          templateCode: 'SHIRT-OXFORD-BLU',
          itemName: 'Oxford Shirt Blue',
          colour: 'Blue',
          size: 'L',
          itemCode: 'SHIRT-OXFORD-BLU-L',
          quantity: 5,
          indicativeRate: 1200.0,
        ),
      ];

      final cart = CartModel(
        customer: 'CUST-001',
        customerName: 'Metro Store',
        territory: 'Delhi',
        deliveryDate: DateTime(2026, 12, 1),
        items: items,
        clientRequestId: 'uuid-req-998877',
      );

      expect(cart.totalPieces, equals(15));
      expect(cart.indicativeSubtotal, equals(18000.0));
      expect(cart.isRepriced, isFalse);

      // Server repricing update
      final repriced = cart.copyWith(
        serverSubtotal: 18000.0,
        serverTaxes: 900.0, // 5% GST
        serverGrandTotal: 18900.0,
        serverApprovedLimit: 50000.0,
        serverNewTotalExposure: 35000.0,
        serverExceedsLimit: false,
        isRepriced: true,
      );

      expect(repriced.isRepriced, isTrue);
      expect(repriced.serverGrandTotal, equals(18900.0));
      expect(repriced.serverExceedsLimit, isFalse);
    });
  });
}
