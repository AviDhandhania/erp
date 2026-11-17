// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/catalogue_model.dart';
import '../services/sales_api_service.dart';
import '../services/sales_local_cache.dart';

/// State controller for the garment product catalogue and barcode lookup.
class CatalogueController {
  final SalesApiService apiService;
  final SalesLocalCache localCache;
  final MobileScannerController scannerController;

  List<CatalogueTemplateModel> templates = [];
  bool isLoading = false;
  String? errorMessage;
  bool isStaleCache = false;
  int currentPage = 1;
  bool hasMore = false;

  CatalogueController({
    required this.apiService,
    required this.localCache,
    required this.scannerController,
  });

  Future<void> fetchCatalogue({
    String? search,
    String? collection,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      templates.clear();
    }

    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getCatalogue(
        search: search,
        collection: collection,
        page: currentPage,
        pageSize: 50,
      );

      if (refresh) {
        templates = res.items;
      } else {
        templates.addAll(res.items);
      }
      hasMore = res.hasMore;
      isStaleCache = false;

      // Update encrypted local cache
      await localCache.cacheCatalogueTemplates(res.items);
    } catch (e) {
      // Offline fallback: load from SQLCipher cache and mark as STALE
      templates = await localCache.getCachedCatalogue(search: search, collection: collection);
      isStaleCache = true;
      hasMore = false;
    } finally {
      isLoading = false;
    }
  }

  /// Resolves scanned barcode against server or local catalogue.
  Future<ProductVariantModel?> lookupBarcode(String barcode) async {
    try {
      final res = await apiService.resolveBarcode(barcode, operation: 'catalogue_lookup');
      final itemCode = res['item_code'] as String?;
      if (itemCode != null) {
        // Find matching variant across templates
        for (final t in templates) {
          for (final v in t.variants) {
            if (v.itemCode == itemCode || v.barcode == barcode) {
              return v;
            }
          }
        }
      }
    } catch (_) {
      // Fallback: check locally loaded variants
      for (final t in templates) {
        for (final v in t.variants) {
          if (v.barcode == barcode || v.itemCode == barcode) {
            return v;
          }
        }
      }
    }
    return null;
  }
}
