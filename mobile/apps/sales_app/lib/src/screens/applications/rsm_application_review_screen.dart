// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/retailer_application_model.dart';
import '../services/sales_application_manager.dart';

/// Screen enabling Regional Sales Managers to review pending applications, update commercial
/// assessments, propose initial exposure limits, and approve/reject/request information.
class RsmApplicationReviewScreen {
  final SalesApplicationManager manager;
  final RetailerApplicationModel application;

  const RsmApplicationReviewScreen({
    required this.manager,
    required this.application,
  });

  Map<String, dynamic> buildViewData() {
    return {
      'id': application.id,
      'status': application.status,
      'retailer_name': application.retailerName,
      'operating_type': application.operatingType,
      'territory': application.territory,
      'salesperson': application.salesperson,
      'submitted_on': application.submittedOn?.toIso8601String(),
      'evidence_photos': application.evidencePhotos.map((p) => {
        'photo_url': p.photoPathOrUrl,
        'caption': p.caption,
        'type': p.photoType,
        'checksum': p.sha256Checksum,
      }).toList(),
      'commercial_assessment': {
        'estimated_turnover': application.estimatedMonthlyTurnover,
        'expected_footfall': application.expectedFootfall,
        'square_footage': application.shopSquareFootage,
        'payment_terms': application.proposedPaymentTerms,
        'deposit_ref': application.securityDepositReference,
        'review_notes': application.commercialReviewNotes,
        'initial_exposure_limit': application.initialExposureLimit,
      },
      'actions': [
        'update_commercial_fields',
        'request_more_information',
        'approve_with_limit',
        'reject',
      ],
    };
  }
}
