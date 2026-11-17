// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';
import 'warehouse_app.dart';

/// Entrypoint for Clothing Warehouse Mobile application.
///
/// Target Roles:
/// - Clothing Warehouse Manager
/// - Clothing Business Administrator
///
/// Security & Architectural Invariants:
/// - Strictly manager-only access (operator accounts retired/rejected).
/// - Enforces TLS 1.2+ with strict hostname validation.
/// - Stores OAuth2 PKCE tokens in hardware-backed secure storage.
/// - Encrypts local persistence using SQLCipher 256-bit AES.
/// - Offline barcode scans are queued locally, but native document creation and stock
///   transitions remain strictly BLOCKED until online server reconciliation succeeds with zero conflicts.
/// - Post-refurbishment reinspection must pass before restocking into saleable inventory.
/// - Thermal printer payloads are validated to ensure zero secrets, passwords, or customer financial data.
void main() async {
  const appId = 'com.clothingerp.warehouse';
  const appVersion = '1.0.0';

  // 1. Hardware Secure Storage & Cryptography
  final secureStorage = KeyStoreSecureStorage();

  // 2. Strict TLS & API Client
  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_warehouse_mobile',
    redirectUri: 'com.clothingerp.warehouse://oauth/callback',
    secureStorage: secureStorage,
  );

  final apiClient = ClothingApiClient(
    baseUrl: Uri.parse('https://clothing.local'),
    authManager: authManager,
    tlsConfig: tlsConfig,
    clientAppId: appId,
    clientAppVersion: appVersion,
  );

  // 3. Encrypted SQLCipher Database & Schema Initialization
  final encryptedDb = ClothingEncryptedDb(
    dbName: 'clothing_warehouse_encrypted.db',
    secureStorage: secureStorage,
  );

  final localCache = WarehouseLocalCache(encryptedDb: encryptedDb);
  await localCache.initializeSchema();

  // 4. Peripheral Hardware & Scanner Controllers
  final scannerController = MobileScannerController(
    debounceWindow: const Duration(milliseconds: 50),
    suppressDuplicates: true,
  );

  final photoManager = SafePhotoManager();

  // 5. Session Lifecycle & Remote Revocation Listener
  final sessionLifecycle = SessionLifecycleManager(
    authManager: authManager,
    secureStorage: secureStorage,
    onLocalDataWipeRequested: () async {
      await localCache.wipeAllCaches();
    },
  );

  // 6. Domain Services
  final warehouseApiService = WarehouseApiService(apiClient: apiClient);
  final printerService = PrinterService(apiService: warehouseApiService);

  final fulfillmentManager = FulfillmentManager(
    apiService: warehouseApiService,
    localCache: localCache,
  );

  final returnsManager = ReturnsManager(
    apiService: warehouseApiService,
    localCache: localCache,
    photoManager: photoManager,
  );

  // 7. Controllers
  final homeController = WarehouseHomeController(
    apiService: warehouseApiService,
    localCache: localCache,
    sessionLifecycle: sessionLifecycle,
  );

  final pickingController = PickingController(
    fulfillmentManager: fulfillmentManager,
    localCache: localCache,
    scannerController: scannerController,
  );

  final packingController = PackingController(
    fulfillmentManager: fulfillmentManager,
    printerService: printerService,
  );

  final dispatchController = DispatchController(
    fulfillmentManager: fulfillmentManager,
    photoManager: photoManager,
  );

  final returnsController = ReturnsController(
    returnsManager: returnsManager,
    scannerController: scannerController,
    photoManager: photoManager,
  );

  final refurbishmentController = RefurbishmentController(
    returnsManager: returnsManager,
  );

  final printerController = PrinterController(
    printerService: printerService,
  );

  final conflictsController = WarehouseConflictsController(
    localCache: localCache,
    fulfillmentManager: fulfillmentManager,
  );

  // 8. Bootstrap Manager Session
  try {
    await homeController.bootstrapSession();
  } catch (e) {
    // Graceful offline or unauthenticated startup
  }
}
