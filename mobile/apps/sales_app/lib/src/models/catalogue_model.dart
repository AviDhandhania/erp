// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Single garment size variant under a style/colourway template.
@immutable
class ProductVariantModel {
  final String itemCode; // Specific SKU (e.g. SHIRT-SLIM-BLU-M)
  final String size; // S, M, L, XL, etc.
  final double standardRate; // Indicative cached price (NON-AUTHORITATIVE)
  final double availableStock; // Indicative cached stock (NON-AUTHORITATIVE)
  final String? barcode;

  const ProductVariantModel({
    required this.itemCode,
    required this.size,
    required this.standardRate,
    this.availableStock = 0.0,
    this.barcode,
  });

  factory ProductVariantModel.fromJson(Map<String, dynamic> json) => ProductVariantModel(
    itemCode: json['item_code'] as String? ?? '',
    size: json['size'] as String? ?? json['variant_attribute_value'] as String? ?? '',
    standardRate: (json['standard_rate'] as num?)?.toDouble() ?? 0.0,
    availableStock: (json['actual_qty'] as num?)?.toDouble() ?? (json['stock_qty'] as num?)?.toDouble() ?? 0.0,
    barcode: json['barcode'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'item_code': itemCode,
    'size': size,
    'standard_rate': standardRate,
    'actual_qty': availableStock,
    'barcode': barcode,
  };
}

/// Garment product template representing a design style & colourway.
@immutable
class CatalogueTemplateModel {
  final String templateCode; // Item template code (e.g. SHIRT-SLIM-BLU)
  final String itemName;
  final String? description;
  final String? category;
  final String? collection; // Summer 2026, Festive, etc.
  final String? colour;
  final String? imageUrl;
  final List<ProductVariantModel> variants;
  final DateTime? cachedAt;
  final bool isStale; // Always marked when served from offline cache

  const CatalogueTemplateModel({
    required this.templateCode,
    required this.itemName,
    this.description,
    this.category,
    this.collection,
    this.colour,
    this.imageUrl,
    this.variants = const [],
    this.cachedAt,
    this.isStale = false,
  });

  /// The cached prices and stock quantities are strictly advisory.
  /// Authoritative calculations must be performed on the server.
  bool get hasAuthoritativeData => !isStale;

  factory CatalogueTemplateModel.fromJson(Map<String, dynamic> json, {bool isStale = false, DateTime? cachedAt}) {
    final rawVariants = json['variants'] as List<dynamic>? ?? [];
    return CatalogueTemplateModel(
      templateCode: json['name'] as String? ?? json['item_code'] as String? ?? '',
      itemName: json['item_name'] as String? ?? '',
      description: json['description'] as String?,
      category: json['item_group'] as String? ?? json['category'] as String?,
      collection: json['collection'] as String?,
      colour: json['colour'] as String? ?? json['color'] as String?,
      imageUrl: json['image'] as String? ?? json['image_url'] as String?,
      variants: rawVariants
          .whereType<Map<String, dynamic>>()
          .map((v) => ProductVariantModel.fromJson(v))
          .toList(),
      isStale: isStale,
      cachedAt: cachedAt ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': templateCode,
    'item_name': itemName,
    'description': description,
    'item_group': category,
    'collection': collection,
    'colour': colour,
    'image_url': imageUrl,
    'variants': variants.map((v) => v.toJson()).toList(),
    'is_stale': isStale,
    'cached_at': cachedAt?.toIso8601String(),
  };
}
