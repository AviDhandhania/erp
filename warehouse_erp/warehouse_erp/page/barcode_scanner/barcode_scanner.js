// Copyright (c) 2026, Clothing ERP Contributors
// For license information, please see license.txt

frappe.pages["barcode_scanner"].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Barcode Scanner"),
        single_column: true,
    });

    // Load ClothingScanner controller script if not already loaded
    frappe.require("/assets/warehouse_erp/js/clothing_scanner.js", function() {
        new BarcodeScannerPage(page);
    });
};

class BarcodeScannerPage {
    constructor(page) {
        this.page = page;
        this.scanner = null;
        this.history = [];
        this.isCameraActive = false;
        this.isTorchActive = false;

        this.render();
        this.initScanner();
    }

    render() {
        const html = `
        <div class="barcode-scanner-container" id="scanner-view-container">
            <div class="scanner-card">
                <div class="scanner-controls">
                    <div style="flex: 1; min-width: 220px;">
                        <label style="font-size: 12px; font-weight: 600; margin-bottom: 4px; display: block;">${__("Operation Context")}</label>
                        <select class="form-control" id="scanner-context-select">
                            <option value="lookup" selected>${__("Item Lookup / Catalog Verification")}</option>
                            <option value="picking">${__("Picking Verification")}</option>
                            <option value="returns">${__("Customer Returns Intake")}</option>
                            <option value="quality">${__("Quality Cycle / Inspection")}</option>
                            <option value="location">${__("Warehouse Location Bin")}</option>
                        </select>
                    </div>

                    <div style="display: flex; gap: 15px; align-items: center; margin-top: 15px;">
                        <label style="font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px;">
                            <input type="checkbox" id="scanner-continuous-toggle">
                            <span>${__("Continuous Scan Mode")}</span>
                        </label>
                        <label style="font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px;">
                            <input type="checkbox" id="scanner-sound-toggle" checked>
                            <span>${__("Sound Feedback")}</span>
                        </label>
                    </div>
                </div>

                <!-- Camera Viewport (Optional) -->
                <div id="camera-viewport-wrapper" style="display: none;">
                    <div class="scanner-viewport-box">
                        <video class="scanner-video" id="scanner-video-el"></video>
                        <div class="scanner-viewfinder-overlay">
                            <div class="scanner-laser-line"></div>
                        </div>
                    </div>
                    <div style="text-align: center; margin-bottom: 15px;">
                        <button class="btn btn-sm btn-default" id="toggle-torch-btn" style="margin-right: 8px;">
                            <i class="fa fa-lightbulb-o"></i> ${__("Toggle Torch")}
                        </button>
                        <button class="btn btn-sm btn-danger" id="stop-camera-btn">
                            <i class="fa fa-stop"></i> ${__("Stop Camera")}
                        </button>
                    </div>
                </div>

                <!-- Input & Action Bar -->
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="flex: 1; position: relative;">
                        <input type="text"
                               class="form-control barcode-scanner-input"
                               id="manual-barcode-input"
                               placeholder="${__("Scan with hardware gun or type barcode / SKU / serial...")}"
                               autocomplete="off"
                               aria-label="${__("Barcode Scan Input")}">
                    </div>
                    <button class="btn btn-primary" id="manual-scan-submit-btn">
                        <i class="fa fa-barcode"></i> ${__("Submit Scan")}
                    </button>
                    <button class="btn btn-default" id="start-camera-btn">
                        <i class="fa fa-camera"></i> ${__("Use Camera")}
                    </button>
                </div>

                <div id="scanner-active-result" style="display: none;"></div>
            </div>

            <!-- Scan History Timeline -->
            <div class="scanner-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h5 style="margin: 0; font-weight: 600;">${__("Recent Scans")}</h5>
                    <button class="btn btn-xs btn-default" id="clear-history-btn">${__("Clear History")}</button>
                </div>
                <div style="overflow-x: auto;">
                    <table class="scan-history-table">
                        <thead>
                            <tr>
                                <th>${__("Time")}</th>
                                <th>${__("Barcode Text")}</th>
                                <th>${__("Namespace")}</th>
                                <th>${__("Status")}</th>
                                <th>${__("Result / Description")}</th>
                            </tr>
                        </thead>
                        <tbody id="scan-history-tbody">
                            <tr><td colspan="5" class="text-muted text-center" style="padding: 15px;">${__("No barcodes scanned yet.")}</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        `;

        this.page.main.html(html);
        this.bindEvents();
    }

    initScanner() {
        const container = document.getElementById("scanner-view-container");
        this.scanner = new ClothingScanner({
            targetContainer: container,
            soundEnabled: true,
            continuousMode: false,
            operationContext: "lookup",
            onScan: (res) => this.onScanCompleted(res),
        });

        // Set focus to the barcode input field
        setTimeout(() => {
            const input = document.getElementById("manual-barcode-input");
            if (input) input.focus();
        }, 200);
    }

