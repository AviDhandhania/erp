// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:async';
import 'dart:convert';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:uuid/uuid.dart';

import '../network/api_client.dart';
import '../network/api_exceptions.dart';
import 'encrypted_db.dart';

/// Lifecycle States of an Offline Queued Mutation.
enum MutationStatus {
  pending('pending'),
  inFlight('in_flight'),
  completed('completed'),
  failed('failed'),
  conflict('conflict');

  final String value;
  const MutationStatus(this.value);

  static MutationStatus fromString(String val) {
    for (final s in MutationStatus.values) {
      if (s.value == val) return s;
    }
    return MutationStatus.pending;
  }
}

/// Strongly-typed Envelope for Queued Mutations.
class OfflineMutationEnvelope {
  final String idempotencyKey;
  final String operationType;
  final String endpoint;
  final Map<String, dynamic> payload;
  final int schemaVersion;
  final String userId;
  final String deviceId;
  final DateTime deviceTimestamp;
  final MutationStatus status;
  final int retryCount;
  final String? lastError;
  final DateTime createdAt;

  const OfflineMutationEnvelope({
    required this.idempotencyKey,
    required this.operationType,
    required this.endpoint,
    required this.payload,
    required this.schemaVersion,
    required this.userId,
    required this.deviceId,
    required this.deviceTimestamp,
    required this.status,
    required this.retryCount,
    this.lastError,
    required this.createdAt,
  });

  factory OfflineMutationEnvelope.fromRow(Map<String, dynamic> row) {
    return OfflineMutationEnvelope(
      idempotencyKey: row['idempotency_key'] as String,
      operationType: row['operation_type'] as String,
      endpoint: row['endpoint'] as String,
      payload: jsonDecode(row['payload'] as String) as Map<String, dynamic>,
      schemaVersion: (row['schema_version'] as num).toInt(),
      userId: row['user_id'] as String,
      deviceId: row['device_id'] as String,
      deviceTimestamp: DateTime.parse(row['device_timestamp'] as String).toUtc(),
      status: MutationStatus.fromString(row['status'] as String),
      retryCount: (row['retry_count'] as num).toInt(),
      lastError: row['last_error'] as String?,
      createdAt: DateTime.parse(row['created_at'] as String).toUtc(),
    );
  }

