# ADR-001: Mobile Framework Selection for Clothing ERP Suite

## Status
**Accepted** (2026-11-17)

## Deciders
- Enterprise Architecture & Security Team
- Mobile Platform Engineering
- Operations Leadership (Field Sales, Warehouse Fulfillment, Quality Control)

---

## Context and Problem Statement
The Clothing ERP Suite requires three distinct, dedicated production mobile applications:
1. **Clothing Sales Mobile**: Tailored for Area Sales Managers (ASM) and Regional Sales Managers (RSM) conducting field retail visits, order creation, catalogue browsing, and collection follow-ups.
2. **Clothing Warehouse Mobile**: Tailored for Warehouse Managers and logistics personnel executing high-speed pick/pack/dispatch, location transfer, and customer return intakes.
3. **Clothing Quality Mobile**: Tailored for Quality Inspectors and Quality Managers conducting 7-stage garment manufacturing inspections, measurement audits, and defect evidence photo uploads.

All three applications must operate in rugged, real-world conditions: intermittent or zero cellular connectivity (deep warehouse aisles, rural distributor shops), high-frequency barcode scanning (keyboard-wedge hardware scanners, camera viewfinders, OEM broadcast intents), strict multi-tenant and role-scoped authorization, and hardware-backed cryptographic storage for offline operations.

We must select an architectural framework that maximizes code reuse across common infrastructure (OAuth2/PKCE authentication, versioned API clients, encrypted offline databases, scanner abstraction, photo compression) while strictly enforcing separate application targets, distinct bundle identifiers, and zero risk of cross-role data leakage.

---

## Decision Drivers

