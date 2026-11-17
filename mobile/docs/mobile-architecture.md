# Clothing ERP Mobile Suite Architecture

## 1. Monorepo Structure

```
clothing_erp/mobile/
├── melos.yaml                      # Multi-package monorepo workspace configuration
├── pubspec.yaml                    # Workspace root
├── analysis_options.yaml           # Strict static analysis rules (no dynamic, null safety)
├── .fvmrc                          # Flutter SDK version pin (3.24.5)
├── docs/                           # Architecture, security & signing guidelines
│   ├── mobile-architecture.md
│   └── signing-and-distribution.md
├── scripts/                        # Mobile SBOM and supply-chain scanners
│   ├── generate_mobile_sbom.py
│   └── scan_mobile_dependencies.py
├── packages/                       # Shared reusable foundation packages
│   ├── core/                       # Auth, networking, encrypted DB, offline queue, scanner
│   │   ├── pubspec.yaml
│   │   └── lib/
│   │       ├── clothing_core.dart
│   │       └── src/
│   │           ├── accessibility/  # 48dp touch targets, semantic announcements
│   │           ├── auth/           # OAuth2 PKCE, KeyStore/KeyChain, session lifecycle
│   │           ├── l10n/           # English, Hindi, Marathi, Tamil, Bengali
│   │           ├── media/          # Safe photo compression, EXIF stripping, SHA-256
│   │           ├── network/        # Versioned API client, TLS, pagination, errors
│   │           ├── scanner/        # Keyboard-wedge buffer, camera, broadcast intents
│   │           └── storage/        # SQLCipher encrypted DB, UUID offline queue
│   └── design_system/              # UI tokens, themes, viewfinders, status badges
│       ├── pubspec.yaml
│       └── lib/
│           └── clothing_design_system.dart
└── apps/                           # Three separate application targets
    ├── sales_app/                  # com.clothingerp.sales (ASM/RSM)
    ├── warehouse_app/              # com.clothingerp.warehouse (Warehouse Manager)
    └── quality_app/                # com.clothingerp.quality (Quality Inspector/Manager)
```

---

## 2. Security Boundaries & Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Field Staff (ASM / Warehouse Mgr)
    participant App as Mobile App Target
    participant Storage as Keystore / Keychain
    participant Frappe as ERPNext Backend (OAuth2)
    participant LocalDB as SQLCipher Encrypted DB

    Note over App,Storage: App Boot & Session Verification
    App->>Storage: Read Token & DB Key
    alt Token Missing or Expired
        App->>Frappe: OAuth2 Authorize (PKCE S256 Challenge)
        User->>Frappe: Authenticate & Consent
        Frappe-->>App: Authorization Code
        App->>Frappe: Exchange Code + PKCE Verifier
        Frappe-->>App: Access Token + Refresh Token
        App->>Storage: Save Encrypted Tokens
    end

    Note over App,LocalDB: Offline Mutation Pipeline
    User->>App: Perform Action (Scan / Pick / Order)
    App->>LocalDB: Enqueue Mutation (UUID Idempotency Key, Status: Pending)
    App->>Frappe: POST /api/method/... (Header: X-Idempotency-Key)
    alt Network Available & Success
        Frappe-->>App: 200 OK (Validated State)
        App->>LocalDB: Delete Queued Mutation
    else Network Offline
        App->>App: Keep in Encrypted Queue (Retry on Reconnect)
    else Conflict (Expired Batch / Over-pick / Price Change)
        Frappe-->>App: 409 Conflict / Error Code
        App->>LocalDB: Transition to Conflict Status (Halt Retries)
        App->>User: Display Conflict Alert & Resolution UI
    end
```

---

## 3. Peripheral Scanner Subsystem

```mermaid
flowchart TD
    ScannerInput["Physical Scan Input"]
    Wedge["USB / Bluetooth Keyboard Wedge"]
    Camera["Camera Viewfinder Stream"]
    Intent["Android OEM Broadcast (Zebra/Honeywell)"]

    ScannerInput --> Wedge
    ScannerInput --> Camera
    ScannerInput --> Intent

    Wedge -->|"Inter-char buffer (<50ms)"| Controller["MobileScannerController"]
    Camera -->|"Frame barcode detector"| Controller
    Intent -->|"Broadcast receiver intent"| Controller

    Controller --> Debounce{"Debounce Check (1500ms) & Duplicate Suppression"}
    Debounce -->|Duplicate in window| Dropped["Discarded"]
    Debounce -->|Valid new scan| Pipeline["Resolve & Validate"]

    Pipeline --> Audio["Web Audio / Native Synth (880Hz / 220Hz)"]
    Pipeline --> Haptic["Haptic Vibration (navigator.vibrate / HapticFeedback)"]
    Pipeline --> Server["Server-side resolve_scan API"]
```

---

## 4. Minimum Supported Standards
- **Android**: Min SDK 28 (Android 9.0 Pie), Target SDK 34 (Android 14).
- **iOS**: Min iOS 15.0, Target iOS 17+.
- **Database**: SQLCipher 256-bit AES.
- **Network**: Strict TLS 1.2+ with hostname verification; zero trust-all-certificates bypass.
- **Idempotency**: UUID v4 client keys bound to server mutation transactions.
