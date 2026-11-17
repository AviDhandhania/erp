// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Evidence photo captured during retailer onboarding.
@immutable
class ApplicationEvidencePhoto {
  final String photoPathOrUrl;
  final String caption;
  final String photoType; // 'Storefront' | 'Interior' | 'GST Certificate' | 'PAN Card' | 'Cheque'
  final String sha256Checksum;
  final int fileSize;

  const ApplicationEvidencePhoto({
    required this.photoPathOrUrl,
    required this.caption,
    required this.photoType,
    required this.sha256Checksum,
    this.fileSize = 0,
  });

  factory ApplicationEvidencePhoto.fromJson(Map<String, dynamic> json) => ApplicationEvidencePhoto(
    photoPathOrUrl: json['file_url'] as String? ?? json['path'] as String? ?? '',
    caption: json['caption'] as String? ?? '',
    photoType: json['photo_type'] as String? ?? 'Storefront',
    sha256Checksum: json['sha256_checksum'] as String? ?? '',
    fileSize: json['file_size'] as int? ?? 0,
  );

  Map<String, dynamic> toJson() => {
    'file_url': photoPathOrUrl,
    'caption': caption,
    'photo_type': photoType,
    'sha256_checksum': sha256Checksum,
    'file_size': fileSize,
  };
}

/// Retailer application onboarding record for prospective shops.
@immutable
class RetailerApplicationModel {
  final String? id; // Server application name (e.g. RAP-2026-0001)
  final String clientDraftId; // Local UUID for draft save/resume
  final String retailerName;
  final String contactPerson;
  final String mobileNo;
  final String? emailId;
  final String operatingType; // Buy & Sell | SIS | EBOC | etc.
  final String territory;
  final String address;
  final String? gstin;
  final String? pan;
  final List<ApplicationEvidencePhoto> evidencePhotos;

  // Workflow state
  final String status; // Draft | Submitted to RSM | Pending | More Information Requested | Resubmitted | Approved | Rejected
  final String? salesperson; // ASM username
  final String? supervisingRsm;
  final String? requestedInformation;
  final String? rejectionReason;
  final DateTime? submittedOn;
  final DateTime? reviewedOn;

  // RSM Commercial Review Fields
  final double? estimatedMonthlyTurnover;
  final int? expectedFootfall;
  final double? shopSquareFootage;
  final String? proposedPaymentTerms;
  final String? securityDepositReference;
  final String? commercialReviewNotes;
  final double? initialExposureLimit;

  const RetailerApplicationModel({
    this.id,
    required this.clientDraftId,
    required this.retailerName,
    required this.contactPerson,
    required this.mobileNo,
    this.emailId,
    required this.operatingType,
    required this.territory,
    required this.address,
    this.gstin,
    this.pan,
    this.evidencePhotos = const [],
    this.status = 'Draft',
    this.salesperson,
    this.supervisingRsm,
    this.requestedInformation,
    this.rejectionReason,
    this.submittedOn,
    this.reviewedOn,
    this.estimatedMonthlyTurnover,
    this.expectedFootfall,
    this.shopSquareFootage,
    this.proposedPaymentTerms,
    this.securityDepositReference,
    this.commercialReviewNotes,
    this.initialExposureLimit,
  });

  bool get isDraft => status == 'Draft';
  bool get isPendingReview => status == 'Pending' || status == 'Submitted to RSM' || status == 'Resubmitted';
  bool get isRfi => status == 'More Information Requested';
  bool get isApproved => status == 'Approved';
  bool get isRejected => status == 'Rejected';

