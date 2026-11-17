// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'package:clothing_core/clothing_core.dart';
import '../models/fulfillment_task_model.dart';
import '../models/pick_item_model.dart';
import '../models/warehouse_conflict_model.dart';

/// Manages SQLCipher-encrypted local offline storage for the Warehouse mobile app.
///
/// Security:
/// - All tables reside in an encrypted SQLite database.
/// - Stores only fulfillment tasks belonging to assigned warehouses.
/// - Caches are strictly non-authoritative for stock transitions.
/// - Provides full cryptographic wipe upon account revocation or user logout.
class WarehouseLocalCache {
  final ClothingEncryptedDb encryptedDb;

  WarehouseLocalCache({required this.encryptedDb});

  Future<void> initializeSchema() async {
    // Tasks table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_warehouse_tasks (
        name TEXT PRIMARY KEY,
        task_type TEXT NOT NULL,
        warehouse TEXT NOT NULL,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    // Pick Items table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_pick_items (
        location_id TEXT PRIMARY KEY,
        pick_list TEXT NOT NULL,
        item_code TEXT NOT NULL,
        warehouse TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    // Offline Scans Queue table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_offline_scans (
        id TEXT PRIMARY KEY,
        pick_list TEXT NOT NULL,
        location_id TEXT NOT NULL,
        barcode TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        scanned_at TEXT NOT NULL,
        sync_status TEXT NOT NULL
      );
    ''');

    // Offline Sync Conflicts table
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_warehouse_conflicts (
        mutation_id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        document_reference TEXT NOT NULL,
        scanned_barcode TEXT NOT NULL,
        error_message TEXT NOT NULL,
        error_code TEXT,
        failed_at TEXT NOT NULL,
        resolution_status TEXT NOT NULL
      );
    ''');
  }

  // -------------------------------------------------------------------------
  // Tasks Cache
  // -------------------------------------------------------------------------

  Future<void> cacheTasks(List<FulfillmentTaskModel> tasks) async {
    final now = DateTime.now().toIso8601String();
    for (final t in tasks) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_warehouse_tasks (name, task_type, warehouse, status, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [t.name, t.taskType, t.warehouse, t.status, jsonEncode(t.toJson()), now],
      );
    }
  }

  Future<List<FulfillmentTaskModel>> getCachedTasks({String taskType = 'pick', String? warehouse}) async {
    String query = 'SELECT payload_json FROM local_warehouse_tasks WHERE task_type = ?';
    final args = <dynamic>[taskType];

    if (warehouse != null && warehouse.isNotEmpty) {
      query += ' AND warehouse = ?';
      args.add(warehouse);
    }
    query += ' ORDER BY name DESC;';

    final rows = await encryptedDb.query(query, args);
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return FulfillmentTaskModel.fromJson(jsonMap);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Pick Items Cache
  // -------------------------------------------------------------------------

  Future<void> cachePickItems(String pickList, List<PickItemModel> items) async {
    final now = DateTime.now().toIso8601String();
    for (final item in items) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_pick_items (location_id, pick_list, item_code, warehouse, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [item.locationId, pickList, item.itemCode, item.warehouse, jsonEncode(item.toJson()), now],
      );
    }
  }

  Future<List<PickItemModel>> getCachedPickItems(String pickList) async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_pick_items WHERE pick_list = ? ORDER BY location_id ASC;',
      [pickList],
    );
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return PickItemModel.fromJson(jsonMap);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Offline Scans
  // -------------------------------------------------------------------------

  Future<void> recordOfflineScan({
    required String id,
    required String pickList,
    required String locationId,
    required String barcode,
    int quantity = 1,
  }) async {
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_offline_scans (id, pick_list, location_id, barcode, quantity, scanned_at, sync_status)
      VALUES (?, ?, ?, ?, ?, ?, ?);
      ''',
      [id, pickList, locationId, barcode, quantity, DateTime.now().toIso8601String(), 'Pending'],
    );
  }

  Future<List<Map<String, dynamic>>> getPendingOfflineScans() async {
    return encryptedDb.query(
      "SELECT * FROM local_offline_scans WHERE sync_status = 'Pending' ORDER BY scanned_at ASC;",
    );
  }

  Future<void> markScanSynced(String id) async {
    await encryptedDb.execute(
      "UPDATE local_offline_scans SET sync_status = 'Synced' WHERE id = ?;",
      [id],
    );
  }

  // -------------------------------------------------------------------------
  // Conflicts Storage
  // -------------------------------------------------------------------------

  Future<void> recordConflict(WarehouseConflictModel conflict) async {
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_warehouse_conflicts (mutation_id, operation_type, document_reference, scanned_barcode, error_message, error_code, failed_at, resolution_status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?);
      ''',
      [
        conflict.mutationId,
        conflict.operationType,
        conflict.documentReference,
        conflict.scannedBarcode,
        conflict.errorMessage,
        conflict.serverErrorCode,
        conflict.failedAt.toIso8601String(),
        conflict.resolutionStatus,
      ],
    );
  }

  Future<List<WarehouseConflictModel>> getUnresolvedConflicts() async {
    final rows = await encryptedDb.query(
      "SELECT * FROM local_warehouse_conflicts WHERE resolution_status = 'Unresolved' ORDER BY failed_at DESC;",
    );
    return rows.map((r) => WarehouseConflictModel.fromJson(r)).toList();
  }

  Future<void> updateConflictResolution(String mutationId, String status) async {
    await encryptedDb.execute(
      'UPDATE local_warehouse_conflicts SET resolution_status = ? WHERE mutation_id = ?;',
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
