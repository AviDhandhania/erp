// Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
// Use of this source code is governed by a MIT-style license.

import 'dart:io';
import '../models/stage_inspection_model.dart';
import '../models/checklist_template_model.dart';
import '../models/inspection_reading_model.dart';
import '../models/inspection_defect_model.dart';
import '../models/inspection_evidence_photo.dart';
import '../services/quality_inspection_manager.dart';

/// State controller for performing stage quality inspections.
class InspectionController {
  final QualityInspectionManager inspectionManager;

  StageInspectionModel? activeInspection;
  List<InspectionChecklistItem> checklistItems = [];
  List<InspectionReadingModel> readings = [];
  List<InspectionDefectModel> defects = [];
  List<InspectionEvidencePhoto> evidencePhotos = [];
  AqlSamplingPlanModel samplingPlan = const AqlSamplingPlanModel(lotSize: 0, sampleSize: 0);

  String recommendation = 'Accept Lot';
  String result = 'Pending Review';
  bool correctiveActionRequired = false;
  String? correctiveActionDescription;
  String? correctiveActionOwner;
  DateTime? correctiveActionDueDate;

  bool isLoading = false;
  String? errorMessage;
  String? statusMessage;

  InspectionController({required this.inspectionManager});

  /// Initializes inspection session for a cycle and stage.
  Future<void> initializeInspection({
    required String cycleKey,
    required int stage,
    required String stageName,
    required String supplier,
    required String itemCode,
    String? itemGroup,
    String? purchaseOrder,
    String? productionLot,
    int visitNumber = 1,
  }) async {
    isLoading = true;
    errorMessage = null;

    try {
      // 1. Try to restore saved draft from encrypted SQLCipher cache
      final draft = await inspectionManager.getDraft(cycleKey, stage);
      if (draft != null) {
        activeInspection = draft;
        checklistItems = List.from(draft.checklistItems);
        readings = List.from(draft.readings);
        defects = List.from(draft.defects);
        evidencePhotos = List.from(draft.evidencePhotos);
        samplingPlan = draft.samplingPlan;
        recommendation = draft.recommendation;
        result = draft.result;
        correctiveActionRequired = draft.correctiveActionRequired;
        correctiveActionDescription = draft.correctiveActionDescription;
        correctiveActionOwner = draft.correctiveActionOwner;
        correctiveActionDueDate = draft.correctiveActionDueDate;
        statusMessage = 'Restored saved draft from local encrypted cache.';
      } else {
        // 2. Load fresh template if itemGroup provided
        if (itemGroup != null) {
          final template = await inspectionManager.loadChecklistTemplate(itemGroup);
          checklistItems = template.items
              .map((i) => InspectionChecklistItem(
                    checkpoint: i.checkpoint,
                    category: i.category,
                    isMandatory: i.isMandatory,
                  ))
              .toList();
        }

        activeInspection = StageInspectionModel(
          name: 'NEW-${DateTime.now().microsecondsSinceEpoch}',
          cycleKey: cycleKey,
          stage: stage,
          stageName: stageName,
          visitNumber: visitNumber,
          supplier: supplier,
          itemCode: itemCode,
          purchaseOrder: purchaseOrder,
          productionLot: productionLot,
        );
      }
    } catch (e) {
      errorMessage = 'Failed to initialize inspection: $e';
    } finally {
      isLoading = false;
    }
  }

  /// Updates status of a checkpoint row.
  void updateChecklistStatus(int index, String status, {String? notes}) {
    if (index >= 0 && index < checklistItems.length) {
      checklistItems[index] = checklistItems[index].copyWith(
        status: status,
        notes: notes,
      );
      _recalculateResult();
    }
  }

  /// Adds a measurement reading row.
  void addReading(InspectionReadingModel reading) {
    readings.add(reading);
    _recalculateResult();
  }

  /// Adds a defect observation row.
  void addDefect(InspectionDefectModel defect) {
    defects.add(defect);
    _recalculateResult();
  }

  /// Captures a private evidence photo via SafePhotoManager.
  Future<void> capturePhoto(File photoFile, String caption) async {
    try {
      final photo = await inspectionManager.captureEvidencePhoto(
        rawPhotoFile: photoFile,
        caption: caption,
        displayOrder: evidencePhotos.length + 1,
      );
      evidencePhotos.add(photo);
      statusMessage = 'Evidence photo captured and sanitized.';
    } catch (e) {
      errorMessage = 'Photo capture failed: $e';
    }
  }

  /// Saves in-progress draft to encrypted cache.
  Future<void> saveDraft() async {
    if (activeInspection == null) return;

    final draft = StageInspectionModel(
      name: activeInspection!.name,
      cycleKey: activeInspection!.cycleKey,
      stage: activeInspection!.stage,
      stageName: activeInspection!.stageName,
      visitNumber: activeInspection!.visitNumber,
      supplier: activeInspection!.supplier,
      itemCode: activeInspection!.itemCode,
      purchaseOrder: activeInspection!.purchaseOrder,
      productionLot: activeInspection!.productionLot,
      checklistItems: checklistItems,
      readings: readings,
      defects: defects,
      samplingPlan: samplingPlan,
      evidencePhotos: evidencePhotos,
      recommendation: recommendation,
      result: result,
      correctiveActionRequired: correctiveActionRequired,
      correctiveActionDescription: correctiveActionDescription,
      correctiveActionOwner: correctiveActionOwner,
      correctiveActionDueDate: correctiveActionDueDate,
    );

    await inspectionManager.saveDraft(draft);
    statusMessage = 'Draft saved to local encrypted cache.';
  }

  /// Submits completed inspection report to server.
  Future<bool> submitInspection({bool isOnline = true}) async {
    if (activeInspection == null) return false;

    isLoading = true;
    errorMessage = null;

    try {
      final model = StageInspectionModel(
        name: activeInspection!.name,
        cycleKey: activeInspection!.cycleKey,
        stage: activeInspection!.stage,
        stageName: activeInspection!.stageName,
        visitNumber: activeInspection!.visitNumber,
        supplier: activeInspection!.supplier,
        itemCode: activeInspection!.itemCode,
        purchaseOrder: activeInspection!.purchaseOrder,
        productionLot: activeInspection!.productionLot,
        checklistItems: checklistItems,
        readings: readings,
        defects: defects,
        samplingPlan: samplingPlan,
        evidencePhotos: evidencePhotos,
        recommendation: recommendation,
        result: result,
        correctiveActionRequired: correctiveActionRequired,
        correctiveActionDescription: correctiveActionDescription,
        correctiveActionOwner: correctiveActionOwner,
        correctiveActionDueDate: correctiveActionDueDate,
      );

      await inspectionManager.submitInspection(model, isOnline: isOnline);
      statusMessage = 'Quality inspection report submitted successfully.';
      return true;
    } catch (e) {
      errorMessage = 'Submission failed: $e';
      return false;
    } finally {
      isLoading = false;
    }
  }

  void _recalculateResult() {
    final hasFailedChecklist = checklistItems.any((c) => c.isFailed && c.isMandatory);
    final hasOutOfSpecReading = readings.any((r) => !r.isInSpec);
    final hasCriticalDefect = defects.any((d) => d.isCritical);

    if (hasCriticalDefect || hasFailedChecklist) {
      result = 'Failed';
      recommendation = 'Reject Lot';
    } else if (hasOutOfSpecReading) {
      result = 'Conditionally Passed';
      recommendation = 'Correction & Resubmission Required';
    } else {
      result = 'Passed';
      recommendation = 'Accept Lot';
    }
  }
}
