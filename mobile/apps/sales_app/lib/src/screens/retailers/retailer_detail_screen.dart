// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/retailer_model.dart';

/// Screen presenting the detailed profile and operational status of a retailer.
class RetailerDetailScreen {
  final RetailerModel retailer;

  const RetailerDetailScreen({required this.retailer});

  Map<String, dynamic> buildViewData() {
    return {
      'id': retailer.id,
      'name': retailer.customerName,
      'territory': retailer.territory,
      'operating_type': retailer.operatingType,
      'contact': {
        'mobile_no': retailer.mobileNo,
        'email_id': retailer.emailId,
        'primary_address': retailer.primaryAddress,
        'has_coordinates': retailer.latitude != null && retailer.longitude != null,
        'latitude': retailer.latitude,
        'longitude': retailer.longitude,
      },
      'exposure': {
        'approved_limit': retailer.approvedExposureLimit,
        'total_exposure': retailer.totalExposure,
        'available_exposure': retailer.availableExposure,
        'exceeds_limit': retailer.exceedsLimit,
      },
      'cadence': {
        'status': retailer.cadenceStatus,
      },
      'order_eligibility': {
        'is_blocked': retailer.orderBlocked,
        'block_reason': retailer.blockReason,
        'can_order': !retailer.orderBlocked,
      },
      'available_actions': [
        'start_visit',
        if (!retailer.orderBlocked) 'create_order',
        'view_collections',
        'open_maps_navigation',
        'call_phone',
      ],
    };
  }
}
