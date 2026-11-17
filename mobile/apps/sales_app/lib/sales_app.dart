// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

library sales_app;

// Models
export 'src/models/sales_dashboard_model.dart';
export 'src/models/retailer_model.dart';
export 'src/models/retailer_application_model.dart';
export 'src/models/retailer_visit_model.dart';
export 'src/models/catalogue_model.dart';
export 'src/models/cart_order_model.dart';
export 'src/models/collection_model.dart';
export 'src/models/delivery_follow_up_model.dart';
export 'src/models/supervision_model.dart';
export 'src/models/conflict_model.dart';

// Services
export 'src/services/sales_api_service.dart';
export 'src/services/sales_local_cache.dart';
export 'src/services/sales_order_manager.dart';
export 'src/services/sales_visit_manager.dart';
export 'src/services/sales_application_manager.dart';

// Controllers
export 'src/controllers/sales_home_controller.dart';
export 'src/controllers/retailer_directory_controller.dart';
export 'src/controllers/catalogue_controller.dart';
export 'src/controllers/cart_controller.dart';
export 'src/controllers/orders_controller.dart';
export 'src/controllers/visits_controller.dart';
export 'src/controllers/collections_controller.dart';
export 'src/controllers/delivery_follow_up_controller.dart';
export 'src/controllers/rsm_supervision_controller.dart';
export 'src/controllers/conflicts_controller.dart';

// Screens
export 'src/screens/sales_home_screen.dart';
export 'src/screens/retailers/retailer_list_screen.dart';
export 'src/screens/retailers/retailer_detail_screen.dart';
export 'src/screens/applications/retailer_application_form_screen.dart';
export 'src/screens/applications/rsm_application_review_screen.dart';
export 'src/screens/visits/visit_queue_screen.dart';
export 'src/screens/visits/visit_checkin_screen.dart';
export 'src/screens/catalogue/catalogue_screen.dart';
export 'src/screens/catalogue/product_detail_screen.dart';
export 'src/screens/cart/cart_screen.dart';
export 'src/screens/cart/order_detail_screen.dart';
export 'src/screens/collections/collection_worklist_screen.dart';
export 'src/screens/delivery/delivery_follow_up_screen.dart';
export 'src/screens/supervision/rsm_supervision_screen.dart';
export 'src/screens/conflicts/conflicts_screen.dart';