  Map<String, dynamic> toRow() {
    return {
      'idempotency_key': idempotencyKey,
      'operation_type': operationType,
      'endpoint': endpoint,
      'payload': jsonEncode(payload),
      'schema_version': schemaVersion,
      'user_id': userId,
      'device_id': deviceId,
      'device_timestamp': deviceTimestamp.toIso8601String(),
      'status': status.value,
      'retry_count': retryCount,
      'last_error': lastError,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

/// Conflict Event emitted when a server revalidation rejects a queued mutation.
class MutationConflictEvent {
  final OfflineMutationEnvelope envelope;
  final ClothingApiException serverException;

  MutationConflictEvent({required this.envelope, required this.serverException});
}

/// Offline Mutation Queue with UUID Idempotency and Conflict Model.
///
/// Rules:
/// 1. Server state and permissions are ALWAYS revalidated upon synchronization.
/// 2. Offline queued mutations NEVER grant authority or alter server balance directly.
/// 3. Conflicting mutations (over-pick, expired batch, modified record) transition to [MutationStatus.conflict]
///    and halt automatic retry until the user explicitly resolves or discards them.
class OfflineMutationQueue {
  final ClothingEncryptedDb encryptedDb;

  final _conflictController = StreamController<MutationConflictEvent>.broadcast();
  Stream<MutationConflictEvent> get conflictStream => _conflictController.stream;

  OfflineMutationQueue({required this.encryptedDb});

  /// Enqueue a mutation for synchronization.
  Future<String> enqueue({
    required String operationType,
    required String endpoint,
    required Map<String, dynamic> payload,
    required String userId,
    required String deviceId,
    int schemaVersion = 1,
    String? explicitIdempotencyKey,
  }) async {
    final db = await encryptedDb.open();
    final idempotencyKey = explicitIdempotencyKey ?? const Uuid().v4();
    final now = DateTime.now().toUtc();

    final envelope = OfflineMutationEnvelope(
      idempotencyKey: idempotencyKey,
      operationType: operationType,
      endpoint: endpoint,
      payload: payload,
      schemaVersion: schemaVersion,
      userId: userId,
      deviceId: deviceId,
      deviceTimestamp: now,
      status: MutationStatus.pending,
      retryCount: 0,
      createdAt: now,
    );

    await db.insert(
      'offline_mutation_queue',
      envelope.toRow(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    return idempotencyKey;
  }

  /// Retrieve all pending mutations in FIFO order.
  Future<List<OfflineMutationEnvelope>> getPendingMutations() async {
    final db = await encryptedDb.open();
    final rows = await db.query(
      'offline_mutation_queue',
      where: 'status = ?',
      whereArgs: [MutationStatus.pending.value],
      orderBy: 'created_at ASC',
    );
    return rows.map(OfflineMutationEnvelope.fromRow).toList();
  }

  /// Retrieve all mutations currently halted in conflict state.
  Future<List<OfflineMutationEnvelope>> getConflictMutations() async {
    final db = await encryptedDb.open();
    final rows = await db.query(
      'offline_mutation_queue',
      where: 'status = ?',
      whereArgs: [MutationStatus.conflict.value],
      orderBy: 'created_at ASC',
    );
    return rows.map(OfflineMutationEnvelope.fromRow).toList();
  }

  /// Synchronize all pending mutations through the versioned API client.
  Future<int> processPendingQueue(ClothingApiClient apiClient) async {
    final pending = await getPendingMutations();
    var processedCount = 0;

    for (final item in pending) {
      final db = await encryptedDb.open();
      // Mark in-flight under transaction
      await db.update(
        'offline_mutation_queue',
        {'status': MutationStatus.inFlight.value},
        where: 'idempotency_key = ?',
        whereArgs: [item.idempotencyKey],
      );

      try {
        await apiClient.post(
          item.endpoint,
          body: item.payload,
          idempotencyKey: item.idempotencyKey,
        );

        // Success: Remove from queue cleanly
        await db.delete(
          'offline_mutation_queue',
          where: 'idempotency_key = ?',
          whereArgs: [item.idempotencyKey],
        );
        processedCount++;
      } on ClothingApiException catch (e) {
        if (_isConflictError(e.errorCode)) {
          // Transition to CONFLICT: halt retries and alert user
          await db.update(
            'offline_mutation_queue',
            {
              'status': MutationStatus.conflict.value,
              'last_error': '${e.errorCode.code}: ${e.message}',
            },
            where: 'idempotency_key = ?',
            whereArgs: [item.idempotencyKey],
          );
          _conflictController.add(
            MutationConflictEvent(envelope: item, serverException: e),
          );
        } else if (e.errorCode == ClothingErrorCode.networkOffline) {
          // Transient network failure: return to pending for next cycle
          await db.update(
            'offline_mutation_queue',
            {
              'status': MutationStatus.pending.value,
              'retry_count': item.retryCount + 1,
              'last_error': 'Network offline',
            },
            where: 'idempotency_key = ?',
            whereArgs: [item.idempotencyKey],
          );
          break; // Stop queue processing if network dropped
        } else {
          // Permanent or unrecoverable client validation error
          await db.update(
            'offline_mutation_queue',
            {
              'status': MutationStatus.failed.value,
              'retry_count': item.retryCount + 1,
              'last_error': '${e.errorCode.code}: ${e.message}',
            },
            where: 'idempotency_key = ?',
            whereArgs: [item.idempotencyKey],
          );
        }
      } catch (err) {
        // Unexpected error
        await db.update(
          'offline_mutation_queue',
          {
            'status': MutationStatus.pending.value,
            'retry_count': item.retryCount + 1,
            'last_error': err.toString(),
          },
          where: 'idempotency_key = ?',
          whereArgs: [item.idempotencyKey],
        );
      }
    }

    return processedCount;
  }

  /// Resolve a conflicted mutation: either discard it or reset to pending for retry.
  Future<void> resolveConflict(String idempotencyKey, {required bool discard}) async {
    final db = await encryptedDb.open();
    if (discard) {
      await db.delete(
        'offline_mutation_queue',
        where: 'idempotency_key = ?',
        whereArgs: [idempotencyKey],
      );
    } else {
      await db.update(
        'offline_mutation_queue',
        {
          'status': MutationStatus.pending.value,
          'last_error': null,
        },
        where: 'idempotency_key = ?',
        whereArgs: [idempotencyKey],
      );
    }
  }

  static bool _isConflictError(ClothingErrorCode code) {
    switch (code) {
      case ClothingErrorCode.concurrencyConflict:
      case ClothingErrorCode.idempotencyMismatch:
      case ClothingErrorCode.wrongItem:
      case ClothingErrorCode.wrongBatch:
      case ClothingErrorCode.expiredBatch:
      case ClothingErrorCode.wrongSerial:
      case ClothingErrorCode.overPick:
      case ClothingErrorCode.overReturn:
      case ClothingErrorCode.unauthorizedWarehouse:
      case ClothingErrorCode.unauthorizedTerritory:
        return true;
      default:
        return false;
    }
  }

  void dispose() {
    _conflictController.close();
  }
}
