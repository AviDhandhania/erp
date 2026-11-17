# Mobile Application Signing, Distribution, and Key Management Architecture

## 1. Core Security Doctrine

1. **Zero Committed Signing Material**:
   - Android release keystores (`.jks`, `.keystore`), key passwords, store passwords, and alias names must **NEVER** be committed to Git.
   - Apple distribution certificates (`.p12`), provisioning profiles (`.mobileprovision`), and App Store Connect API keys must **NEVER** be committed to Git.
2. **Pull Request Isolation**:
   - Pull request CI workflows never have access to production signing credentials.
   - PR builds produce unsigned or debug-signed binaries exclusively for automated testing.
3. **Protected Release Environments**:
   - Production signing executes exclusively inside a dedicated, isolated GitHub Actions environment (`production-mobile`) requiring manual approval by designated release managers.

---

## 2. Android Signing Architecture

### 2.1 Keystore Segregation
Each of the three applications maintains a distinct, dedicated release key:
- `com.clothingerp.sales`: `clothing-sales-release.jks`
- `com.clothingerp.warehouse`: `clothing-warehouse-release.jks`
- `com.clothingerp.quality`: `clothing-quality-release.jks`

### 2.2 Key Specification
- Algorithm: RSA 4096-bit or ECDSA P-384.
- Validity: Minimum 25 years.
- Digest Algorithm: SHA-256.

```bash
# Generation of dedicated release key (conducted in air-gapped security workstation):
keytool -genkeypair -v \
  -keystore clothing-sales-release.jks \
  -alias clothing_sales \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000 \
  -sigalg SHA256withRSA
```

### 2.3 CI Injection Mechanism
In GitHub Actions:
- The binary keystore is base64-encoded and stored in GitHub Encrypted Secrets: `ANDROID_KEYSTORE_SALES_BASE64`.
- Keystore passwords and alias passwords are stored in `ANDROID_KEYSTORE_PASSWORD` and `ANDROID_KEY_PASSWORD`.
- The CI runner decodes the keystore into an ephemeral runner directory and deletes it immediately after the build step:

```bash
echo "$ANDROID_KEYSTORE_SALES_BASE64" | base64 -d > /tmp/keystore.jks
# Execute build with gradle signing properties
rm -f /tmp/keystore.jks
```

---

## 3. iOS Signing Architecture

### 3.1 Profile and Certificate Segregation
- **Sales App**: `com.clothingerp.sales` with `Clothing Sales AppStore Profile`.
- **Warehouse App**: `com.clothingerp.warehouse` with `Clothing Warehouse In-House Profile`.
- **Quality App**: `com.clothingerp.quality` with `Clothing Quality In-House Profile`.

### 3.2 Secure Fastlane / GitHub Actions Provisioning
- Fastlane Match (or native GitHub Actions step) retrieves certificates encrypted with AES-256 from a private, access-controlled repository using an ephemeral encryption key (`MATCH_PASSWORD`).
- App Store Connect API Key (`AUTH_KEY_P8`) is injected via secrets to upload builds directly to TestFlight and Apple Business Manager.

---

## 4. Enterprise Distribution Channels

1. **Clothing Sales Mobile**:
   - Distributed via Google Play (Private Enterprise Track) and Apple Business Manager / TestFlight.
   - Deployed to company-owned and BYOD sales handsets managed via Microsoft Intune or Knox Mobile Enrollment.
2. **Clothing Warehouse Mobile**:
   - Distributed via Enterprise Mobile Device Management (MDM) / SOTI MobiControl directly to rugged Android handhelds (Zebra TC52/TC57, Honeywell CT40).
   - APK signed with in-house enterprise release key.
3. **Clothing Quality Mobile**:
   - Distributed via Enterprise MDM to dedicated inspection tablets and rugged smartphones.

---

## 5. Mobile SBOM & Supply Chain Verification

Every production release artifact is accompanied by:
1. **Software Bill of Materials (SBOM)**: Generated in CycloneDX 1.5 JSON and SPDX 2.3 format covering all direct and transitive Flutter/Dart dependencies.
2. **Dependency Vulnerability Attestation**: Scanned against GitHub Advisory Database and OSV.dev before build sign-off.
3. **SHA-256 Checksum Manifest**: Released alongside APK/IPA bundles for verification before MDM staging.
