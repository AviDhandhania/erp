// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';

/// Entrypoint for Clothing Quality Mobile application.
///
/// Target Roles:
/// - Clothing Quality Inspector
/// - Clothing Quality Manager
///
/// Security:
/// Multi-company and supplier isolation enforced server-side.
void main() {
  const appId = 'com.clothingerp.quality';
  const appVersion = '1.0.0';

  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final secureStorage = KeyStoreSecureStorage();

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_quality_mobile',
    redirectUri: 'com.clothingerp.quality://oauth/callback',
    secureStorage: secureStorage,
  );

  final encryptedDb = ClothingEncryptedDb(
    dbName: 'clothing_quality_encrypted.db',
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

  // Ready for Session 18 Quality UI features
}
