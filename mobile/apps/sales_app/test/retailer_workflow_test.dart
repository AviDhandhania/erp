// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:test/test.dart';
import 'package:sales_app/sales_app.dart';

void main() {
  group('Retailer & Application Workflow Tests', () {
    test('retailer model accurately reflects operating type and exposure', () {
      final json = {
        'name': 'CUST-BOUTIQUE-001',
        'customer_name': 'Prestige Apparels',
        'territory': 'South Mumbai',
        'customer_group': 'Buy & Sell',
        'mobile_no': '+91 98200 12345',
        'approved_limit': 1000000.0,
        'total_exposure': 750000.0,
        'available_exposure': 250000.0,
        'exceeds_limit': false,
        'cadence_status': 'OK',
        'order_blocked': false,
      };

      final retailer = RetailerModel.fromJson(json);

      expect(retailer.id, equals('CUST-BOUTIQUE-001'));
      expect(retailer.isBuyAndSell, isTrue);
      expect(retailer.isSIS, isFalse);
      expect(retailer.availableExposure, equals(250000.0));
      expect(retailer.orderBlocked, isFalse);
    });

    test('retailer application supports multi-photo private evidence and commercial review', () {
      final photo = const ApplicationEvidencePhoto(
        photoPathOrUrl: '/private/files/storefront_001.jpg',
        caption: 'Storefront entrance sign',
        photoType: 'Storefront',
        sha256Checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        fileSize: 450000,
      );

      final app = RetailerApplicationModel(
        clientDraftId: 'draft-uuid-001',
        retailerName: 'Vogue Boutique',
        contactPerson: 'Rajesh Sharma',
        mobileNo: '+91 98111 22334',
        operatingType: 'Buy & Sell',
        territory: 'Delhi Central',
        address: '14 Connaught Place, New Delhi',
        evidencePhotos: [photo],
        status: 'Draft',
      );

      expect(app.isDraft, isTrue);
      expect(app.evidencePhotos.length, equals(1));
      expect(app.evidencePhotos.first.photoType, equals('Storefront'));

      // Transition to RSM review with commercial fields
      final rsmReviewed = app.copyWith(
        status: 'Pending',
        estimatedMonthlyTurnover: 1500000.0,
        expectedFootfall: 120,
        shopSquareFootage: 850.0,
        proposedPaymentTerms: '30 Days Net',
        initialExposureLimit: 500000.0,
      );

      expect(rsmReviewed.isPendingReview, isTrue);
      expect(rsmReviewed.estimatedMonthlyTurnover, equals(1500000.0));
      expect(rsmReviewed.initialExposureLimit, equals(500000.0));
    });

    test('application RFI notes and resubmission transitions', () {
      final app = RetailerApplicationModel(
        id: 'RAP-2026-0001',
        clientDraftId: 'draft-uuid-001',
        retailerName: 'Metro Styles',
        contactPerson: 'Sunil Verma',
        mobileNo: '+91 98333 44556',
        operatingType: 'SIS',
        territory: 'Pune West',
        address: 'FC Road, Pune',
        status: 'More Information Requested',
        requestedInformation: 'Please provide clear copy of GST Certificate.',
      );

      expect(app.isRfi, isTrue);
      expect(app.requestedInformation, contains('GST Certificate'));

      final resubmitted = app.copyWith(
        status: 'Resubmitted',
      );
      expect(resubmitted.isPendingReview, isTrue);
    });
  });
}
