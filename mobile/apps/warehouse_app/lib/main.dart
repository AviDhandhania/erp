// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';

/// Entrypoint for Clothing Warehouse Mobile application.
///
/// Target Roles:
/// - Clothing Warehouse Manager
///
/// Security:
/// Scoped strictly to authorized warehouses assigned to the manager.
void main() {
  const appId = 'com.clothingerp.warehouse';
  const appVersion = '1.0.0';

  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final secureStorage = KeyStoreSecureStorage();

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_warehouse_mobile',
    redirectUri: 'com.clothingerp.warehouse://oauth/callback',
    secureStorage: secureStorage,
  );

  final encryptedDb = ClothingEncryptedDb(
    dbName: 'clothing_warehouse_encrypted.db',
    secureStorage: secureStorage,
  );

  final offlineQueue = OfflineMutationQueue(
    encryptedDb: encryptedDb,
  );

  final scannerController = MobileScannerController(
    debounceWindow: const Duration(milliseconds: 1000),
    suppressDuplicates: true,
  );

  final sessionManager = SessionLifecycleManager(
    authManager: authManager,
    secureStorage: secureStorage,
    onLocalDataWipeRequested: () async {
      await encryptedDb.destroyAndWipe();
    },
  );

  // Ready for Session 17 Warehouse UI features
}
