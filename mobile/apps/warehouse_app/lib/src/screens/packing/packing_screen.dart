// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import '../../controllers/packing_controller.dart';
import '../../models/packing_model.dart';

/// Screen for carton packing, package measurement capture, and packing slip generation.
///
/// Features:
/// - Active carton item allocation.
/// - Dimension capture (L / W / H / dimension UOM).
/// - Weight capture (Gross / Net weight / weight UOM).
/// - Carton barcode generation and label printing.
/// - Packing Slip generation with native ERPNext controllers.
class PackingScreen {
  final PackingController controller;

  const PackingScreen({required this.controller});

  Map<String, dynamic> buildViewData() {
    return {
      'state': controller.isLoading ? 'loading' : 'ready',
      'active_pick_list': controller.activePickList,
      'cartons_count': controller.packages.length,
      'is_online': controller.isOnline,
      'error_message': controller.errorMessage,
      'packages': controller.packages.map((pkg) => {
        'package_id': pkg.packageId,
        'carton_barcode': pkg.cartonBarcode,
        'package_type': pkg.packageType,
        'items_count': pkg.items.length,
        'dimensions': {
          'length': pkg.length,
          'width': pkg.width,
          'height': pkg.height,
          'uom': pkg.dimensionUom,
          'is_valid': pkg.hasValidDimensions,
        },
        'weights': {
          'gross_weight': pkg.grossWeight,
          'net_weight': pkg.netWeight,
          'uom': pkg.weightUom,
          'is_valid': pkg.hasValidWeights,
        },
        'packing_slip_id': pkg.packingSlipId,
        'is_complete': pkg.isComplete,
      }).toList(),
      'can_generate_packing_slip': controller.isOnline &&
          controller.packages.isNotEmpty &&
          controller.packages.every((p) => p.isComplete),
      'actions': [
        'add_carton',
        'record_measurements',
        'print_carton_label',
        'generate_packing_slip',
      ],
    };
  }
}
