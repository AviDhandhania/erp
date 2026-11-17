// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'package:clothing_core/clothing_core.dart';
import '../models/production_cycle_model.dart';
import '../models/stage_inspection_model.dart';
import '../models/checklist_template_model.dart';
import '../models/return_quarantine_model.dart';

/// SQLCipher 256-bit AES encrypted local persistence for Clothing Quality Mobile.
///
/// Cryptographic Invariant:
/// - Derived encryption keys from hardware KeyStore / Keychain.
/// - Immediate cryptographic destruction (`destroyAndWipe`) on logout or remote role revocation.
class QualityLocalCache {
  final ClothingEncryptedDb encryptedDb;

  QualityLocalCache({required this.encryptedDb});

  /// Initializes encrypted database schema for quality domain.
  Future<void> initializeSchema() async {
    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_production_cycles (
        cycle_key TEXT PRIMARY KEY,
        supplier TEXT NOT NULL,
        current_stage INTEGER NOT NULL,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_stage_inspections (
        name TEXT PRIMARY KEY,
        cycle_key TEXT NOT NULL,
        stage INTEGER NOT NULL,
        is_draft INTEGER NOT NULL DEFAULT 0,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_checklist_templates (
        item_group TEXT PRIMARY KEY,
        version INTEGER NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_return_quarantine (
        name TEXT PRIMARY KEY,
        customer TEXT NOT NULL,
        item_code TEXT NOT NULL,
        quality_decision TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    ''');

    await encryptedDb.execute('''
      CREATE TABLE IF NOT EXISTS local_quality_conflicts (
        mutation_id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        document_reference TEXT,
        error_message TEXT NOT NULL,
        error_code TEXT,
        failed_at TEXT NOT NULL,
        resolution_status TEXT NOT NULL DEFAULT 'Unresolved'
      );
    ''');
  }

  // -------------------------------------------------------------------------
  // Production Cycles Cache
  // -------------------------------------------------------------------------

  Future<void> cacheCycles(List<ProductionCycleModel> cycles) async {
    final now = DateTime.now().toIso8601String();
    for (final c in cycles) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_production_cycles (cycle_key, supplier, current_stage, status, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [c.cycleKey, c.supplier, c.currentStage, c.status, jsonEncode(c.toJson()), now],
      );
    }
  }

  Future<List<ProductionCycleModel>> getCachedCycles({String? supplier, String? status}) async {
    String query = 'SELECT payload_json FROM local_production_cycles WHERE 1=1';
    final args = <dynamic>[];

    if (supplier != null && supplier.isNotEmpty) {
      query += ' AND supplier = ?';
      args.add(supplier);
    }
    if (status != null && status.isNotEmpty) {
      query += ' AND status = ?';
      args.add(status);
    }
    query += ' ORDER BY current_stage ASC, cycle_key DESC;';

    final rows = await encryptedDb.query(query, args);
    return rows.map((row) {
      final jsonMap = jsonDecode(row['payload_json'] as String) as Map<String, dynamic>;
      return ProductionCycleModel.fromJson(jsonMap);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Stage Inspections Cache
  // -------------------------------------------------------------------------

  Future<void> saveDraftInspection(StageInspectionModel inspection) async {
    final now = DateTime.now().toIso8601String();
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_stage_inspections (name, cycle_key, stage, is_draft, payload_json, updated_at)
      VALUES (?, ?, ?, 1, ?, ?);
      ''',
      [inspection.name, inspection.cycleKey, inspection.stage, jsonEncode(inspection.toJson()), now],
    );
  }

  Future<StageInspectionModel?> getCachedDraftInspection(String cycleKey, int stage) async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_stage_inspections WHERE cycle_key = ? AND stage = ? AND is_draft = 1 LIMIT 1;',
      [cycleKey, stage],
    );
    if (rows.isEmpty) return null;
    final jsonMap = jsonDecode(rows.first['payload_json'] as String) as Map<String, dynamic>;
    return StageInspectionModel.fromJson(jsonMap);
  }

  // -------------------------------------------------------------------------
  // Checklist Templates Cache
  // -------------------------------------------------------------------------

  Future<void> cacheChecklistTemplate(ChecklistTemplateModel template) async {
    final now = DateTime.now().toIso8601String();
    await encryptedDb.execute(
      '''
      INSERT OR REPLACE INTO local_checklist_templates (item_group, version, payload_json, updated_at)
      VALUES (?, ?, ?, ?);
      ''',
      [template.itemGroup, template.version, jsonEncode(template.toJson()), now],
    );
  }

  Future<ChecklistTemplateModel?> getCachedChecklistTemplate(String itemGroup) async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_checklist_templates WHERE item_group = ? LIMIT 1;',
      [itemGroup],
    );
    if (rows.isEmpty) return null;
    final jsonMap = jsonDecode(rows.first['payload_json'] as String) as Map<String, dynamic>;
    return ChecklistTemplateModel.fromJson(jsonMap);
  }

  // -------------------------------------------------------------------------
  // Return Quarantine Cache
  // -------------------------------------------------------------------------

  Future<void> cacheQuarantineItems(List<ReturnQuarantineModel> items) async {
    final now = DateTime.now().toIso8601String();
    for (final item in items) {
      await encryptedDb.execute(
        '''
        INSERT OR REPLACE INTO local_return_quarantine (name, customer, item_code, quality_decision, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?);
        ''',
        [item.name, item.customer, item.itemCode, item.qualityDecision, jsonEncode(item.toJson()), now],
      );
    }
  }

  Future<List<ReturnQuarantineModel>> getCachedQuarantineItems() async {
    final rows = await encryptedDb.query(
      'SELECT payload_json FROM local_return_quarantine ORDER BY name DESC;',
    );
    return rows.map((r) {
      final jsonMap = jsonDecode(r['payload_json'] as String) as Map<String, dynamic>;
      return ReturnQuarantineModel.fromJson(jsonMap);
    }).toList();
  }

  // -------------------------------------------------------------------------
  // Full Cryptographic Wipe
  // -------------------------------------------------------------------------

  Future<void> wipeAllCaches() async {
    await encryptedDb.destroyAndWipe();
  }
}