  RetailerApplicationModel copyWith({
    String? id,
    String? clientDraftId,
    String? retailerName,
    String? contactPerson,
    String? mobileNo,
    String? emailId,
    String? operatingType,
    String? territory,
    String? address,
    String? gstin,
    String? pan,
    List<ApplicationEvidencePhoto>? evidencePhotos,
    String? status,
    String? salesperson,
    String? supervisingRsm,
    String? requestedInformation,
    String? rejectionReason,
    DateTime? submittedOn,
    DateTime? reviewedOn,
    double? estimatedMonthlyTurnover,
    int? expectedFootfall,
    double? shopSquareFootage,
    String? proposedPaymentTerms,
    String? securityDepositReference,
    String? commercialReviewNotes,
    double? initialExposureLimit,
  }) {
    return RetailerApplicationModel(
      id: id ?? this.id,
      clientDraftId: clientDraftId ?? this.clientDraftId,
      retailerName: retailerName ?? this.retailerName,
      contactPerson: contactPerson ?? this.contactPerson,
      mobileNo: mobileNo ?? this.mobileNo,
      emailId: emailId ?? this.emailId,
      operatingType: operatingType ?? this.operatingType,
      territory: territory ?? this.territory,
      address: address ?? this.address,
      gstin: gstin ?? this.gstin,
      pan: pan ?? this.pan,
      evidencePhotos: evidencePhotos ?? this.evidencePhotos,
      status: status ?? this.status,
      salesperson: salesperson ?? this.salesperson,
      supervisingRsm: supervisingRsm ?? this.supervisingRsm,
      requestedInformation: requestedInformation ?? this.requestedInformation,
      rejectionReason: rejectionReason ?? this.rejectionReason,
      submittedOn: submittedOn ?? this.submittedOn,
      reviewedOn: reviewedOn ?? this.reviewedOn,
      estimatedMonthlyTurnover: estimatedMonthlyTurnover ?? this.estimatedMonthlyTurnover,
      expectedFootfall: expectedFootfall ?? this.expectedFootfall,
      shopSquareFootage: shopSquareFootage ?? this.shopSquareFootage,
      proposedPaymentTerms: proposedPaymentTerms ?? this.proposedPaymentTerms,
      securityDepositReference: securityDepositReference ?? this.securityDepositReference,
      commercialReviewNotes: commercialReviewNotes ?? this.commercialReviewNotes,
      initialExposureLimit: initialExposureLimit ?? this.initialExposureLimit,
    );
  }

  factory RetailerApplicationModel.fromJson(Map<String, dynamic> json) {
    final rawPhotos = json['evidence_photos'] as List<dynamic>? ?? [];
    return RetailerApplicationModel(
      id: json['name'] as String?,
      clientDraftId: json['client_draft_id'] as String? ?? json['name'] as String? ?? '',
      retailerName: json['retailer_name'] as String? ?? '',
      contactPerson: json['contact_person'] as String? ?? '',
      mobileNo: json['mobile_no'] as String? ?? '',
      emailId: json['email_id'] as String?,
      operatingType: json['customer_group'] as String? ?? json['operating_type'] as String? ?? 'Buy & Sell',
      territory: json['territory'] as String? ?? '',
      address: json['primary_address'] as String? ?? json['address'] as String? ?? '',
      gstin: json['gstin'] as String?,
      pan: json['pan'] as String?,
      evidencePhotos: rawPhotos
          .whereType<Map<String, dynamic>>()
          .map((p) => ApplicationEvidencePhoto.fromJson(p))
          .toList(),
      status: json['status'] as String? ?? 'Draft',
      salesperson: json['salesperson'] as String?,
      supervisingRsm: json['supervising_rsm'] as String?,
      requestedInformation: json['requested_information'] as String?,
      rejectionReason: json['rejection_reason'] as String?,
      submittedOn: DateTime.tryParse(json['creation'] as String? ?? ''),
      reviewedOn: DateTime.tryParse(json['reviewed_on'] as String? ?? ''),
      estimatedMonthlyTurnover: (json['estimated_monthly_turnover'] as num?)?.toDouble(),
      expectedFootfall: json['expected_footfall'] as int?,
      shopSquareFootage: (json['shop_square_footage'] as num?)?.toDouble(),
      proposedPaymentTerms: json['proposed_payment_terms'] as String?,
      securityDepositReference: json['security_deposit_reference'] as String?,
      commercialReviewNotes: json['commercial_review_notes'] as String?,
      initialExposureLimit: (json['initial_exposure_limit'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': id,
    'client_draft_id': clientDraftId,
    'retailer_name': retailerName,
    'contact_person': contactPerson,
    'mobile_no': mobileNo,
    'email_id': emailId,
    'customer_group': operatingType,
    'territory': territory,
    'primary_address': address,
    'gstin': gstin,
    'pan': pan,
    'evidence_photos': evidencePhotos.map((p) => p.toJson()).toList(),
    'status': status,
    'salesperson': salesperson,
    'supervising_rsm': supervisingRsm,
    'requested_information': requestedInformation,
    'rejection_reason': rejectionReason,
    'estimated_monthly_turnover': estimatedMonthlyTurnover,
    'expected_footfall': expectedFootfall,
    'shop_square_footage': shopSquareFootage,
    'proposed_payment_terms': proposedPaymentTerms,
    'security_deposit_reference': securityDepositReference,
    'commercial_review_notes': commercialReviewNotes,
    'initial_exposure_limit': initialExposureLimit,
  };
}
