// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'package:meta/meta.dart';

/// Single variant quantity entry in cart line item.
@immutable
class CartLineItem {
  final String templateCode;
  final String itemName;
  final String colour;
  final String size;
  final String itemCode; // Specific SKU
  final int quantity;
  final double indicativeRate; // Local cached estimate

  const CartLineItem({
    required this.templateCode,
    required this.itemName,
    required this.colour,
    required this.size,
    required this.itemCode,
    required this.quantity,
    required this.indicativeRate,
  });

  double get lineTotal => quantity * indicativeRate;

  CartLineItem copyWith({int? quantity}) => CartLineItem(
    templateCode: templateCode,
    itemName: itemName,
    colour: colour,
    size: size,
    itemCode: itemCode,
    quantity: quantity ?? this.quantity,
    indicativeRate: indicativeRate,
  );

  Map<String, dynamic> toJson() => {
    'item_code': itemCode,
    'template_code': templateCode,
    'item_name': itemName,
    'colour': colour,
    'size': size,
    'qty': quantity,
    'rate': indicativeRate,
  };

  factory CartLineItem.fromJson(Map<String, dynamic> json) => CartLineItem(
    templateCode: json['template_code'] as String? ?? '',
    itemName: json['item_name'] as String? ?? '',
    colour: json['colour'] as String? ?? '',
    size: json['size'] as String? ?? '',
    itemCode: json['item_code'] as String? ?? '',
    quantity: json['qty'] as int? ?? (json['quantity'] as num?)?.toInt() ?? 1,
    indicativeRate: (json['rate'] as num?)?.toDouble() ?? 0.0,
  );
}

/// Active mobile shopping cart prior to draft order placement.
@immutable
class CartModel {
  final String customer;
  final String customerName;
  final String territory;
  final DateTime deliveryDate;
  final List<CartLineItem> items;
  final String clientRequestId; // UUID v4 idempotency key

  // Server repricing & exposure preflight values
  final double? serverSubtotal;
  final double? serverTaxes;
  final double? serverGrandTotal;
  final double? serverApprovedLimit;
  final double? serverNewTotalExposure;
  final bool? serverExceedsLimit;
  final bool isRepriced;

  const CartModel({
    required this.customer,
    required this.customerName,
    required this.territory,
    required this.deliveryDate,
    required this.items,
    required this.clientRequestId,
    this.serverSubtotal,
    this.serverTaxes,
    this.serverGrandTotal,
    this.serverApprovedLimit,
    this.serverNewTotalExposure,
    this.serverExceedsLimit,
    this.isRepriced = false,
  });

  int get totalPieces => items.fold(0, (sum, item) => sum + item.quantity);
  double get indicativeSubtotal => items.fold(0.0, (sum, item) => sum + item.lineTotal);

  CartModel copyWith({
    List<CartLineItem>? items,
    DateTime? deliveryDate,
    String? clientRequestId,
    double? serverSubtotal,
    double? serverTaxes,
    double? serverGrandTotal,
    double? serverApprovedLimit,
    double? serverNewTotalExposure,
    bool? serverExceedsLimit,
    bool? isRepriced,
  }) {
    return CartModel(
      customer: customer,
      customerName: customerName,
      territory: territory,
      deliveryDate: deliveryDate ?? this.deliveryDate,
      items: items ?? this.items,
      clientRequestId: clientRequestId ?? this.clientRequestId,
      serverSubtotal: serverSubtotal ?? this.serverSubtotal,
      serverTaxes: serverTaxes ?? this.serverTaxes,
      serverGrandTotal: serverGrandTotal ?? this.serverGrandTotal,
      serverApprovedLimit: serverApprovedLimit ?? this.serverApprovedLimit,
      serverNewTotalExposure: serverNewTotalExposure ?? this.serverNewTotalExposure,
      serverExceedsLimit: serverExceedsLimit ?? this.serverExceedsLimit,
      isRepriced: isRepriced ?? this.isRepriced,
    );
  }
}

/// Order record synchronized from native ERPNext Sales Order controller.
@immutable
class SalesOrderModel {
  final String id; // Sales Order name (e.g. SO-2026-0001)
  final String customer;
  final String customerName;
  final DateTime transactionDate;
  final DateTime deliveryDate;
  final int totalQty;
  final String currency;
  final double grandTotal;
  final int docstatus; // 0=Draft, 1=Submitted, 2=Cancelled
  final String status; // Draft | Pending Approval | To Deliver and Bill | Cancelled | Completed
  final String? rejectionReason;
  final String? amendedFrom;
  final String? requestId;

  const SalesOrderModel({
    required this.id,
    required this.customer,
    required this.customerName,
    required this.transactionDate,
    required this.deliveryDate,
    required this.totalQty,
    required this.currency,
    required this.grandTotal,
    required this.docstatus,
    required this.status,
    this.rejectionReason,
    this.amendedFrom,
    this.requestId,
  });

  bool get isDraft => docstatus == 0;
  bool get isSubmitted => docstatus == 1;
  bool get isCancelled => docstatus == 2;
  bool get isRejected => rejectionReason != null && rejectionReason!.isNotEmpty;

  factory SalesOrderModel.fromJson(Map<String, dynamic> json) => SalesOrderModel(
    id: json['name'] as String? ?? '',
    customer: json['customer'] as String? ?? '',
    customerName: json['customer_name'] as String? ?? '',
    transactionDate: DateTime.tryParse(json['transaction_date'] as String? ?? '') ?? DateTime.now(),
    deliveryDate: DateTime.tryParse(json['delivery_date'] as String? ?? '') ?? DateTime.now(),
    totalQty: (json['total_qty'] as num?)?.toInt() ?? 0,
    currency: json['currency'] as String? ?? 'INR',
    grandTotal: (json['grand_total'] as num?)?.toDouble() ?? 0.0,
    docstatus: json['docstatus'] as int? ?? 0,
    status: json['status'] as String? ?? 'Draft',
    rejectionReason: json['custom_clothing_rejection_reason'] as String? ?? json['rejection_reason'] as String?,
    amendedFrom: json['amended_from'] as String?,
    requestId: json['custom_clothing_request_id'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'name': id,
    'customer': customer,
    'customer_name': customerName,
    'transaction_date': transactionDate.toIso8601String().substring(0, 10),
    'delivery_date': deliveryDate.toIso8601String().substring(0, 10),
    'total_qty': totalQty,
    'currency': currency,
    'grand_total': grandTotal,
    'docstatus': docstatus,
    'status': status,
    'custom_clothing_rejection_reason': rejectionReason,
    'amended_from': amendedFrom,
    'custom_clothing_request_id': requestId,
  };
}
