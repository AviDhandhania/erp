// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../controllers/catalogue_controller.dart';
import '../models/catalogue_model.dart';

/// Screen displaying the garment catalogue subset with offline caching and barcode scanning.
class CatalogueScreen {
  final CatalogueController controller;

  const CatalogueScreen({required this.controller});

  Map<String, dynamic> buildViewData({String? searchQuery, String? selectedCollection}) {
    return {
      'state': controller.isLoading && controller.templates.isEmpty ? 'loading' : 'ready',
      'is_stale_cache': controller.isStaleCache,
      'stale_cache_warning': controller.isStaleCache
          ? 'Cached catalogue data: Prices and stock levels are non-authoritative. Server revalidation will occur before order placement.'
          : null,
      'search_query': searchQuery ?? '',
      'selected_collection': selectedCollection ?? 'All',
      'templates_count': controller.templates.length,
      'has_more': controller.hasMore,
      'templates': controller.templates.map((t) => {
        'template_code': t.templateCode,
        'item_name': t.itemName,
        'colour': t.colour,
        'collection': t.collection,
        'image_url': t.imageUrl,
        'variants_count': t.variants.length,
        'sizes_available': t.variants.map((v) => v.size).toList(),
      }).toList(),
      'actions': [
        'scan_barcode',
        'refresh_catalogue',
        'open_cart',
      ],
    };
  }
}
