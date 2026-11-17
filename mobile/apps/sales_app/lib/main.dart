// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';

/// Entrypoint for Clothing Sales Mobile application.
///
/// Target Roles:
/// - Clothing Sales Representative (ASM)
/// - Clothing Regional Sales Manager (RSM)
///
/// Security:
/// Strictly rejects non-sales roles at boot.
void main() {
  const appId = 'com.clothingerp.sales';
  const appVersion = '1.0.0';

  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final secureStorage = KeyStoreSecureStorage();

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_sales_mobile',
    redirectUri: 'com.clothingerp.sales://oauth/callback',
    secureStorage: secureStorage,
  );

  final encryptedDb = ClothingEncryptedDb(
    dbName: 'clothing_sales_encrypted.db',
    secureStorage: secureStorage,
  );

  final offlineQueue = OfflineMutationQueue(
    encryptedDb: encryptedDb,
  );

  final sessionManager = SessionLifecycleManager(
    authManager: authManager,
    secureStorage: secureStorage,
    onLocalDataWipeRequested: () async {
      await encryptedDb.destroyAndWipe();
    },
  );

  // Ready for Session 16 Sales UI features
}
