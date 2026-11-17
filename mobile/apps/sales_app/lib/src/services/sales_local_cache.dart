// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'package:clothing_core/clothing_core.dart';
import '../models/retailer_model.dart';
import '../models/catalogue_model.dart';
import '../models/retailer_application_model.dart';
import '../models/cart_order_model.dart';
import '../models/conflict_model.dart';

/// Manages SQLCipher-encrypted local offline storage for the Sales mobile app.
///
/// Security:
/// - All tables reside in an encrypted SQLite database.
/// - Stores only authorized territory data.
/// - Caches are strictly non-authoritative: marked stale on load.
/// - Provides full cryptographic wipe upon account revocation or user logout.
class SalesLocalCache {
  final ClothingEncryptedDb encryptedDb;

  SalesLocalCache({required this.encryptedDb});

  Future<void> initializeSchema() async {
    // Retailers table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_retailers (
        id TEXT PRIMARY KEY,
        customer_name TEXT NOT NULL,
        territory TEXT NOT NULL,
        operating_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    // Catalogue table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_catalogue (
        template_code TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        collection TEXT,
        category TEXT,
        payload_json TEXT NOT NULL,
        cached_at TEXT NOT NULL
      );
    ''');

    // Retailer Applications Drafts table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_application_drafts (
        client_draft_id TEXT PRIMARY KEY,
        retailer_name TEXT NOT NULL,
        territory TEXT NOT NULL,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        last_modified TEXT NOT NULL
      );
    ''');

    // Active Cart table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_active_cart (
        customer_id TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        last_modified TEXT NOT NULL
      );
    ''');

    // Offline Sync Conflicts table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_sync_conflicts (
        mutation_id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        error_message TEXT NOT NULL,
        error_code TEXT,
        failed_at TEXT NOT NULL,
        resolution_status TEXT NOT NULL
      );
    ''');
  }

  // -------------------------------------------------------------------------
  // Retailers Cache
  // -------------------------------------------------------------------------

  Future<void> cacheRetailers(List<RetailerModel> retailers) async {
    for (final r in retailers) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_retailers (id, customer_name, territory, operating_type, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [r.id, r.customerName, r.territory, r.operatingType, jsonEncode(r.toJson()), DateTime.now().toIso8601String()],
      );
    }
  }

  Future<List<RetailerModel>> getCachedRetailers({String? search, String? group}) async {
    String query = 'SELECT payload_json FROM local_retailers';
    final conditions = <String>[];
    final args = <dynamic>[];

    if (search != null && search.isNotEmpty) {
      conditions.add('(customer_name LIKE ? OR id LIKE ?)');
      args.addAll(['%$search%', '%$search%']);
    }
    if (group != null && group.isNotEmpty) {
      conditions.add('operating_type = ?');
      args.add(group);
    }

    if (conditions.isNotEmpty) {
      query += ' WHERE ${conditions.join(' AND ')}';
    }
    query += ' ORDER BY customer_name ASC;';

    final rows = await encryptedDb.query(query, args);
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return RetailerModel.fromJson(jsonMap);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Catalogue Cache (Explicitly Non-Authoritative)
  // -------------------------------------------------------------------------

  Future<void> cacheCatalogueTemplates(List<CatalogueTemplateModel> templates) async {
    final now = DateTime.now().toIso8601String();
    for (final t in templates) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_catalogue (template_code, item_name, collection, category, payload_json, cached_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [t.templateCode, t.itemName, t.collection, t.category, jsonEncode(t.toJson()), now],
      );
    }
  }

  Future<List<CatalogueTemplateModel>> getCachedCatalogue({String? search, String? collection}) async {
    String query = 'SELECT payload_json, cached_at FROM local_catalogue';
    final conditions = <String>[];
    final args = <dynamic>[];

    if (search != null && search.isNotEmpty) {
      conditions.add('(item_name LIKE ? OR template_code LIKE ?)');
      args.addAll(['%$search%', '%$search%']);
    }
    if (collection != null && collection.isNotEmpty) {
      conditions.add('collection = ?');
      args.add(collection);
    }

    if (conditions.isNotEmpty) {
      query += ' WHERE ${conditions.join(' AND ')}';
    }
    query += ' ORDER BY item_name ASC;';

    final rows = await encryptedDb.query(query, args);
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      final cachedAt = DateTime.tryParse(row['cached_at'] as String? ?? '');
      // Always mark cached catalogue entries as STALE (non-authoritative)
      return CatalogueTemplateModel.fromJson(jsonMap, isStale: true, cachedAt: cachedAt);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Application Drafts
  // -------------------------------------------------------------------------

  Future<void> saveApplicationDraft(RetailerApplicationModel draft) async {
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_application_drafts (client_draft_id, retailer_name, territory, status, payload_json, last_modified)
      VALUES (?, ?, ?, ?, ?, ?);
      ''',
      [
        draft.clientDraftId,
        draft.retailerName,
        draft.territory,
        draft.status,
        jsonEncode(draft.toJson()),
        DateTime.now().toIso8601String(),
      ],
    );
  }

  Future<List<RetailerApplicationModel>> getSavedApplicationDrafts() async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_application_drafts ORDER BY last_modified DESC;',
    );
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return RetailerApplicationModel.fromJson(jsonMap);
    }).toList();
  }

  Future<void> deleteApplicationDraft(String clientDraftId) async {
    await encryptedDb.execute(
      'DELETE FROM local_application_drafts WHERE client_draft_id = ?;',
      [clientDraftId],
    );
  }

  // -------------------------------------------------------------------------
  // Active Cart Cache
  // -------------------------------------------------------------------------

  Future<void> saveActiveCart(CartModel cart) async {
    final payload = {
      'customer': cart.customer,
      'customer_name': cart.customerName,
      'territory': cart.territory,
      'delivery_date': cart.deliveryDate.toIso8601String(),
      'client_request_id': cart.clientRequestId,
      'items': cart.items.map((i) => i.toJson()).toList(),
    };
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_active_cart (customer_id, payload_json, last_modified)
      VALUES (?, ?, ?);
      ''',
      [cart.customer, jsonEncode(payload), DateTime.now().toIso8601String()],
    );
  }

  Future<CartModel?> getActiveCart(String customerId) async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_active_cart WHERE customer_id = ?;',
      [customerId],
    );
    if (rows.isEmpty) return null;

    final jsonMap = jsonDecode(rows.first['payload_json'] as String) as Map<String, dynamic>;
    final rawItems = jsonMap['items'] as List<dynamic>? ?? [];
    return CartModel(
      customer: jsonMap['customer'] as String? ?? customerId,
      customerName: jsonMap['customer_name'] as String? ?? '',
      territory: jsonMap['territory'] as String? ?? '',
      deliveryDate: DateTime.tryParse(jsonMap['delivery_date'] as String? ?? '') ?? DateTime.now().add(const Duration(days: 3)),
      clientRequestId: jsonMap['client_request_id'] as String? ?? '',
      items: rawItems.whereType<Map<String, dynamic>>().map((i) => CartLineItem.fromJson(i)).toList(),
      isRepriced: false, // Cached cart must always be revalidated on server
    );
  }

  Future<void> clearActiveCart(String customerId) async {
    await encryptedDb.execute(
      'DELETE FROM local_active_cart WHERE customer_id = ?;',
      [customerId],
    );
  }

  // -------------------------------------------------------------------------
  // Sync Conflicts Storage
  // -------------------------------------------------------------------------

  Future<void> recordConflict(ConflictModel conflict) async {
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_sync_conflicts (mutation_id, operation_type, payload_json, error_message, error_code, failed_at, resolution_status)
      VALUES (?, ?, ?, ?, ?, ?, ?);
      ''',
      [
        conflict.mutationId,
        conflict.operationType,
        jsonEncode(conflict.payload),
        conflict.errorMessage,
        conflict.serverErrorCode,
        conflict.failedAt.toIso8601String(),
        conflict.resolutionStatus,
      ],
    );
  }

  Future<List<ConflictModel>> getUnresolvedConflicts() async {
    final rows = await encryptedDb.query(
      "SELECT * FROM local_sync_conflicts WHERE resolution_status = 'Unresolved' ORDER BY failed_at DESC;",
    );
    return rows.map((row) {
      final payload = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return ConflictModel(
        mutationId: row['mutation_id'] as String,
        operationType: row['operation_type'] as String,
        payload: payload,
        errorMessage: row['error_message'] as String,
        serverErrorCode: row['error_code'] as String?,
        failedAt: DateTime.tryParse(row['failed_at'] as String) ?? DateTime.now(),
        resolutionStatus: row['resolution_status'] as String,
      );
    }).toList();
  }

  Future<void> updateConflictResolution(String mutationId, String status) async {
    await encryptedDb.execute(
      'UPDATE local_sync_conflicts SET resolution_status = ? WHERE mutation_id = ?;',
      [status, mutationId],
    );
  }

  // -------------------------------------------------------------------------
  // Full Cryptographic Wipe
  // -------------------------------------------------------------------------

  Future<void> wipeAllCaches() async {
    await encryptedDb.destroyAndWipe();
  }
}
