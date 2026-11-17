// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Standardized Bounded Mobile Pagination Model.
class PaginatedResponse<T> {
  final List<T> items;
  final int limit;
  final int start;
  final bool hasMore;
  final int totalCount;

  const PaginatedResponse({
    required this.items,
    required this.limit,
    required this.start,
    required this.hasMore,
    required this.totalCount,
  });

  factory PaginatedResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) itemParser,
  ) {
    final rawItems = json['items'] as List<dynamic>? ?? json['message'] as List<dynamic>? ?? [];
    final parsedItems = rawItems
        .whereType<Map<String, dynamic>>()
        .map((m) => itemParser(m))
        .toList();

    final limit = (json['limit'] as num?)?.toInt() ?? 20;
    final start = (json['start'] as num?)?.toInt() ?? 0;
    final totalCount = (json['total_count'] as num?)?.toInt() ?? parsedItems.length;
    final hasMore = (json['has_more'] as bool?) ?? (start + parsedItems.length < totalCount);

    return PaginatedResponse<T>(
      items: parsedItems,
      limit: limit,
      start: start,
      hasMore: hasMore,
      totalCount: totalCount,
    );
  }

  Map<String, dynamic> toJson(Map<String, dynamic> Function(T) itemSerializer) {
    return {
      'items': items.map((i) => itemSerializer(i)).toList(),
      'limit': limit,
      'start': start,
      'has_more': hasMore,
      'total_count': totalCount,
    };
  }
}
