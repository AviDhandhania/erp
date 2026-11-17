// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/retailer_visit_model.dart';
import '../services/sales_visit_manager.dart';

/// Screen providing geolocation check-in verification, storefront photo capture,
/// and visit activity reporting.
class VisitCheckinScreen {
  final SalesVisitManager manager;
  final String customer;
  final String customerName;
  final String obligationType;

  const VisitCheckinScreen({
    required this.manager,
    required this.customer,
    required this.customerName,
    required this.obligationType,
  });

  Map<String, dynamic> buildViewData({
    double? latitude,
    double? longitude,
    double? accuracyMeters,
    bool consent = false,
    String? checkinPhotoUrl,
    String? outcome,
    String? notes,
    int? footfall,
    String? financialReview,
    int? sisStockAuditQty,
  }) {
    final hasCoordinates = latitude != null && longitude != null;
    final checkinVerified = hasCoordinates && consent;

    return {
      'customer': customer,
      'customer_name': customerName,
      'obligation_type': obligationType,
      'checkin': {
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_meters': accuracyMeters,
        'consent_given': consent,
        'photo_captured': checkinPhotoUrl != null,
        'photo_url': checkinPhotoUrl,
        'status': checkinVerified ? 'Verified' : 'Pending Verification',
      },
      'report_form': {
        'outcome': outcome ?? 'Samples Shown',
        'allowed_outcomes': [
          'Order Taken',
          'Samples Shown',
          'Stock Reviewed',
          'Follow-Up Needed',
          'Retailer Unavailable',
        ],
        'notes': notes ?? '',
        'footfall': footfall,
        'financial_review': financialReview,
        'sis_stock_audit_qty': sisStockAuditQty,
      },
      'can_submit': consent && outcome != null && outcome.isNotEmpty,
      'actions': [
        'toggle_consent',
        'capture_coordinates',
        'capture_storefront_photo',
        'submit_visit',
      ],
    };
  }
}
