// Copyright (c) 2026, Clothing ERP Contributors
// For license information, please see license.txt

/**
 * Reusable Web & Mobile Scanner Controller for Clothing ERP.
 * 
 * Supports:
 * - Hardware keyboard-wedge scanners (timing-based detection, < 50ms latency).
 * - Mobile camera scanning (BarcodeDetector API & MediaDevices stream).
 * - Torch / flashlight toggle.
 * - Debounce and duplicate suppression (1500ms cooldown for identical barcode).
 * - Continuous scanning mode.
 * - Web Audio API synthesized audio tones (880Hz success, 220Hz failure).
 * - Haptic feedback (navigator.vibrate).
 * - Visual feedback (flash borders/banners).
 * - Accessible manual keyboard entry with ARIA live region announcements.
 */

class ClothingScanner {
    constructor(options = {}) {
        this.options = Object.assign({
            debounceMs: 1500,
            continuousMode: false,
            soundEnabled: true,
            hapticEnabled: true,
            operationContext: "lookup",
            warehouse: null,
            documentType: null,
            documentName: null,
            expectedItem: null,
            expectedBatch: null,
            expectedSerial: null,
            targetContainer: null,
            onScan: null,
        }, options);

        this.lastScanText = null;
        this.lastScanTime = 0;
        this.wedgeBuffer = "";
        this.wedgeLastKeyTime = 0;
        this.audioCtx = null;
        this.videoStream = null;
        this.isScanningActive = false;

        this._initAudio();
        this._initKeyboardWedgeListener();
    }

