// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';
import 'sales_app.dart';

/// Entrypoint for Clothing Sales Mobile application.
///
/// Target Roles:
/// - Clothing Area Sales Manager (ASM) / Clothing Sales Representative
/// - Clothing Regional Sales Manager (RSM)
///
/// Security:
/// - Enforces TLS 1.2+ with strict hostname validation.
/// - Stores OAuth2 PKCE tokens in hardware-backed secure storage.
/// - Encrypts local persistence using SQLCipher 256-bit AES.
/// - Immediately wipes session tokens and local caches upon role revocation or user disable.
/// - Prices and stock from local cache are strictly non-authoritative; server revalidation is required.
void main() async {
  const appId = 'com.clothingerp.sales';
  const appVersion = '1.0.0';

  // 1. Hardware Secure Storage & Cryptography
  final secureStorage = KeyStoreSecureStorage();

  // 2. Strict TLS & API Client
  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_sales_mobile',
    redirectUri: 'com.clothingerp.sales://oauth/callback',
    secureStorage: secureStorage,
  );

  final apiClient = ClothingApiClient(
    baseUrl: Uri.parse('https://clothing.local'),
    authManager: authManager,
    tlsConfig: tlsConfig,
    clientAppId: appId,
    clientAppVersion: appVersion,
  );

  // 3. Encrypted SQLCipher Database & Offline Mutation Queue
  final encryptedDb = ClothingEncryptedDb(
    dbName: 'clothing_sales_encrypted.db',
    secureStorage: secureStorage,
  );

  final localCache = SalesLocalCache(encryptedDb: encryptedDb);
  await localCache.initializeSchema();

  final mutationQueue = OfflineMutationQueue(
    encryptedDb: encryptedDb,
  );

  // 4. Peripheral Hardware & Media Subsystems
  final scannerController = MobileScannerController();
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
  final salesApiService = SalesApiService(apiClient: apiClient);
  final orderManager = SalesOrderManager(
    apiService: salesApiService,
    localCache: localCache,
    mutationQueue: mutationQueue,
  );
  final visitManager = SalesVisitManager(
    apiService: salesApiService,
    localCache: localCache,
    mutationQueue: mutationQueue,
    photoManager: photoManager,
  );
  final applicationManager = SalesApplicationManager(
    apiService: salesApiService,
    localCache: localCache,
    photoManager: photoManager,
  );

  // 7. Controllers
  final homeController = SalesHomeController(
    apiService: salesApiService,
    sessionLifecycle: sessionLifecycle,
  );
  final directoryController = RetailerDirectoryController(
    apiService: salesApiService,
    localCache: localCache,
  );
  final catalogueController = CatalogueController(
    apiService: salesApiService,
    localCache: localCache,
    scannerController: scannerController,
  );
  final cartController = CartController(
    orderManager: orderManager,
    localCache: localCache,
  );
  final ordersController = OrdersController(
    apiService: salesApiService,
  );
  final visitsController = VisitsController(
    apiService: salesApiService,
    visitManager: visitManager,
  );
  final collectionsController = CollectionsController(
    apiService: salesApiService,
  );
  final deliveryController = DeliveryFollowUpController(
    apiService: salesApiService,
    scannerController: scannerController,
  );
  final supervisionController = RsmSupervisionController(
    apiService: salesApiService,
    applicationManager: applicationManager,
  );
  final conflictsController = ConflictsController(
    localCache: localCache,
    mutationQueue: mutationQueue,
  );

  // 8. Boot & Route Validation
  await homeController.loadDashboard();
}
