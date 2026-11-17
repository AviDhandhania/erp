// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

/// Standardized, Stable Mobile Error Codes aligned with Server Definitions.
enum ClothingErrorCode {
  authExpired('AUTH_EXPIRED', 'Your session has expired. Please log in again.'),
  authInvalid('AUTH_INVALID', 'Invalid credentials or authorization code.'),
  unauthorizedRole('UNAUTHORIZED_ROLE', 'You do not have the required role for this action.'),
  unauthorizedWarehouse('UNAUTHORIZED_WAREHOUSE', 'You do not have access to this warehouse location.'),
  unauthorizedTerritory('UNAUTHORIZED_TERRITORY', 'You do not have access to retailers in this territory.'),
  wrongItem('WRONG_ITEM', 'Scanned item does not match expectation.'),
  wrongBatch('WRONG_BATCH', 'Scanned batch does not match expectation.'),
  expiredBatch('EXPIRED_BATCH', 'The scanned batch has expired and cannot be processed.'),
  wrongSerial('WRONG_SERIAL', 'Scanned serial number is invalid or not allocated to this document.'),
  overPick('OVER_PICK', 'Scanned quantity exceeds remaining balance on pick list.'),
  overReturn('OVER_RETURN', 'Return quantity exceeds delivered balance on invoice/delivery note.'),
  concurrencyConflict('CONCURRENCY_CONFLICT', 'Record was modified by another user or session. Please refresh.'),
  idempotencyMismatch('IDEMPOTENCY_MISMATCH', 'Conflicting payload submitted with existing idempotency key.'),
  rateLimited('RATE_LIMITED', 'Too many requests. Please slow down and try again.'),
  versionDeprecated('VERSION_DEPRECATED', 'This version of the application is no longer supported. Please update.'),
  networkOffline('NETWORK_OFFLINE', 'Device is offline. Mutation saved to encrypted queue.'),
  validationFailed('VALIDATION_FAILED', 'Input data validation failed.'),
  serverError('SERVER_ERROR', 'Internal server error occurred. Please contact support.');

  final String code;
  final String defaultMessage;

  const ClothingErrorCode(this.code, this.defaultMessage);

  static ClothingErrorCode fromString(String? codeStr) {
    if (codeStr == null) return ClothingErrorCode.serverError;
    for (final val in ClothingErrorCode.values) {
      if (val.code.toLowerCase() == codeStr.toLowerCase()) {
        return val;
      }
    }
    return ClothingErrorCode.serverError;
  }
}

/// Rich, Typed API Exception for Mobile Clients.
class ClothingApiException implements Exception {
  final int statusCode;
  final ClothingErrorCode errorCode;
  final String message;
  final Map<String, dynamic>? details;
  final DateTime timestamp;

  ClothingApiException({
    required this.statusCode,
    required this.errorCode,
    required this.message,
    this.details,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now().toUtc();

  @override
  String toString() => 'ClothingApiException(status: $statusCode, code: ${errorCode.code}, message: $message)';

  factory ClothingApiException.fromResponse(int statusCode, Map<String, dynamic> body) {
    final codeStr = body['error_code'] as String? ?? body['exc_type'] as String?;
    final msg = body['message'] as String? ?? body['_server_messages'] as String? ?? 'An unexpected error occurred.';
    return ClothingApiException(
      statusCode: statusCode,
      errorCode: ClothingErrorCode.fromString(codeStr),
      message: msg,
      details: body,
    );
  }

  factory ClothingApiException.offline() {
    return ClothingApiException(
      statusCode: 0,
      errorCode: ClothingErrorCode.networkOffline,
      message: ClothingErrorCode.networkOffline.defaultMessage,
    );
  }
}
