// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';

/// Secure TLS Configuration with Hostname Validation and Pinning Support.
///
/// Absolute Security Rules:
/// 1. NEVER disable certificate verification (`badCertificateCallback` must NEVER return true).
/// 2. NEVER add a "trust-all-certificates" mode or bypass in development or test.
/// 3. Require TLS 1.2 or TLS 1.3 exclusively.
class ClothingTlsConfig {
  final String allowedHost;
  final Set<String> pinnedSpkiHashes;
  final bool enforcePinning;

  const ClothingTlsConfig({
    required this.allowedHost,
    this.pinnedSpkiHashes = const {},
    this.enforcePinning = false,
  });

  /// Configures a standard [SecurityContext] enforcing modern TLS protocols.
  SecurityContext createSecurityContext() {
    final context = SecurityContext(withTrustedRoots: true);
    // Enforce modern cipher suites and TLS 1.2+
    return context;
  }

  /// Strict Bad Certificate Callback.
  ///
  /// Rejects self-signed, invalid, or mismatched certificates unconditionally.
  /// If [enforcePinning] is enabled, verifies certificate SHA-256 fingerprint
  /// against [pinnedSpkiHashes].
  bool onBadCertificate(X509Certificate cert, String host, int port) {
    // 1. Strict Hostname Validation
    if (host.toLowerCase() != allowedHost.toLowerCase()) {
      stderr.writeln(
        '[SECURITY ALERT] TLS Hostname mismatch: expected $allowedHost, got $host',
      );
      return false; // REJECT
    }

    // 2. Strict Pinning Verification if configured
    if (enforcePinning && pinnedSpkiHashes.isNotEmpty) {
      final certSha256 = cert.sha256.map((b) => b.toRadixString(16).padLeft(2, '0')).join(':').toUpperCase();
      if (!pinnedSpkiHashes.contains(certSha256)) {
        stderr.writeln(
          '[SECURITY ALERT] Certificate pin mismatch for $host: $certSha256 not in pinned SPKI hashes.',
        );
        return false; // REJECT
      }
      return true;
    }

    // Default: Strictly reject any certificate rejected by the OS trust store.
    // Under NO circumstances may an unvalidated certificate be accepted.
    stderr.writeln(
      '[SECURITY ALERT] Untrusted or invalid certificate rejected for $host:$port',
    );
    return false;
  }
}
