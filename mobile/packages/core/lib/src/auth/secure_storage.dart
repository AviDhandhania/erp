// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'token_model.dart';

/// Abstract Contract for Hardware-Backed Secure Storage.
abstract class ClothingSecureStorage {
  Future<void> write(String key, String value);
  Future<String?> read(String key);
  Future<void> delete(String key);
  Future<void> deleteAll();

  Future<void> saveToken(ClothingTokenModel token);
  Future<ClothingTokenModel?> getToken();
  Future<void> clearToken();

  Future<void> saveDatabaseEncryptionKey(String key);
  Future<String?> getDatabaseEncryptionKey();
}

/// Production Implementation backed by iOS Keychain & Android Keystore.
///
/// Configuration Guarantees:
/// - iOS: `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` (hardware encrypted, excluded from iCloud backups).
/// - Android: `EncryptedSharedPreferences` using AES-256 GCM backed by Android KeyStore.
class KeyStoreSecureStorage implements ClothingSecureStorage {
  final FlutterSecureStorage _storage;

  KeyStoreSecureStorage({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(
                encryptedSharedPreferences: true,
                resetOnError: false,
              ),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock_this_device,
                synchronizable: false,
              ),
            );

  static const _tokenKey = 'clothing_auth_token_v1';
  static const _dbKey = 'clothing_sqlcipher_encryption_key_v1';

  @override
  Future<void> write(String key, String value) => _storage.write(key: key, value: value);

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);

  @override
  Future<void> deleteAll() => _storage.deleteAll();

  @override
  Future<void> saveToken(ClothingTokenModel token) async {
    final serialized = jsonEncode(token.toJson());
    await write(_tokenKey, serialized);
  }

  @override
  Future<ClothingTokenModel?> getToken() async {
    final serialized = await read(_tokenKey);
    if (serialized == null || serialized.isEmpty) return null;
    try {
      final json = jsonDecode(serialized) as Map<String, dynamic>;
      final userId = json['user_id'] as String? ?? 'unknown';
      return ClothingTokenModel.fromJson(json, userId);
    } catch (_) {
      await delete(_tokenKey);
      return null;
    }
  }

  @override
  Future<void> clearToken() => delete(_tokenKey);

  @override
  Future<void> saveDatabaseEncryptionKey(String key) => write(_dbKey, key);

  @override
  Future<String?> getDatabaseEncryptionKey() => read(_dbKey);
}

/// In-Memory implementation for Hermetic Unit & CI Testing.
class InMemorySecureStorage implements ClothingSecureStorage {
  final Map<String, String> _data = {};

  @override
  Future<void> write(String key, String value) async => _data[key] = value;

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> delete(String key) async => _data.remove(key);

  @override
  Future<void> deleteAll() async => _data.clear();

  @override
  Future<void> saveToken(ClothingTokenModel token) async {
    _data['token'] = jsonEncode(token.toJson());
  }

  @override
  Future<ClothingTokenModel?> getToken() async {
    final val = _data['token'];
    if (val == null) return null;
    final json = jsonDecode(val) as Map<String, dynamic>;
    return ClothingTokenModel.fromJson(json, json['user_id'] as String? ?? 'test');
  }

  @override
  Future<void> clearToken() async => _data.remove('token');

  @override
  Future<void> saveDatabaseEncryptionKey(String key) async => _data['db_key'] = key;

  @override
  Future<String?> getDatabaseEncryptionKey() async => _data['db_key'];
}