    bindEvents() {
        const contextSelect = document.getElementById("scanner-context-select");
        if (contextSelect) {
            contextSelect.addEventListener("change", (e) => {
                if (this.scanner) {
                    this.scanner.options.operationContext = e.target.value;
                }
            });
        }

        const continuousToggle = document.getElementById("scanner-continuous-toggle");
        if (continuousToggle) {
            continuousToggle.addEventListener("change", (e) => {
                if (this.scanner) {
                    this.scanner.options.continuousMode = e.target.checked;
                }
            });
        }

        const soundToggle = document.getElementById("scanner-sound-toggle");
        if (soundToggle) {
            soundToggle.addEventListener("change", (e) => {
                if (this.scanner) {
                    this.scanner.options.soundEnabled = e.target.checked;
                }
            });
        }

        const manualInput = document.getElementById("manual-barcode-input");
        const submitBtn = document.getElementById("manual-scan-submit-btn");

        const submitManual = () => {
            const val = manualInput.value.trim();
            if (val && this.scanner) {
                this.scanner.processScan(val, "manual");
                manualInput.value = "";
                manualInput.focus();
            }
        };

        if (submitBtn) {
            submitBtn.addEventListener("click", submitManual);
        }
        if (manualInput) {
            manualInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    submitManual();
                }
            });
        }

        // Camera handlers
        const startCameraBtn = document.getElementById("start-camera-btn");
        const stopCameraBtn = document.getElementById("stop-camera-btn");
        const toggleTorchBtn = document.getElementById("toggle-torch-btn");
        const cameraWrapper = document.getElementById("camera-viewport-wrapper");
        const videoEl = document.getElementById("scanner-video-el");

        if (startCameraBtn) {
            startCameraBtn.addEventListener("click", async () => {
                try {
                    cameraWrapper.style.display = "block";
                    await this.scanner.startCamera(videoEl);
                    this.isCameraActive = true;
                    startCameraBtn.style.display = "none";
                } catch (err) {
                    frappe.msgprint({
                        title: __("Camera Error"),
                        message: __(err.message || "Could not access camera."),
                        indicator: "red",
                    });
                    cameraWrapper.style.display = "none";
                }
            });
        }

        if (stopCameraBtn) {
            stopCameraBtn.addEventListener("click", () => {
                if (this.scanner) this.scanner.stopCamera();
                cameraWrapper.style.display = "none";
                if (startCameraBtn) startCameraBtn.style.display = "inline-block";
                this.isCameraActive = false;
            });
        }

        if (toggleTorchBtn) {
            toggleTorchBtn.addEventListener("click", async () => {
                this.isTorchActive = !this.isTorchActive;
                await this.scanner.toggleTorch(this.isTorchActive);
            });
        }

        const clearBtn = document.getElementById("clear-history-btn");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                this.history = [];
                this.renderHistory();
            });
        }
    }

    onScanCompleted(res) {
        const resultBox = document.getElementById("scanner-active-result");
        if (!resultBox) return;

        resultBox.style.display = "block";
        const feedback = res.feedback || {};
        const isSuccess = res.success;
        const statusClass = isSuccess ? "" : (feedback.status === "warning" ? "warning" : "error");

        resultBox.className = `scanner-result-box ${statusClass}`;

        let detailsHtml = "";
        if (isSuccess && res.details) {
            detailsHtml = `<div style="font-size: 12px; margin-top: 6px; color: #444;">`;
            for (let [k, v] of Object.entries(res.details)) {
                if (v !== null && v !== undefined && k !== "barcode") {
                    const cleanK = frappe.model.unscrub(k);
                    detailsHtml += `<span style="margin-right: 15px;"><strong>${cleanK}:</strong> ${frappe.utils.escape_html(String(v))}</span>`;
                }
            }
            detailsHtml += `</div>`;
        }

        resultBox.html(`
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>${frappe.utils.escape_html(feedback.message || res.message || "Scan processed")}</strong>
                <span class="scan-badge ${feedback.color || (isSuccess ? "green" : "red")}">${frappe.utils.escape_html(res.namespace || "unknown")}</span>
            </div>
            ${detailsHtml}
        `);

        // Add to history
        this.history.unshift({
            time: frappe.datetime.now_time(),
            text: res.scan_text,
            namespace: res.namespace || "unknown",
            success: isSuccess,
            message: feedback.message || res.message || "",
            color: feedback.color || (isSuccess ? "green" : "red"),
        });

        if (this.history.length > 50) {
            this.history.pop();
        }

        this.renderHistory();
    }

    renderHistory() {
        const tbody = document.getElementById("scan-history-tbody");
        if (!tbody) return;

        if (this.history.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-muted text-center" style="padding: 15px;">${__("No barcodes scanned yet.")}</td></tr>`;
            return;
        }

        let html = "";
        for (let row of this.history) {
            const badgeClass = row.color === "green" ? "green" : (row.color === "amber" ? "amber" : "red");
            html += `
            <tr>
                <td style="color: #666;">${frappe.utils.escape_html(row.time)}</td>
                <td><strong>${frappe.utils.escape_html(row.text)}</strong></td>
                <td><code>${frappe.utils.escape_html(row.namespace)}</code></td>
                <td><span class="scan-badge ${badgeClass}">${row.success ? __("Success") : __("Failed")}</span></td>
                <td>${frappe.utils.escape_html(row.message)}</td>
            </tr>
            `;
        }
        tbody.innerHTML = html;
    }
}
