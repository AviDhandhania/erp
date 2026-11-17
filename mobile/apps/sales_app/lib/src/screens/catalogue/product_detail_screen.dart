// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/catalogue_model.dart';

/// Screen presenting a garment template style, colourway, and size variant matrix.
class ProductDetailScreen {
  final CatalogueTemplateModel template;

  const ProductDetailScreen({required this.template});

  Map<String, dynamic> buildViewData({Map<String, int> selectedQuantities = const {}}) {
    int totalQty = 0;
    double indicativeTotal = 0.0;

    final variantRows = template.variants.map((v) {
      final qty = selectedQuantities[v.itemCode] ?? 0;
      totalQty += qty;
      indicativeTotal += qty * v.standardRate;

      return {
        'item_code': v.itemCode,
        'size': v.size,
        'standard_rate': v.standardRate,
        'available_stock': v.availableStock,
        'barcode': v.barcode,
        'selected_qty': qty,
      };
    }).toList();

    return {
      'template_code': template.templateCode,
      'item_name': template.itemName,
      'colour': template.colour,
      'collection': template.collection,
      'category': template.category,
      'description': template.description,
      'image_url': template.imageUrl,
      'is_stale': template.isStale,
      'matrix': variantRows,
      'total_pieces_selected': totalQty,
      'indicative_total_value': indicativeTotal,
      'can_add_to_cart': totalQty > 0,
      'actions': [
        'update_variant_qty',
        'add_to_cart',
      ],
    };
  }
}