    // -----------------------------------------------------------------------
    // Audio Synthesis (Web Audio API)
    // -----------------------------------------------------------------------
    _initAudio() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.audioCtx = new AudioContext();
            }
        } catch (e) {
            console.warn("Web Audio API not supported", e);
        }
    }

    _resumeAudio() {
        if (this.audioCtx && this.audioCtx.state === "suspended") {
            this.audioCtx.resume();
        }
    }

    playSuccessTone() {
        if (!this.options.soundEnabled || !this.audioCtx) return;
        this._resumeAudio();
        try {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, this.audioCtx.currentTime); // High clean chime
            gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.12);
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.start();
            osc.stop(this.audioCtx.currentTime + 0.12);
        } catch (e) {
            // Audio error safe handling
        }
    }

    playErrorTone() {
        if (!this.options.soundEnabled || !this.audioCtx) return;
        this._resumeAudio();
        try {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(220, this.audioCtx.currentTime); // Low double buzz
            gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.25);
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.start();
            osc.stop(this.audioCtx.currentTime + 0.25);
        } catch (e) {
            // Audio error safe handling
        }
    }

    playWarningTone() {
        if (!this.options.soundEnabled || !this.audioCtx) return;
        this._resumeAudio();
        try {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.type = "triangle";
            osc.frequency.setValueAtTime(440, this.audioCtx.currentTime);
            gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.18);
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.start();
            osc.stop(this.audioCtx.currentTime + 0.18);
        } catch (e) {
            // Audio error safe handling
        }
    }

    // -----------------------------------------------------------------------
    // Haptic & Visual Feedback
    // -----------------------------------------------------------------------
    triggerHaptic(type = "success") {
        if (!this.options.hapticEnabled || !navigator.vibrate) return;
        try {
            if (type === "success") {
                navigator.vibrate([100]);
            } else if (type === "warning") {
                navigator.vibrate([80, 40, 80]);
            } else {
                navigator.vibrate([120, 60, 120]);
            }
        } catch (e) {
            // Safe vibration fallback
        }
    }

    flashVisual(color = "green") {
        const container = this.options.targetContainer || document.body;
        const className = color === "green" ? "scanner-flash-green" : (color === "amber" ? "scanner-flash-amber" : "scanner-flash-red");
        container.classList.add(className);
        setTimeout(() => {
            container.classList.remove(className);
        }, 350);
    }

    // -----------------------------------------------------------------------
    // Hardware Keyboard-Wedge Scanner Listener
    // -----------------------------------------------------------------------
    _initKeyboardWedgeListener() {
        this._wedgeHandler = (e) => {
            const now = Date.now();
            const diff = now - this.wedgeLastKeyTime;
            this.wedgeLastKeyTime = now;

            // If user is actively typing in a standard textarea, don't hijack unless rapid
            const activeTag = document.activeElement ? document.activeElement.tagName : "";
            const isTyping = (activeTag === "TEXTAREA" || (activeTag === "INPUT" && !document.activeElement.classList.contains("barcode-scanner-input")));

            if (e.key === "Enter") {
                if (this.wedgeBuffer.length >= 3 && (diff < 80 || !isTyping)) {
                    e.preventDefault();
                    e.stopPropagation();
                    const scanned = this.wedgeBuffer.trim();
                    this.wedgeBuffer = "";
                    this.processScan(scanned, "hardware_wedge");
                } else {
                    this.wedgeBuffer = "";
                }
                return;
            }

            if (e.key.length === 1) {
                // If interval between keystrokes is very fast (< 50ms), it is a hardware wedge scanner
                if (diff > 120 && this.wedgeBuffer.length > 0 && isTyping) {
                    this.wedgeBuffer = ""; // Reset buffer if normal slow manual typing
                }
                this.wedgeBuffer += e.key;
            }
        };

        window.addEventListener("keydown", this._wedgeHandler, true);
    }

    destroy() {
        if (this._wedgeHandler) {
            window.removeEventListener("keydown", this._wedgeHandler, true);
        }
        this.stopCamera();
    }

    // -----------------------------------------------------------------------
    // Debounce, Duplicate Suppression & Scan Processing
    // -----------------------------------------------------------------------
    processScan(rawText, source = "manual") {
        const text = String(rawText || "").trim();
        if (!text) return;

        const now = Date.now();
        const isSameBarcode = (this.lastScanText === text);
        const elapsed = now - this.lastScanTime;

        // Duplicate suppression: ignore identical scan within debounce window
        if (isSameBarcode && elapsed < this.options.debounceMs) {
            this.announceAccessibility(`Duplicate scan ignored: ${text}`);
            return;
        }

        // Update debounce state
        this.lastScanText = text;
        this.lastScanTime = now;

        this.announceAccessibility(`Processing scan: ${text}`);

        // Server-Side Resolver Invocation
        frappe.call({
            method: "warehouse_erp.barcodes.resolve_scan",
            args: {
                scan_text: text,
                operation_context: this.options.operationContext,
                warehouse: this.options.warehouse,
                document_type: this.options.documentType,
                document_name: this.options.documentName,
                expected_item: this.options.expectedItem,
                expected_batch: this.options.expectedBatch,
                expected_serial: this.options.expectedSerial,
            },
            callback: (r) => {
                const res = r.message || {};
                this.handleScanResult(res, text, source);
            },
            error: (err) => {
                this.playErrorTone();
                this.triggerHaptic("error");
                this.flashVisual("red");
                this.announceAccessibility(`Scan failed: server communication error`);
                if (this.options.onScan) {
                    this.options.onScan({
                        success: false,
                        scan_text: text,
                        error_code: "NETWORK_ERROR",
                        message: __("Server error resolving scan."),
                    });
                }
            },
        });
    }

    handleScanResult(res, rawText, source) {
        const feedback = res.feedback || {};
        const status = feedback.status || (res.success ? "valid" : "error");

        if (status === "valid" || res.success) {
            this.playSuccessTone();
            this.triggerHaptic("success");
            this.flashVisual("green");
            this.announceAccessibility(feedback.message || `Valid scan: ${rawText}`);
        } else if (status === "warning") {
            this.playWarningTone();
            this.triggerHaptic("warning");
            this.flashVisual("amber");
            this.announceAccessibility(feedback.message || `Warning: ${res.message}`);
        } else {
            this.playErrorTone();
            this.triggerHaptic("error");
            this.flashVisual("red");
            this.announceAccessibility(feedback.message || `Error: ${res.message}`);
        }

        if (this.options.onScan) {
            this.options.onScan(res);
        }

        // If continuous mode is enabled, keep ready for the next scan immediately
        if (this.options.continuousMode) {
            // Ready for next scan
        }
    }

    // -----------------------------------------------------------------------
    // Camera Scanning & Torch Control
    // -----------------------------------------------------------------------
    async startCamera(videoElement) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Camera streaming not supported on this browser.");
        }

        try {
            this.videoStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "environment",
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            });
            videoElement.srcObject = this.videoStream;
            videoElement.setAttribute("playsinline", true);
            await videoElement.play();
            this.isScanningActive = true;

            // Use Native BarcodeDetector if available
            if ("BarcodeDetector" in window) {
                const detector = new window.BarcodeDetector({
                    formats: ["code_128", "ean_13", "ean_8", "upc_a", "qr_code"],
                });

                const scanFrame = async () => {
                    if (!this.isScanningActive) return;
                    try {
                        const barcodes = await detector.detect(videoElement);
                        if (barcodes.length > 0) {
                            const raw = barcodes[0].rawValue;
                            this.processScan(raw, "camera");
                        }
                    } catch (e) {
                        // ignore frame detection error
                    }
                    if (this.isScanningActive) {
                        requestAnimationFrame(scanFrame);
                    }
                };
                requestAnimationFrame(scanFrame);
            }
        } catch (err) {
            this.isScanningActive = false;
            throw err;
        }
    }

    stopCamera() {
        this.isScanningActive = false;
        if (this.videoStream) {
            this.videoStream.getTracks().forEach((track) => track.stop());
            this.videoStream = null;
        }
    }

    async toggleTorch(enable) {
        if (!this.videoStream) return false;
        const track = this.videoStream.getVideoTracks()[0];
        if (!track) return false;

        const capabilities = track.getCapabilities ? track.getCapabilities() : {};
        if (!capabilities.torch) return false;

        try {
            await track.applyConstraints({
                advanced: [{ torch: !!enable }],
            });
            return true;
        } catch (e) {
            return false;
        }
    }

    // -----------------------------------------------------------------------
    // Accessible Announcements (ARIA Live Region)
    // -----------------------------------------------------------------------
    announceAccessibility(message) {
        let liveRegion = document.getElementById("clothing-scanner-live-region");
        if (!liveRegion) {
            liveRegion = document.createElement("div");
            liveRegion.id = "clothing-scanner-live-region";
            liveRegion.setAttribute("aria-live", "polite");
            liveRegion.setAttribute("aria-atomic", "true");
            liveRegion.style.position = "absolute";
            liveRegion.style.left = "-9999px";
            liveRegion.style.width = "1px";
            liveRegion.style.height = "1px";
            liveRegion.style.overflow = "hidden";
            document.body.appendChild(liveRegion);
        }
        liveRegion.textContent = message;
    }
}

// Global exposure for Frappe desk & apps
window.ClothingScanner = ClothingScanner;
