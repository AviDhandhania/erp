// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import 'package:clothing_design_system/clothing_design_system.dart';
import 'quality_app.dart';

/// Entrypoint for Clothing Quality Mobile application.
///
/// Target Roles:
/// - Clothing Quality Inspector
/// - Clothing Quality Manager
/// - Clothing Business Administrator (High-risk Gate Reviews)
///
/// Security & Architectural Invariants:
/// - Multi-company and supplier isolation enforced server-side.
/// - Stores OAuth2 PKCE tokens in hardware-backed secure storage.
/// - Encrypts local persistence using SQLCipher 256-bit AES (`ClothingEncryptedDb`).
/// - Strict cryptographic wipe (`destroyAndWipe`) on logout or role revocation.
/// - High-risk Administrator approvals strictly require online connectivity,
///   an exact immutable review bundle with SHA-256 fingerprint, and strong reauthentication.
/// - Controlled report viewing with ephemeral device storage; zero permanent private URLs exposed.
void main() async {
  const appId = 'com.clothingerp.quality';
  const appVersion = '1.0.0';

  // 1. Hardware Secure Storage & Cryptography
  final secureStorage = KeyStoreSecureStorage();

  // 2. Strict TLS & API Client
  final tlsConfig = ClothingTlsConfig(
    allowedHost: 'clothing.local',
  );

  final authManager = ClothingAuthManager(
    serverBaseUrl: Uri.parse('https://clothing.local'),
    clientId: 'clothing_quality_mobile',
    redirectUri: 'com.clothingerp.quality://oauth/callback',
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
    dbName: 'clothing_quality_encrypted.db',
    secureStorage: secureStorage,
  );

  final localCache = QualityLocalCache(encryptedDb: encryptedDb);
  await localCache.initializeSchema();

  final photoManager = SafePhotoManager();

  // 4. Session Lifecycle & Remote Revocation Listener
  final controlledReportManager = ControlledReportManager(
    apiService: QualityApiService(apiClient: apiClient),
  );

  final sessionLifecycle = SessionLifecycleManager(
    authManager: authManager,
    secureStorage: secureStorage,
    onLocalDataWipeRequested: () async {
      await localCache.wipeAllCaches();
      await controlledReportManager.wipeAllReports();
    },
  );

  // 5. Domain Services
  final qualityApiService = QualityApiService(apiClient: apiClient);
  final cycleManager = QualityCycleManager(
    apiService: qualityApiService,
    localCache: localCache,
  );
  final inspectionManager = QualityInspectionManager(
    apiService: qualityApiService,
    localCache: localCache,
    photoManager: photoManager,
  );
  final dispositionManager = QuarantineDispositionManager(
    apiService: qualityApiService,
    localCache: localCache,
    photoManager: photoManager,
  );
  final gateReviewManager = GateReviewManager(
    apiService: qualityApiService,
  );

  // 6. Controllers
  final homeController = QualityHomeController(
    apiService: qualityApiService,
    localCache: localCache,
    sessionLifecycle: sessionLifecycle,
  );
  final cyclesController = CyclesController(
    cycleManager: cycleManager,
  );
  final inspectionController = InspectionController(
    inspectionManager: inspectionManager,
  );
  final revisionController = RevisionController(
    inspectionManager: inspectionManager,
  );
  final quarantineController = ReturnQuarantineController(
    dispositionManager: dispositionManager,
  );
  final gateReviewController = GateReviewController(
    gateReviewManager: gateReviewManager,
  );
  final reportController = ControlledReportController(
    reportManager: controlledReportManager,
  );

  // 7. Bootstrap Inspector Session
  try {
    await homeController.loadDashboard();
  } catch (e) {
    // Graceful offline or unauthenticated startup
  }
}
