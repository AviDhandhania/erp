// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

library quality_app;

// Models
export 'src/models/quality_boot_model.dart';
export 'src/models/production_cycle_model.dart';
export 'src/models/checklist_template_model.dart';
export 'src/models/inspection_reading_model.dart';
export 'src/models/inspection_defect_model.dart';
export 'src/models/inspection_evidence_photo.dart';
export 'src/models/stage_inspection_model.dart';
export 'src/models/revision_comparison_model.dart';
export 'src/models/return_quarantine_model.dart';
export 'src/models/gate_review_bundle_model.dart';
export 'src/models/controlled_report_model.dart';

// Services
export 'src/services/quality_api_service.dart';
export 'src/services/quality_local_cache.dart';
export 'src/services/quality_cycle_manager.dart';
export 'src/services/quality_inspection_manager.dart';
export 'src/services/quarantine_disposition_manager.dart';
export 'src/services/gate_review_manager.dart';
export 'src/services/controlled_report_manager.dart';

// Controllers
export 'src/controllers/quality_home_controller.dart';
export 'src/controllers/cycles_controller.dart';
export 'src/controllers/inspection_controller.dart';
export 'src/controllers/revision_controller.dart';
export 'src/controllers/return_quarantine_controller.dart';
export 'src/controllers/gate_review_controller.dart';
export 'src/controllers/controlled_report_controller.dart';

// Screens
export 'src/screens/quality_home_screen.dart';
export 'src/screens/cycles/production_cycle_list_screen.dart';
export 'src/screens/cycles/cycle_detail_screen.dart';
export 'src/screens/inspection/inspection_form_screen.dart';
export 'src/screens/inspection/revision_compare_screen.dart';
export 'src/screens/returns/return_quarantine_list_screen.dart';
export 'src/screens/returns/return_quarantine_detail_screen.dart';
export 'src/screens/gate_review/gate_review_screen.dart';
export 'src/screens/reports/controlled_report_screen.dart';