1. **Security Posture & Least Privilege**:
   - Zero tolerance for WebView-based injection vulnerabilities (XSS, DOM storage theft, insecure bridge exploitation).
   - Direct native access to iOS Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`) and Android Keystore (hardware-backed AES-256 GCM encryption).
   - Strict TLS validation with hostname verification and custom certificate pinning support; zero "trust-all-certificates" bypasses.
   - Encrypted local persistence (SQLCipher / AES-256) with remote wipe capability upon logout or session revocation.

2. **Hardware Scanner & Peripheral Performance**:
   - High-throughput scanning: sub-50ms inter-character interval capture for USB/Bluetooth keyboard-wedge laser scanners.
   - Deep integration with rugged Android handhelds (Zebra DataWedge, Honeywell Mobility Edge) via native broadcast intents.
   - Responsive camera-based scanning with millisecond-grade focus and torch/flashlight control.

3. **Offline Reliability & Concurrency**:
   - Structured, encrypted offline write queues with UUID idempotency keys.
   - Reliable background synchronization that survives app backgrounding, memory pressure, and network transitions.
   - Concurrency-safe local storage that never corrupts under unexpected power loss.

4. **Multi-Target Architecture & Code Sharing**:
   - Capability to maintain three distinct branded applications with separate application/bundle identifiers (`com.clothingerp.sales`, `com.clothingerp.warehouse`, `com.clothingerp.quality`).
   - Shared core packages for networking, security, data models, design tokens, and hardware drivers to eliminate code duplication.

5. **Operational Viability & Maintainability**:
   - Single unified engineering codebase to avoid maintaining separate Swift and Kotlin codebases for three apps (which would require 6 codebases).
   - Strong static typing and compile-time null safety to prevent runtime crashes in field operations.

---

## Considered Options

### Option 1: Flutter (Dart) — *Preferred Candidate*
Flutter compiles Dart ahead-of-time (AOT) to native ARM64 machine code for iOS and Android. It renders UI via its own deterministic graphics pipeline (Impeller/Skia) without relying on system WebViews or JavaScript bridges.

### Option 2: Capacitor / Ionic / Progressive Web App (PWA)
Capacitor wraps a single-page web application (HTML/CSS/JavaScript) inside a native WebView container (`WKWebView` on iOS, `WebView` on Android), communicating with native APIs via a serialized JavaScript-to-Native bridge.

### Option 3: Separate Native Development (Swift / SwiftUI on iOS + Kotlin / Jetpack Compose on Android)
Building fully native applications for each platform using Apple and Google's respective first-party toolchains, languages, and UI frameworks.

---

## Comparative Analysis Matrix

| Evaluation Dimension | Option 1: Flutter (Dart) | Option 2: Capacitor / PWA | Option 3: Separate Native (Swift + Kotlin) |
| :--- | :--- | :--- | :--- |
| **Runtime Security & Attack Surface** | **High**: Compiles to native ARM64 binary. No browser sandbox, no DOM XSS vulnerabilities, no serialized JS bridge to exploit. | **Low**: Vulnerable to WebView-based attacks, DOM-based storage leakage (`localStorage`/IndexedDB are unencrypted), and JS bridge tampering. | **Highest**: Direct native binary execution; standard OS security models. |
| **Cryptographic Storage** | **High**: Direct native FFI to SQLCipher with hardware Keystore/Keychain key derivation via `flutter_secure_storage`. | **Low**: Plugins bridge to native keystore, but web storage primitives are inherently insecure. Memory leaks in WebView heap. | **Highest**: Direct OS Keychain and Keystore API access; zero abstraction penalty. |
| **Scanner Performance** | **High**: Native keyboard buffer event handling; seamless platform channels for Zebra/Honeywell broadcast intents. | **Medium/Low**: High latency in keyboard event propagation through WebView; sluggish camera frame analysis in web workers. | **Highest**: Zero-latency broadcast receiver registration and low-level camera pipeline. |
| **Offline Reliability & DB** | **High**: Embedded SQLite/SQLCipher runs directly in process thread; robust ACID guarantees independent of browser cache eviction. | **Low**: Browsers and WebViews can purge IndexedDB under OS memory pressure. Background sync is unreliable in iOS WebViews. | **Highest**: Native SQLite/Room/CoreData with OS background task schedulers. |
| **Code Reuse across 3 Apps** | **High**: 85%+ shared code across `core`, `design_system`, and networking. Thin entrypoints for 3 app targets. | **High**: Shared web components, but native plugin configurations must still be maintained per target. | **Lowest**: 0% code reuse between iOS and Android. Maintaining 3 distinct apps requires 6 separate application projects. |
| **UI Determinism & Fidelity** | **High**: Pixel-perfect rendering across all Android OEMs and iOS versions via dedicated engine. | **Medium/Low**: Inconsistent CSS quirks across older Android WebViews; sluggish scrolling on low-end rugged devices. | **High**: Platform-native look and feel, but requires duplicating custom UI components twice. |
| **Developer Maintenance** | **Optimal**: 1 language (Dart), 1 monorepo (`melos`), shared test suite, unified CI pipeline. | **Medium**: Requires web stack plus Cordova/Capacitor native wrapper troubleshooting. | **Prohibitive**: Requires dual skillsets (iOS Swift + Android Kotlin); 6 separate apps to build, test, and release. |

---

## Detailed Evaluation of Rejection Factors

### Why Capacitor / PWA is Rejected for Production
1. **Unacceptable Security Vulnerabilities**:
   - WebViews expose the application to cross-site scripting (XSS), token extraction from browser memory, and insecure JavaScript-to-native message handlers.
   - PWA local storage (`IndexedDB`) cannot be reliably encrypted with hardware-backed keys on either Android or iOS without severe performance degradation.
   - WebViews are subject to unpredictable system eviction policies: iOS WebKit can silently delete local storage if storage limits are reached, which would destroy pending offline field sales orders or unsubmitted pick lists.
2. **Peripheral & Scanner Latency**:
   - Warehouse barcode scanning requires sub-50ms keystroke capture. In WebView architectures, hardware keyboard wedge inputs pass through system input methods and browser DOM event loops, leading to dropped characters and input buffering delays.
   - Background barcode scanning via Zebra DataWedge broadcast intents requires constant background thread listening, which WebViews throttle aggressively.
3. **App Store & Device Lifecycle Compliance**:
   - Pure web wrappers often fail Apple App Store Review Guideline 4.2 (Minimum Functionality) and provide subpar gesture/animation responsiveness on budget Android devices used by field staff.

### Why Pure Native (Swift + Kotlin) is Rejected
1. **Unsustainable Maintenance Overhead**:
   - Delivering 3 distinct applications across 2 platforms natively would require authoring and maintaining **6 distinct codebases**:
     - Sales iOS (Swift) + Sales Android (Kotlin)
     - Warehouse iOS (Swift) + Warehouse Android (Kotlin)
     - Quality iOS (Swift) + Quality Android (Kotlin)
   - Every security fix, token rotation update, offline queue improvement, or API schema change would have to be implemented and tested twice in different languages.
2. **Increased Risk of Architectural Divergence**:
   - Subtle differences in crypto implementation, offline conflict resolution, and token expiry logic between iOS and Android would lead to fragmented bugs and inconsistent data in MariaDB.

---

## Decision Outcome

**Chosen Solution**: **Option 1: Flutter (Dart) with a Melos Monorepo Architecture**

### Justification
1. **Security & Cryptography**:
   - Flutter compiles to native AOT machine code, eliminating the WebView attack surface entirely.
   - Provides native FFI bindings to SQLCipher for full-database 256-bit AES encryption.
   - Robust, battle-tested community plugins (`flutter_secure_storage`, `local_auth`) interface directly with Apple Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`) and Android Keystore (`EncryptedSharedPreferences` backed by hardware TEE/StrongBox).
