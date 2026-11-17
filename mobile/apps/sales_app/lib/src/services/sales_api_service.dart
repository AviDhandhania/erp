// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/sales_dashboard_model.dart';
import '../models/retailer_model.dart';
import '../models/retailer_application_model.dart';
import '../models/retailer_visit_model.dart';
import '../models/catalogue_model.dart';
import '../models/cart_order_model.dart';
import '../models/collection_model.dart';
import '../models/delivery_follow_up_model.dart';
import '../models/supervision_model.dart';

/// Typed HTTP communication service interfacing with the Clothing ERP Field Sales backend.
///
/// Security:
/// - Enforces POST for all mutating state operations.
/// - Passes UUID idempotency keys via `X-Idempotency-Key` and request payloads.
/// - Requires valid session bearer tokens; never embeds static credentials.
class SalesApiService {
  final ClothingApiClient apiClient;

  SalesApiService({required this.apiClient});

  // -------------------------------------------------------------------------
  // 1. Bootstrap & Handshake
  // -------------------------------------------------------------------------

  Future<Map<String, dynamic>> getMobileBoot() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.get_mobile_boot',
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 2. Operational Dashboard
  // -------------------------------------------------------------------------

  Future<SalesDashboardModel> getOperationalDashboard() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.get_mobile_dashboard',
    );
    return SalesDashboardModel.fromJson(response.data);
  }

  // -------------------------------------------------------------------------
  // 3. Retailer Directory & Detail
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<RetailerModel>> getRetailers({
    String? search,
    String? group,
    int page = 1,
    int pageSize = 50,
  }) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
      if (group != null && group.isNotEmpty) 'group': group,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.get_mobile_retailers',
      queryParams: queryParams,
    );

    final rawList = response.data['retailers'] as List<dynamic>? ?? [];
    final items = rawList
        .whereType<Map<String, dynamic>>()
        .map((r) => RetailerModel.fromJson(r))
        .toList();

    return PaginatedResponse<RetailerModel>(
      items: items,
      page: response.data['page'] as int? ?? page,
      pageSize: response.data['page_size'] as int? ?? pageSize,
      hasMore: response.data['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> getRetailerExposure(String customer) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.get_retailer_stock_exposure',
      queryParams: {'customer': customer},
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 4. Product Catalogue Subset & Barcode Lookup
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<CatalogueTemplateModel>> getCatalogue({
    String? search,
    String? styleCode,
    String? collection,
    int page = 1,
    int pageSize = 50,
  }) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
      if (styleCode != null && styleCode.isNotEmpty) 'style_code': styleCode,
      if (collection != null && collection.isNotEmpty) 'collection': collection,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.get_mobile_catalogue',
      queryParams: queryParams,
    );

    final rawTemplates = response.data['templates'] as List<dynamic>? ?? [];
    final items = rawTemplates
        .whereType<Map<String, dynamic>>()
        .map((t) => CatalogueTemplateModel.fromJson(t, isStale: false))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<CatalogueTemplateModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> resolveBarcode(
    String barcode, {
    String operation = 'catalogue_lookup',
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.barcodes.resolve_scan',
      body: {
        'barcode': barcode,
        'operation': operation,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 5. Cart, Repricing & Orders
  // -------------------------------------------------------------------------

  /// Calls server repricing & exposure preflight prior to order placement.
  /// Enforces that client cached prices and stock are strictly non-authoritative.
  Future<Map<String, dynamic>> prepriceAndCheckExposure({
    required String customer,
    required List<Map<String, dynamic>> items,
    String? company,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.pricing.preprice_sales_order',
      body: {
        'customer': customer,
        'items': items,
        if (company != null) 'company': company,
      },
    );
    return response.data;
  }

  Future<SalesOrderModel> createOrder({
    required String customer,
    required List<Map<String, dynamic>> items,
    required String requestId,
    DateTime? deliveryDate,
    String? company,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.create_mobile_order',
      idempotencyKey: requestId,
      body: {
        'customer': customer,
        'items': items,
        'request_id': requestId,
        if (deliveryDate != null) 'delivery_date': deliveryDate.toIso8601String().substring(0, 10),
        if (company != null) 'company': company,
      },
    );
    return SalesOrderModel.fromJson(response.data);
  }

  Future<PaginatedResponse<SalesOrderModel>> getOrders({
    String? search,
    String state = 'all',
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String, String>{
      'state': state,
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.get_clothing_orders',
      queryParams: queryParams,
    );

    final rawOrders = response.data['orders'] as List<dynamic>? ?? [];
    final items = rawOrders
        .whereType<Map<String, dynamic>>()
        .map((o) => SalesOrderModel.fromJson(o))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<SalesOrderModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<SalesOrderModel> submitOrder(String orderName) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.submit_clothing_order',
      body: {'name': orderName},
    );
    return SalesOrderModel.fromJson(response.data);
  }

  Future<SalesOrderModel> rejectOrder(String orderName, String reason) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.reject_clothing_order',
      body: {
        'name': orderName,
        'reason': reason,
      },
    );
    return SalesOrderModel.fromJson(response.data);
  }

  Future<SalesOrderModel> resubmitOrder(
    String orderName, {
    List<Map<String, dynamic>>? items,
    DateTime? deliveryDate,
    String? notes,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.resubmit_clothing_order',
      body: {
        'name': orderName,
        if (items != null) 'items': items,
        if (deliveryDate != null) 'delivery_date': deliveryDate.toIso8601String().substring(0, 10),
        if (notes != null) 'notes': notes,
      },
    );
    return SalesOrderModel.fromJson(response.data);
  }

  Future<SalesOrderModel> cancelOrder(String orderName) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.ordering.cancel_clothing_order',
      body: {'name': orderName},
    );
    return SalesOrderModel.fromJson(response.data);
  }

  // -------------------------------------------------------------------------
  // 6. Visits & Obligations
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<VisitObligationModel>> getVisitObligations({
    String? obligationType,
    String? status,
    String? territory,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (obligationType != null) 'obligation_type': obligationType,
      if (status != null) 'status': status,
      if (territory != null) 'territory': territory,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.cadence.get_asm_cadence_directory',
      queryParams: queryParams,
    );

    final rawList = response.data['obligations'] as List<dynamic>? ?? [];
    final items = rawList
        .whereType<Map<String, dynamic>>()
        .map((o) => VisitObligationModel.fromJson(o))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<VisitObligationModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> submitVisitReport(
    RetailerVisitReportModel report, {
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.mobile_api.submit_mobile_visit',
      idempotencyKey: requestId,
      body: {
        'customer': report.customer,
        'visit_date': report.visitDate.toIso8601String().substring(0, 10),
        'outcome': report.outcome,
        if (report.notes != null) 'notes': report.notes,
        if (report.latitude != null) 'latitude': report.latitude,
        if (report.longitude != null) 'longitude': report.longitude,
        if (report.accuracyMeters != null) 'accuracy': report.accuracyMeters,
        'consent': report.consentGiven ? 1 : 0,
        if (report.checkinPhotoUrl != null) 'photo_file': report.checkinPhotoUrl,
        if (requestId != null) 'request_id': requestId,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 7. Retailer Application & Private Evidence
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<RetailerApplicationModel>> getApplicationQueue({
    String queueType = 'pending',
    int page = 1,
    int pageSize = 50,
  }) async {
    final start = (page - 1) * pageSize;
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.get_retailer_application_queue',
      queryParams: {
        'queue_type': queueType,
        'limit': pageSize.toString(),
        'start': start.toString(),
      },
    );

    final rawList = response.data['applications'] as List<dynamic>? ?? [];
    final items = rawList
        .whereType<Map<String, dynamic>>()
        .map((a) => RetailerApplicationModel.fromJson(a))
        .toList();

    return PaginatedResponse<RetailerApplicationModel>(
      items: items,
      page: page,
      pageSize: pageSize,
      hasMore: items.length >= pageSize,
    );
  }

  Future<RetailerApplicationModel> submitRetailerApplication(
    RetailerApplicationModel application, {
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.submit_application',
      idempotencyKey: requestId,
      body: application.toJson(),
    );
    return RetailerApplicationModel.fromJson(response.data);
  }

  Future<Map<String, dynamic>> requestMoreInfoApplication(
    String name,
    String comments,
  ) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.request_more_info',
      body: {
        'name': name,
        'comments': comments,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> resubmitApplication(
    String name, {
    String? notes,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.resubmit',
      body: {
        'name': name,
        if (notes != null) 'notes': notes,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> approveApplication(
    String name, {
    double? initialCreditLimit,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.approve',
      body: {
        'name': name,
        if (initialCreditLimit != null) 'initial_credit_limit': initialCreditLimit,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> rejectApplication(
    String name,
    String reason,
  ) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.reject',
      body: {
        'name': name,
        'reason': reason,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> updateCommercialFields(
    String name,
    Map<String, dynamic> updates,
  ) async {
    final body = <String, dynamic>{'name': name, ...updates};
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.sales_erp.doctype.retailer_application.retailer_application.update_commercial_fields',
      body: body,
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 8. 90–120 Day Collection Worklist
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<CollectionInvoiceModel>> getCollectionWorklist({
    String? customer,
    String? targetDate,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (customer != null) 'customer': customer,
      if (targetDate != null) 'target_date': targetDate,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.cadence.get_collection_obligations',
      queryParams: queryParams,
    );

    final rawList = response.data['collections'] as List<dynamic>? ?? [];
    final items = rawList
        .whereType<Map<String, dynamic>>()
        .map((c) => CollectionInvoiceModel.fromJson(c))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<CollectionInvoiceModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> recordCollectionFollowUp(
    CollectionFollowUpOutcome outcome,
  ) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.cadence.record_collection_follow_up',
      body: outcome.toJson(),
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 9. Delivery Follow-Up
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<DeliveryFollowUpModel>> getDeliveryFollowUps({
    String status = 'all',
    String? search,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String, String>{
      'status': status,
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.delivery_follow_up.get_delivery_follow_up_obligations',
      queryParams: queryParams,
    );

    final rawList = response.data['obligations'] as List<dynamic>? ?? [];
    final items = rawList
        .whereType<Map<String, dynamic>>()
        .map((d) => DeliveryFollowUpModel.fromJson(d))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<DeliveryFollowUpModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> recordDeliveryFollowUp({
    required String obligation,
    required String outcome,
    String? contactPerson,
    String? contactDatetime,
    String? issueNotes,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/sales_erp.delivery_follow_up.record_delivery_follow_up',
      body: {
        'obligation': obligation,
        'outcome': outcome,
        if (contactPerson != null) 'contact_person': contactPerson,
        if (contactDatetime != null) 'contact_datetime': contactDatetime,
        if (issueNotes != null) 'issue_notes': issueNotes,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 10. RSM Supervision
  // -------------------------------------------------------------------------

  Future<RsmSupervisionOverviewModel> getRsmSupervisionOverview() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/sales_erp.supervision.get_rsm_supervision_overview',
    );
    return RsmSupervisionOverviewModel.fromJson(response.data);
  }
}
