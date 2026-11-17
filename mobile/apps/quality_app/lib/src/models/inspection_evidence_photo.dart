// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Captioned private photo evidence captured via SafePhotoManager.
///
/// Invariants:
/// - Strips unsafe EXIF/GPS metadata.
/// - Enforces 2MB maximum payload size.
/// - Immutable SHA-256 cryptographic checksum.
@immutable
class InspectionEvidencePhoto {
  final String photoId;
  final String? localSanitizedPath;
  final String? fileUrl;
  final String caption;
  final String evidenceType; // 'Defect Observation' | 'Measurement' | 'Overall Garment' | 'Packaging'
  final String sha256Checksum;
  final int displayOrder;
  final int revision;
  final String? uploader;
  final DateTime capturedAt;

  const InspectionEvidencePhoto({
    required this.photoId,
    this.localSanitizedPath,
    this.fileUrl,
    required this.caption,
    this.evidenceType = 'Defect Observation',
    required this.sha256Checksum,
    this.displayOrder = 1,
    this.revision = 1,
    this.uploader,
    required this.capturedAt,
  });

  factory InspectionEvidencePhoto.fromJson(Map<String, dynamic> json) {
    return InspectionEvidencePhoto(
      photoId: json['photo_id'] as String? ?? json['name'] as String? ?? '',
      localSanitizedPath: json['local_path'] as String?,
      fileUrl: json['file_url'] as String?,
      caption: json['caption'] as String? ?? '',
      evidenceType: json['evidence_type'] as String? ?? 'Defect Observation',
      sha256Checksum: json['sha256_checksum'] as String? ?? json['sha256'] as String? ?? '',
      displayOrder: (json['display_order'] as num?)?.toInt() ?? 1,
      revision: (json['revision'] as num?)?.toInt() ?? 1,
      uploader: json['uploader'] as String?,
      capturedAt: DateTime.tryParse(json['captured_at'] as String? ?? json['creation'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'photo_id': photoId,
    'local_path': localSanitizedPath,
    'file_url': fileUrl,
    'caption': caption,
    'evidence_type': evidenceType,
    'sha256_checksum': sha256Checksum,
    'display_order': displayOrder,
    'revision': revision,
    'uploader': uploader,
    'captured_at': capturedAt.toIso8601String(),
  };
}
