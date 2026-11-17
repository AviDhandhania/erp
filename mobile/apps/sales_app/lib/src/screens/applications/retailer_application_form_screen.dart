// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/retailer_application_model.dart';
import '../services/sales_application_manager.dart';

/// Screen enabling ASMs to draft, save, resume, and submit retailer applications with private photos.
class RetailerApplicationFormScreen {
  final SalesApplicationManager manager;
  final RetailerApplicationModel initialData;

  const RetailerApplicationFormScreen({
    required this.manager,
    required this.initialData,
  });

  Map<String, dynamic> buildViewData() {
    return {
      'client_draft_id': initialData.clientDraftId,
      'is_draft': initialData.isDraft,
      'status': initialData.status,
      'retailer_name': initialData.retailerName,
      'contact_person': initialData.contactPerson,
      'mobile_no': initialData.mobileNo,
      'email_id': initialData.emailId,
      'operating_type': initialData.operatingType,
      'territory': initialData.territory,
      'address': initialData.address,
      'gstin': initialData.gstin,
      'pan': initialData.pan,
      'evidence_photos_count': initialData.evidencePhotos.length,
      'evidence_photos': initialData.evidencePhotos.map((p) => {
        'photo_url': p.photoPathOrUrl,
        'caption': p.caption,
        'photo_type': p.photoType,
        'sha256': p.sha256Checksum,
      }).toList(),
      'requested_info': initialData.requestedInformation,
      'can_submit': initialData.retailerName.isNotEmpty &&
                    initialData.contactPerson.isNotEmpty &&
                    initialData.mobileNo.isNotEmpty &&
                    initialData.territory.isNotEmpty,
      'actions': [
        'capture_photo',
        'save_draft',
        'submit_to_rsm',
        if (initialData.isRfi) 'resubmit_application',
      ],
    };
  }
}
