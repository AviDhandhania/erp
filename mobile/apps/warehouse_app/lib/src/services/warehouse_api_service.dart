// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:clothing_core/clothing_core.dart';
import '../models/warehouse_boot_model.dart';
import '../models/fulfillment_task_model.dart';
import '../models/pick_item_model.dart';
import '../models/packing_model.dart';
import '../models/delivery_handoff_model.dart';
import '../models/work_queue_model.dart';
import '../models/return_intake_model.dart';
import '../models/refurbishment_model.dart';
import '../models/printer_model.dart';

/// Typed API communication client for the Clothing Warehouse Mobile application.
///
/// Security:
/// - Enforces POST for all state mutations.
/// - Passes UUID idempotency keys via `X-Idempotency-Key` and body payloads.
/// - Strictly validates assigned warehouse boundaries on the server.
class WarehouseApiService {
  final ClothingApiClient apiClient;

  WarehouseApiService({required this.apiClient});

  // -------------------------------------------------------------------------
  // 1. Bootstrap & Handshake
  // -------------------------------------------------------------------------

  Future<WarehouseBootModel> getBoot() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_warehouse_boot',
    );
    return WarehouseBootModel.fromJson(response.data);
  }

  // -------------------------------------------------------------------------
  // 2. Fulfillment Work Queues & Tasks
  // -------------------------------------------------------------------------

  Future<PaginatedResponse<FulfillmentTaskModel>> getTasks({
    String taskType = 'pick',
    String state = 'all',
    int page = 1,
    int pageSize = 20,
    String? search,
  }) async {
    final queryParams = <String, String>{
      'task_type': taskType,
      'state': state,
      'page': page.toString(),
      'page_size': pageSize.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_tasks',
      queryParams: queryParams,
    );

    final rawTasks = response.data['tasks'] as List<dynamic>? ?? [];
    final items = rawTasks
        .whereType<Map<String, dynamic>>()
        .map((t) => FulfillmentTaskModel.fromJson(t))
        .toList();

    final pagination = response.data['pagination'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<FulfillmentTaskModel>(
      items: items,
      page: pagination['page'] as int? ?? page,
      pageSize: pagination['page_size'] as int? ?? pageSize,
      hasMore: pagination['has_more'] as bool? ?? false,
    );
  }

  Future<Map<String, dynamic>> getTaskDetail(String taskType, String name) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_task_detail',
      queryParams: {
        'task_type': taskType,
        'name': name,
      },
    );
    return response.data;
  }

  Future<List<WorkQueueModel>> getWorkQueues({
    String? warehouse,
    String queueType = 'wave',
  }) async {
    final queryParams = <String, String>{
      'queue_type': queueType,
      if (warehouse != null) 'warehouse': warehouse,
    };

    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_work_queues',
      queryParams: queryParams,
    );

    final rawQueues = response.data['queues'] as List<dynamic>? ?? [];
    return rawQueues
        .whereType<Map<String, dynamic>>()
        .map((q) => WorkQueueModel.fromJson(q))
        .toList();
  }

  // -------------------------------------------------------------------------
  // 3. Scan Verification & Picking
  // -------------------------------------------------------------------------

  Future<Map<String, dynamic>> verifyScan({
    required String pickList,
    required String location,
    required String barcode,
    int quantity = 1,
    String? warehouse,
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.verify_mobile_scan',
      idempotencyKey: requestId,
      body: {
        'pick_list': pickList,
        'location': location,
        'barcode': barcode,
        'quantity': quantity,
        if (warehouse != null) 'warehouse': warehouse,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> undoScan({
    required String pickList,
    required String location,
    String? barcode,
    int quantity = 1,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.undo_mobile_scan',
      body: {
        'pick_list': pickList,
        'location': location,
        if (barcode != null) 'barcode': barcode,
        'quantity': quantity,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> completePick(String pickList) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.complete_mobile_pick',
      body: {'pick_list': pickList},
    );
    return response.data;
  }

  Future<Map<String, dynamic>> splitShortageRow({
    required String pickList,
    required String locationId,
    required int unpickedQty,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.fulfillment.split_pick_shortage_row',
      body: {
        'pick_list': pickList,
        'location_name': locationId,
        'shortage_qty': unpickedQty,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 4. Packing, Dispatch & Carrier Handoff
  // -------------------------------------------------------------------------

  Future<Map<String, dynamic>> createDeliveryNote(String pickList) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.create_mobile_delivery_note',
      body: {'pick_list': pickList},
    );
    return response.data;
  }

  Future<PackingPackageModel> createPackingSlip(PackingPackageModel package) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.create_mobile_packing_slip',
      body: {
        'delivery_note': package.deliveryNote,
        'from_case_no': package.fromCaseNo,
        'to_case_no': package.toCaseNo,
        'package_barcode': package.packageBarcode,
        'gross_weight_pkg': package.grossWeightPkg,
        'net_weight_pkg': package.netWeightPkg,
        if (package.length != null) 'length': package.length,
        if (package.width != null) 'width': package.width,
        if (package.height != null) 'height': package.height,
        'dimension_uom': package.dimensionUom,
      },
    );
    return PackingPackageModel.fromJson(response.data);
  }

  Future<Map<String, dynamic>> dispatchDelivery({
    required String deliveryNote,
    String? transporterName,
    String? vehicleNo,
    String? lrNo,
    String? lrDate,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.dispatch_mobile_delivery',
      body: {
        'delivery_note': deliveryNote,
        if (transporterName != null) 'transporter_name': transporterName,
        if (vehicleNo != null) 'vehicle_no': vehicleNo,
        if (lrNo != null) 'lr_no': lrNo,
        if (lrDate != null) 'lr_date': lrDate,
      },
    );
    return response.data;
  }

  Future<DeliveryHandoffModel> recordHandoff(DeliveryHandoffModel handoff) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.record_mobile_handoff',
      idempotencyKey: handoff.requestId,
      body: handoff.toJson(),
    );
    return DeliveryHandoffModel.fromJson(response.data);
  }

  // -------------------------------------------------------------------------
  // 5. Customer Returns & Quarantine Isolation
  // -------------------------------------------------------------------------

  Future<ReturnIntakeModel> intakeReturn(ReturnIntakeModel returnModel) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.intake_mobile_return',
      idempotencyKey: returnModel.requestId,
      body: {
        'delivery_note': returnModel.deliveryNote,
        'item_code': returnModel.itemCode,
        'quantity': returnModel.returnQuantity,
        'quarantine_warehouse': returnModel.quarantineWarehouse,
        'return_reason': returnModel.returnReason,
        if (returnModel.serialNo != null) 'serial_no': returnModel.serialNo,
        if (returnModel.batchNo != null) 'batch_no': returnModel.batchNo,
        'photo_evidence': returnModel.photoUrls,
        if (returnModel.notes != null) 'notes': returnModel.notes,
        'request_id': returnModel.requestId,
      },
    );
    return ReturnIntakeModel.fromJson(response.data);
  }

  Future<Map<String, dynamic>> getReturnsDashboard({String? warehouse}) async {
    final queryParams = <String, String>{
      if (warehouse != null) 'warehouse': warehouse,
    };
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_returns_dashboard',
      queryParams: queryParams,
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 6. Refurbishment & Quality Gate Restocking
  // -------------------------------------------------------------------------

  Future<Map<String, dynamic>> moveRefurbishment({
    required String quarantineName,
    required String refurbishmentWarehouse,
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.move_mobile_refurbishment',
      idempotencyKey: requestId,
      body: {
        'quarantine_name': quarantineName,
        'refurbishment_warehouse': refurbishmentWarehouse,
        if (requestId != null) 'request_id': requestId,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> assignRefurbishment({
    required String quarantineName,
    required String assignee,
    required String operation,
    double estimatedCost = 0.0,
    String? consumedMaterial,
    String? photoBefore,
    String? notes,
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.assign_mobile_refurbishment',
      idempotencyKey: requestId,
      body: {
        'quarantine_name': quarantineName,
        'assignee': assignee,
        'operation': operation,
        'estimated_cost': estimatedCost,
        if (consumedMaterial != null) 'consumed_material': consumedMaterial,
        if (photoBefore != null) 'photo_before': photoBefore,
        if (notes != null) 'notes': notes,
        if (requestId != null) 'request_id': requestId,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> completeRefurbishmentWork({
    required String quarantineName,
    String? photoAfter,
    String? consumedMaterial,
    double? actualCost,
    String? notes,
    bool requireReinspection = true,
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.complete_mobile_refurbishment_work',
      idempotencyKey: requestId,
      body: {
        'quarantine_name': quarantineName,
        if (photoAfter != null) 'photo_after': photoAfter,
        if (consumedMaterial != null) 'consumed_material': consumedMaterial,
        if (actualCost != null) 'actual_cost': actualCost,
        if (notes != null) 'notes': notes,
        'require_reinspection': requireReinspection ? 1 : 0,
        if (requestId != null) 'request_id': requestId,
      },
    );
    return response.data;
  }

  Future<Map<String, dynamic>> completeRefurbishment({
    required String quarantineName,
    required String targetSaleableWarehouse,
    String? notes,
    String? requestId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.complete_mobile_refurbishment',
      idempotencyKey: requestId,
      body: {
        'quarantine_name': quarantineName,
        'target_saleable_warehouse': targetSaleableWarehouse,
        if (notes != null) 'notes': notes,
        if (requestId != null) 'request_id': requestId,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 7. Labels & Safe Printing
  // -------------------------------------------------------------------------

  Future<DocumentLabelModel> getDocumentLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'html',
  }) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.get_mobile_document_label',
      queryParams: {
        'doctype': doctype,
        'name': name,
        if (labelType != null) 'label_type': labelType,
        'label_format': labelFormat,
      },
    );
    return DocumentLabelModel.fromJson(response.data);
  }

  Future<Map<String, dynamic>> printTaskLabel({
    required String doctype,
    required String name,
    String? labelType,
    String labelFormat = 'html',
    bool simulateFailure = false,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/api/method/warehouse_erp.mobile_api.print_mobile_task_label',
      body: {
        'doctype': doctype,
        'name': name,
        if (labelType != null) 'label_type': labelType,
        'label_format': labelFormat,
        'simulate_failure': simulateFailure ? 1 : 0,
      },
    );
    return response.data;
  }

  // -------------------------------------------------------------------------
  // 8. Barcode Resolver
  // -------------------------------------------------------------------------

  Future<Map<String, dynamic>> resolveScan(
    String barcode, {
    String operation = 'picking',
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
}