2. **Scanner & Device Parity**:
   - Raw keyboard listener captures rapid wedge input pulses (< 50ms) without UI lag.
   - Method/Event channels enable seamless binding to Honeywell and Zebra Enterprise broadcast intents.
   - Native camera controllers (`camera`, `mobile_scanner`) provide fluid 60fps frame analysis and direct torch/flashlight control.
3. **Unified Monorepo & Target Separation**:
   - A Melos-driven Dart monorepo (`mobile/`) cleanly separates shared infrastructure (`mobile/packages/core`, `mobile/packages/design_system`) from target applications (`mobile/apps/sales_app`, `mobile/apps/warehouse_app`, `mobile/apps/quality_app`).
   - Each application maintains its own unique application identifier (`com.clothingerp.sales`, `com.clothingerp.warehouse`, `com.clothingerp.quality`), distinct asset bundles, permissions, and role-gated navigation routes.
4. **Offline Resilience**:
   - Direct thread access to encrypted SQLite enables ACID-compliant offline write queues with UUID idempotency keys and transactional status transitions.

---

## Minimum Supported Versions and Standards
- **Android**: Minimum SDK 28 (Android 9.0 Pie), Target SDK 34 (Android 14).
- **iOS**: Minimum iOS 15.0, Target iOS 17+.
- **Dart / Flutter**: Dart 3.x+ with sound null safety.
- **TLS**: Strict TLS 1.2 and TLS 1.3 only; strict hostname validation; zero trust-all certificate bypasses.
- **Cryptography**: AES-256 GCM (local DB), PBKDF2/Argon2 key derivation, SHA-256 for integrity hashing.
- **Authentication**: OAuth 2.0 Authorization Code with PKCE (RFC 7636). Zero passwords or long-lived API secrets stored on device.

---

## Consequences

### Positive Consequences
- **Single Source of Truth**: All API contract models, error handling, offline queue mechanics, and security checks are authored once in `packages/core`.
- **High Performance**: Native 60fps UI on rugged and budget devices (e.g., Samsung Galaxy XCover, Zebra TC series).
- **Strict Isolation**: Distinct bundle identifiers ensure an ASM cannot open the Warehouse app, and a Warehouse Manager cannot open the Sales app on shared devices.
- **Zero WebView Vulnerabilities**: Eliminates DOM XSS, insecure web storages, and arbitrary URL loading vectors.

### Negative Consequences & Mitigations
- **Binary Size**: Flutter engine adds ~15MB to application package size.
  - *Mitigation*: Enable code shrinking (R8 on Android), split debug info (`--split-debug-info`), and strip unused native symbols.
- **Engine Upgrade Overhead**: Upgrading Flutter minor versions requires testing across Android and iOS toolchains.
  - *Mitigation*: Pin exact Flutter SDK version in `.fvmrc` and CI workflow files (`.github/workflows/mobile-ci.yml`).
