// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Single checkpoint item within a checklist template.
@immutable
class ChecklistItemModel {
  final String checkpoint;
  final String category; // 'Workmanship' | 'Measurements' | 'Packaging' | 'Fabric'
  final bool isMandatory;
  final String? guidanceNotes;

  const ChecklistItemModel({
    required this.checkpoint,
    this.category = 'Workmanship',
    this.isMandatory = true,
    this.guidanceNotes,
  });

  factory ChecklistItemModel.fromJson(Map<String, dynamic> json) {
    return ChecklistItemModel(
      checkpoint: json['checkpoint'] as String? ?? json['description'] as String? ?? '',
      category: json['category'] as String? ?? 'Workmanship',
      isMandatory: json['is_mandatory'] == true || json['is_mandatory'] == 1,
      guidanceNotes: json['guidance_notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'checkpoint': checkpoint,
    'category': category,
    'is_mandatory': isMandatory,
    'guidance_notes': guidanceNotes,
  };
}

/// Frozen snapshot of a checkpoint item on an active inspection.
@immutable
class InspectionChecklistItem {
  final String checkpoint;
  final String category;
  final String status; // 'Passed' | 'Failed' | 'NA' | 'Pending'
  final String? notes;
  final bool isMandatory;

  const InspectionChecklistItem({
    required this.checkpoint,
    this.category = 'Workmanship',
    this.status = 'Pending',
    this.notes,
    this.isMandatory = true,
  });

  bool get isPassed => status == 'Passed';
  bool get isFailed => status == 'Failed';
  bool get isNA => status == 'NA';

  InspectionChecklistItem copyWith({
    String? status,
    String? notes,
  }) {
    return InspectionChecklistItem(
      checkpoint: checkpoint,
      category: category,
      status: status ?? this.status,
      notes: notes ?? this.notes,
      isMandatory: isMandatory,
    );
  }

  factory InspectionChecklistItem.fromJson(Map<String, dynamic> json) {
    return InspectionChecklistItem(
      checkpoint: json['checkpoint'] as String? ?? json['check_point'] as String? ?? '',
      category: json['category'] as String? ?? 'Workmanship',
      status: json['status'] as String? ?? 'Pending',
      notes: json['notes'] as String?,
      isMandatory: json['is_mandatory'] == true || json['is_mandatory'] == 1,
    );
  }

  Map<String, dynamic> toJson() => {
    'checkpoint': checkpoint,
    'category': category,
    'status': status,
    'notes': notes,
    'is_mandatory': isMandatory,
  };
}

/// Versioned checklist template for garment categories.
@immutable
class ChecklistTemplateModel {
  final String templateName;
  final String itemGroup;
  final int version;
  final bool isDefault;
  final List<ChecklistItemModel> items;

  const ChecklistTemplateModel({
    required this.templateName,
    required this.itemGroup,
    this.version = 1,
    this.isDefault = true,
    this.items = const [],
  });

  factory ChecklistTemplateModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return ChecklistTemplateModel(
      templateName: json['template_name'] as String? ?? json['name'] as String? ?? '',
      itemGroup: json['item_group'] as String? ?? '',
      version: (json['version'] as num?)?.toInt() ?? 1,
      isDefault: json['is_default'] == true || json['is_default'] == 1,
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map((i) => ChecklistItemModel.fromJson(i))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'template_name': templateName,
    'item_group': itemGroup,
    'version': version,
    'is_default': isDefault,
    'items': items.map((i) => i.toJson()).toList(),
  };
}
