// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../models/retailer_model.dart';
import '../services/sales_api_service.dart';
import '../services/sales_local_cache.dart';

/// State controller for the territory-scoped retailer directory.
class RetailerDirectoryController {
  final SalesApiService apiService;
  final SalesLocalCache localCache;

  List<RetailerModel> retailers = [];
  bool isLoading = false;
  String? errorMessage;
  bool isOfflineMode = false;
  int currentPage = 1;
  bool hasMore = false;

  RetailerDirectoryController({
    required this.apiService,
    required this.localCache,
  });

  Future<void> fetchRetailers({
    String? search,
    String? group,
    bool refresh = false,
  }) async {
    if (refresh) {
      currentPage = 1;
      retailers.clear();
    }

    isLoading = true;
    errorMessage = null;

    try {
      final res = await apiService.getRetailers(
        search: search,
        group: group,
        page: currentPage,
        pageSize: 50,
      );

      if (refresh) {
        retailers = res.items;
      } else {
        retailers.addAll(res.items);
      }
      hasMore = res.hasMore;
      isOfflineMode = false;

      // Cache fresh data for offline use
      await localCache.cacheRetailers(res.items);
    } catch (e) {
      // Offline fallback: load from SQLCipher cache
      retailers = await localCache.getCachedRetailers(search: search, group: group);
      isOfflineMode = true;
      hasMore = false;
    } finally {
      isLoading = false;
    }
  }

  Future<void> loadNextPage({String? search, String? group}) async {
    if (!hasMore || isLoading || isOfflineMode) return;
    currentPage++;
    await fetchRetailers(search: search, group: group, refresh: false);
  }
}
