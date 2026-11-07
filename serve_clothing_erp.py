#!/usr/bin/env python3
"""Clothing ERP & ERPNext Bundled Server Gateway.

Bundles and auto-starts the independent ERPNext server (port 8001) alongside
the Clothing ERP operational portal (port 8000).
- Auto-starts the independent ERPNext backend server if not already running.
- Serves the unified Frappe/ERPNext Desk on http://127.0.0.1:8000.
- App switcher allows switching between ERPNext (Selling, Stock, Buying, Accounting)
  and Clothing ERP (Salesperson Portal, Warehouse Operations).
- Clothing ERP operational interfaces dynamically consume data from ERPNext.
"""

import atexit
import http.server
import json
import os
import signal
import socketserver
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse, parse_qs

# Set up paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from clothing_erp.roles import (
    ROLE_SALESPERSON,
    ROLE_WAREHOUSE_OPERATOR,
    ROLE_SALES_MANAGER,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_BUSINESS_ADMIN,
)
from clothing_erp.security import (
    get_current_user,
    get_user_roles,
    get_active_operational_role,
    is_salesperson,
    is_warehouse_operator,
    is_clothing_admin,
    require_role,
)
from clothing_erp.api import (
    get_user_context,
    switch_preview_role,
    get_salesperson_dashboard,
    get_warehouse_dashboard,
)
from clothing_erp.erpnext_client import (
    check_erpnext_server,
    get_items,
    get_customers,
    get_sales_orders,
    get_pick_lists,
    get_delivery_notes,
    get_erpnext_catalog,
)

PORT = 8000
ERPNEXT_PORT = 8001
_erpnext_process = None


def ensure_erpnext_running():
    """Auto-start the independent ERPNext server process if not already active."""
    global _erpnext_process
    if check_erpnext_server():
        print(f"[Gateway] ERPNext server is already running on port {ERPNEXT_PORT}.")
        return

    print(f"[Gateway] Auto-starting independent ERPNext server on port {ERPNEXT_PORT}...")
    server_script = os.path.join(WORKSPACE_DIR, "erpnext_service", "erpnext_server.py")
    if not os.path.exists(server_script):
        print(f"[Gateway ERROR] erpnext_server.py not found at {server_script}")
        return

    _erpnext_process = subprocess.Popen(
        [sys.executable, server_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )

    # Wait for ERPNext to be responsive
    for _ in range(15):
        time.sleep(0.3)
        if check_erpnext_server():
            print(f"[Gateway] Independent ERPNext server successfully started and healthy on port {ERPNEXT_PORT}.")
            return
    print(f"[Gateway WARNING] ERPNext server spawned, waiting for requests...")


def shutdown_erpnext():
    """Cleanly terminate the auto-started ERPNext server process upon gateway shutdown."""
    global _erpnext_process
    if _erpnext_process:
        print("[Gateway] Shutting down independent ERPNext server...")
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(_erpnext_process.pid), signal.SIGTERM)
            else:
                _erpnext_process.terminate()
            _erpnext_process.wait(timeout=3)
        except Exception:
            pass
        _erpnext_process = None


atexit.register(shutdown_erpnext)


def status_badge(status):
    """Render authentic Frappe status badge."""
    colors = {
        "Confirmed": "background: #e0f2fe; color: #0284c7;",
        "Picking": "background: #ffedd5; color: #c2410c;",
        "Awaiting Approval": "background: #fef9c3; color: #a16207;",
        "Dispatched": "background: #dcfce7; color: #15803d;",
        "In Progress": "background: #e0e7ff; color: #4338ca;",
        "Queued": "background: #f3f4f6; color: #4b5563;",
        "Ready for Dispatch": "background: #dcfce7; color: #15803d;",
    }
    style = colors.get(status, "background: #f3f4f6; color: #4b5563;")
    return f'<span class="badge" style="{style} font-weight: 500; font-size: 11px; padding: 4px 8px; border-radius: 4px;">{status}</span>'


def get_bundled_desk_html(view="overview", active_role=None, active_app="clothing_erp"):
    """Generate exact ERPNext Desk HTML bundling both ERPNext and Clothing ERP."""
    ctx = get_user_context()
    if not active_role:
        active_role = ctx["active_role"]

    sales_data = get_salesperson_dashboard()
    warehouse_data = get_warehouse_dashboard()
    erp_items = get_items()
    erp_customers = get_customers()

    show_sales = active_role in ["Salesperson", "Sales Manager", "Administrator"]
    show_warehouse = active_role in ["Warehouse Operator", "Warehouse Manager", "Administrator"]

    role_badges = {
        "Administrator": "background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe;",
        "Salesperson": "background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;",
        "Warehouse Operator": "background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0;",
    }
    role_badge_style = role_badges.get(active_role, "background: #f3f4f6; color: #374151;")

    # -------------------------------------------------------------
    # 1. ERPNext Standard Catalogue & Core Module Views
    # -------------------------------------------------------------
    if active_app == "erpnext" or view in ["selling", "stock", "buying", "accounting", "crm", "settings", "item", "customer"]:
        module_title = view.capitalize() if view not in ["overview", "app"] else "Selling"
        if view == "item":
            module_title = "Item (Garment Catalog)"
        elif view == "customer":
            module_title = "Customer (Retailers)"

        breadcrumbs = f"Home / ERPNext Core / {module_title}"
        action_buttons = f"""
            <a href="http://127.0.0.1:{ERPNEXT_PORT}/app" target="_blank" class="btn btn-default btn-sm me-2">Independent ERPNext UI (:8001)</a>
            <button class="btn btn-primary btn-sm" onclick="alert('Creating new {module_title} in ERPNext')">+ Add {module_title}</button>
        """

        # Table of items from ERPNext
        item_rows = ""
        for itm in erp_items:
            item_rows += f"""
            <tr class="align-middle">
                <td><span class="fw-bold">{itm.get('item_code')}</span></td>
                <td>{itm.get('item_name')}</td>
                <td><span class="badge bg-light text-dark border">{itm.get('item_group')}</span></td>
                <td><span class="badge bg-secondary-subtle text-secondary">{itm.get('size')} / {itm.get('color')}</span></td>
                <td class="fw-semibold">₹{itm.get('standard_rate', 0):,.2f}</td>
                <td class="text-success fw-bold">{itm.get('actual_qty', 0):.0f} {itm.get('stock_uom')}</td>
                <td class="text-secondary small">{itm.get('warehouse')}</td>
            </tr>
            """

        content_body = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TOTAL GARMENT STYLES</div>
                    <div class="frappe-card-number">{len(erp_items)}</div>
                    <div class="frappe-card-sub text-success">Live from ERPNext Item master</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">RETAILER ACCOUNTS</div>
                    <div class="frappe-card-number">{len(erp_customers)}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Customer doctype</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ACTIVE WAREHOUSES</div>
                    <div class="frappe-card-number">3</div>
                    <div class="frappe-card-sub text-secondary">Finished Goods, Stores, Dispatch</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ERPNEXT SERVER STATUS</div>
                    <div class="frappe-card-number text-success">Online</div>
                    <div class="frappe-card-sub text-secondary">Listening on 127.0.0.1:{ERPNEXT_PORT}</div>
                </div>
            </div>
        </div>

        <div class="frappe-card p-4 mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h2 class="h6 fw-bold mb-0">ERPNext Apparel Item Master (Live Data from Port {ERPNEXT_PORT})</h2>
                    <div class="text-secondary small">These items and variants are served directly by the independent ERPNext backend</div>
                </div>
                <div class="d-flex gap-2">
                    <a href="http://127.0.0.1:{ERPNEXT_PORT}/api/resource/Item" class="btn btn-sm btn-outline-secondary" target="_blank">Raw JSON API &rarr;</a>
                </div>
            </div>
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead>
                        <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                            <th>Item Code</th>
                            <th>Description</th>
                            <th>Group</th>
                            <th>Variant Attributes</th>
                            <th>Standard Rate</th>
                            <th>Stock Balance</th>
                            <th>Warehouse</th>
                        </tr>
                    </thead>
                    <tbody>
                        {item_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4">
                    <h3 class="h6 fw-bold mb-3">ERPNext Workspaces in App Catalogue</h3>
                    <div class="list-group list-group-flush">
                        <a href="/app/selling" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div><strong>🛒 Selling</strong> &bull; <span class="text-secondary small">Sales Orders, Pricing, Quotations</span></div>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/stock" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div><strong>📦 Stock</strong> &bull; <span class="text-secondary small">Garment Items, Variants, Pick Lists, Warehouses</span></div>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/buying" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div><strong>🏭 Buying</strong> &bull; <span class="text-secondary small">Fabric Mills, Yarn Suppliers, Purchase Orders</span></div>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/accounting" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                            <div><strong>💰 Accounting</strong> &bull; <span class="text-secondary small">Invoicing, General Ledger, Receivables</span></div>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4">
                    <h3 class="h6 fw-bold mb-2">Architectural Independence</h3>
                    <p class="text-secondary small mb-3">
                        ERPNext is running independently as requested. The custom app <code>clothing_erp</code> does not reimplement ERPNext core logic, ledgers, or database schemas; it consumes data directly via standard Frappe REST APIs.
                    </p>
                    <div class="p-3 bg-light rounded-2 font-monospace small">
                        <div><strong>ERPNext Backend:</strong> http://127.0.0.1:{ERPNEXT_PORT} (Independent)</div>
                        <div><strong>Unified Gateway:</strong> http://127.0.0.1:{PORT} (Auto-started Bundle)</div>
                        <div><strong>Client Connector:</strong> clothing_erp.erpnext_client</div>
                    </div>
                </div>
            </div>
        </div>
        """

    # -------------------------------------------------------------
    # 2. Clothing ERP Salesperson Portal
    # -------------------------------------------------------------
    elif view in ["salesperson"] or (view == "overview" and active_role == "Salesperson"):
        module_title = "Salesperson Portal"
        breadcrumbs = "Home / Clothing ERP / Salesperson Portal"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="alert('Stage 4: Register Retailer into ERPNext Customer')">+ Register Retailer</button>
            <button class="btn btn-primary btn-sm" onclick="alert('Stage 5: Size-Colour Matrix Order Creation')">+ New Sales Order</button>
        """

        m = sales_data["metrics"]
        kpi_html = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TODAY'S ORDERS</div>
                    <div class="frappe-card-number">{m['today_orders_count']}</div>
                    <div class="frappe-card-sub text-success">Live from ERPNext Sales Order &bull; ₹{m['today_orders_value']:,.0f}</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">CURRENT MONTH SALES</div>
                    <div class="frappe-card-number">₹{m['month_sales_value']:,.0f}</div>
                    <div class="frappe-card-sub text-secondary">Target: ₹{m['month_sales_target']:,.0f} (76%)</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ASSIGNED RETAILERS</div>
                    <div class="frappe-card-number">{m['assigned_retailers_count']}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Customer accounts</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING FOLLOW-UPS</div>
                    <div class="frappe-card-number text-warning">{m['pending_followups_count']}</div>
                    <div class="frappe-card-sub text-secondary">Scheduled retailer visits</div>
                </div>
            </div>
        </div>
        """

        rows_html = ""
        for o in sales_data["recent_orders"]:
            rows_html += f"""
            <tr class="align-middle">
                <td><a href="/app/sales-order" class="fw-semibold text-decoration-none text-dark">{o['name']}</a></td>
                <td>{o['customer']}</td>
                <td class="text-secondary">{o['items']} pcs</td>
                <td class="fw-semibold">₹{o['amount']:,.0f}</td>
                <td>{status_badge(o['status'])}</td>
                <td class="text-secondary small">{o['date']}</td>
            </tr>
            """

        content_body = f"""
        {kpi_html}
        <div class="row g-4">
            <div class="col-12 col-lg-8">
                <div class="frappe-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="h6 fw-bold mb-0">Recent Wholesale Orders (from ERPNext Backend)</h2>
                        <a href="/app/sales-order" class="text-decoration-none small text-secondary">View All &rarr;</a>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                                    <th>Order ID</th>
                                    <th>Retailer</th>
                                    <th>Units</th>
                                    <th>Amount</th>
                                    <th>Status</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-4">
                <div class="frappe-card p-4 mb-4">
                    <h2 class="h6 fw-bold mb-3">Quick Shortcuts</h2>
                    <div class="d-flex flex-column gap-2">
                        <a href="/app/item" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🏷️ Browse ERPNext Garment Catalog</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/customer" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🏬 Retailer Directory</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/sales-order" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🛒 Track Wholesale Orders</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                    </div>
                </div>

                <div class="frappe-card p-4">
                    <h2 class="h6 fw-bold mb-3">Scheduled Follow-ups</h2>
                    <div class="d-flex flex-column gap-3">
                        <div class="p-2 rounded" style="background: #f9fafb; border: 1px solid #f3f4f6;">
                            <div class="fw-bold small">Metro Garments Pvt Ltd</div>
                            <div class="text-secondary small">Contact: Rajesh Kumar &bull; Due: Tomorrow</div>
                            <div class="text-muted small mt-1">Winter collection pre-booking consultation.</div>
                        </div>
                        <div class="p-2 rounded" style="background: #f9fafb; border: 1px solid #f3f4f6;">
                            <div class="fw-bold small">Velvet Denims</div>
                            <div class="text-secondary small">Contact: Pooja Mehta &bull; Due: Nov 9</div>
                            <div class="text-muted small mt-1">Sample delivery confirmation and stock review.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    # -------------------------------------------------------------
    # 3. Clothing ERP Warehouse Operations
    # -------------------------------------------------------------
    elif view in ["warehouse"] or (view == "overview" and active_role == "Warehouse Operator"):
        module_title = "Warehouse Operations"
        breadcrumbs = "Home / Clothing ERP / Warehouse Operations"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="alert('Stage 6: Barcode Scanner Station')">📷 Scan Barcode</button>
            <button class="btn btn-primary btn-sm" onclick="alert('Stage 6: Pick List Assignment')">+ New Pick Task</button>
        """

        m = warehouse_data["metrics"]
        kpi_html = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ASSIGNED PICK LISTS</div>
                    <div class="frappe-card-number text-primary">{m['assigned_pick_lists']}</div>
                    <div class="frappe-card-sub text-secondary">From ERPNext Pick List doctype</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">AWAITING PACKING</div>
                    <div class="frappe-card-number text-warning">{m['orders_awaiting_packing']}</div>
                    <div class="frappe-card-sub text-secondary">Verified items ready for boxing</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">READY FOR DISPATCH</div>
                    <div class="frappe-card-number text-success">{m['orders_ready_for_dispatch']}</div>
                    <div class="frappe-card-sub text-secondary">From ERPNext Delivery Note</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">STOCK SHORTAGES</div>
                    <div class="frappe-card-number text-danger">{m['stock_shortages']}</div>
                    <div class="frappe-card-sub text-danger">Requires warehouse manager review</div>
                </div>
            </div>
        </div>
        """

        pick_rows = ""
        for p in warehouse_data["pick_tasks"]:
            pick_rows += f"""
            <tr class="align-middle">
                <td><a href="/app/pick-list" class="fw-semibold text-decoration-none text-dark">{p['pick_list']}</a></td>
                <td class="text-secondary">{p['order']}</td>
                <td>{p['customer']}</td>
                <td>{p['skus']} SKUs ({p['total_qty']} pcs)</td>
                <td>{status_badge(p['status'])}</td>
                <td><button class="btn btn-sm btn-outline-dark py-0 px-2" style="font-size: 11px;" onclick="alert('Picking {p['pick_list']}')">Pick</button></td>
            </tr>
            """

        content_body = f"""
        {kpi_html}
        <div class="row g-4">
            <div class="col-12 col-lg-8">
                <div class="frappe-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="h6 fw-bold mb-0">Assigned Picking Tasks (from ERPNext Pick List)</h2>
                        <span class="badge bg-light text-dark border">Finished Goods - CE</span>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                                    <th>Pick List</th>
                                    <th>Order Ref</th>
                                    <th>Customer</th>
                                    <th>Items</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pick_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-4">
                <div class="frappe-card p-4 mb-4">
                    <h2 class="h6 fw-bold mb-3">Dispatch Queue</h2>
                    <div class="d-flex flex-column gap-3">
                        <div class="p-3 rounded" style="background: #f9fafb; border: 1px solid #e5e7eb;">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <span class="fw-bold small">MAT-DN-2026-0019</span>
                                {status_badge("Ready for Dispatch")}
                            </div>
                            <div class="text-secondary small">Retailer: Classic Wear Distro</div>
                            <div class="text-secondary small">Carrier: BlueDart Express (4 boxes)</div>
                            <button class="btn btn-sm btn-success w-100 mt-2 py-1" onclick="alert('Confirm dispatch in ERPNext')">Confirm Dispatch &rarr;</button>
                        </div>
                    </div>
                </div>

                <div class="frappe-card p-4">
                    <h2 class="h6 fw-bold mb-2">Barcode Scan Station</h2>
                    <p class="text-secondary small mb-3">Scan product hangtag to verify SKU against ERPNext Item master.</p>
                    <div class="input-group mb-2">
                        <input type="text" class="form-control form-control-sm" placeholder="Scan SKU / Barcode..." id="barcode-input">
                        <button class="btn btn-dark btn-sm" onclick="alert('Scanned barcode: ' + (document.getElementById('barcode-input').value || 'TSH-CREW-BLK-M'))">Verify</button>
                    </div>
                </div>
            </div>
        </div>
        """

    else:
        # Default Unified Overview
        module_title = "Clothing ERP & ERPNext Unified Desk"
        breadcrumbs = "Home / Operational Workspaces / Overview"
        action_buttons = f"""
            <a href="http://127.0.0.1:{ERPNEXT_PORT}/app" target="_blank" class="btn btn-default btn-sm me-2">Independent ERPNext (:8001)</a>
            <button class="btn btn-primary btn-sm" onclick="location.href='/app/salesperson'">Open Salesperson Portal</button>
        """

        content_body = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TODAY'S ORDERS</div>
                    <div class="frappe-card-number">{sales_data['metrics']['today_orders_count']}</div>
                    <div class="frappe-card-sub text-success">₹{sales_data['metrics']['today_orders_value']:,.0f} &bull; Live from ERPNext</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">GARMENT SKUS</div>
                    <div class="frappe-card-number">{len(erp_items)}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Item & Variant master</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING PICKING</div>
                    <div class="frappe-card-number text-warning">{warehouse_data['metrics']['assigned_pick_lists']}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Pick List tasks</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">RETAILER NETWORK</div>
                    <div class="frappe-card-number text-primary">{len(erp_customers)}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Customer doctype</div>
                </div>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <span class="fs-4">🛍️</span>
                            <div>
                                <h3 class="h6 fw-bold mb-0">Salesperson Operational Interface</h3>
                                <div class="text-secondary small">Takes data directly from ERPNext Item & Customer records</div>
                            </div>
                        </div>
                        <a href="/app/salesperson" class="btn btn-sm btn-outline-dark">Open Portal &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Tailored for field sales representatives. Enables rapid catalog browsing, size-colour variant matrix ordering, customer-specific wholesale price lookup, and visit logging.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Salesperson</span>
                        <span class="badge bg-light text-dark border">Consumes: ERPNext Item, Customer</span>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <span class="fs-4">📦</span>
                            <div>
                                <h3 class="h6 fw-bold mb-0">Warehouse Operator Interface</h3>
                                <div class="text-secondary small">Takes tasks directly from ERPNext Pick List & Delivery Note</div>
                            </div>
                        </div>
                        <a href="/app/warehouse" class="btn btn-sm btn-outline-dark">Open Operations &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Tailored for warehouse and fulfillment staff. Streamlines picking list assignments, barcode scanning, carton packaging verification, and dispatch handoff to carriers.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Warehouse Operator</span>
                        <span class="badge bg-light text-dark border">Consumes: ERPNext Pick List, Delivery Note</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="alert alert-light border shadow-sm p-4 mt-4 rounded-3 d-flex align-items-center">
            <div class="fs-2 me-3">🔗</div>
            <div>
                <h4 class="h6 fw-bold mb-1">Bundled & Independent Architecture</h4>
                <div class="text-secondary small">
                    The ERPNext server auto-started independently on <code>http://127.0.0.1:{ERPNEXT_PORT}</code>.
                    All operational screens on this main gateway (<code>http://127.0.0.1:{PORT}</code>) dynamically query the ERPNext server via REST, guaranteeing that ERPNext core remains untouched and authoritative.
                </div>
            </div>
        </div>
        """

    active_overview = "active" if view in ["overview", "app"] and active_app != "erpnext" else ""
    active_sales = "active" if view == "salesperson" else ""
    active_warehouse = "active" if view == "warehouse" else ""
    active_erpnext_item = "active" if view in ["item", "stock"] else ""
    active_erpnext_cust = "active" if view in ["customer", "selling"] else ""

    sales_nav_item = f'<a href="/app/salesperson" class="sidebar-nav-item {active_sales}"><span>🛍️</span> Salesperson Portal</a>' if show_sales else ''
    warehouse_nav_item = f'<a href="/app/warehouse" class="sidebar-nav-item {active_warehouse}"><span>📦</span> Warehouse Operations</a>' if show_warehouse else ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{module_title} — ERPNext & Clothing ERP Gateway</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {{
            --frappe-bg: #f8fafc;
            --frappe-sidebar-bg: #ffffff;
            --frappe-border: #e5e7eb;
            --frappe-text-main: #1f2937;
            --frappe-text-muted: #6b7280;
            --frappe-btn-primary: #171717;
            --frappe-btn-hover: #262626;
        }}
        body {{
            background-color: var(--frappe-bg);
            color: var(--frappe-text-main);
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            font-size: 13px;
        }}
        .frappe-navbar {{
            height: 48px;
            background: #ffffff;
            border-bottom: 1px solid var(--frappe-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            position: sticky;
            top: 0;
            z-index: 1000;
        }}
        .app-switcher-btn {{
            background: #f3f4f6;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            color: #111827;
        }}
        .frappe-search-box {{
            width: 320px;
            background: #f3f4f6;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
            color: #4b5563;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .frappe-search-box .kbd-hint {{
            font-size: 10px;
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 3px;
            padding: 1px 4px;
            color: #6b7280;
        }}
        .frappe-sidebar {{
            width: 230px;
            background: var(--frappe-sidebar-bg);
            border-right: 1px solid var(--frappe-border);
            height: calc(100vh - 48px);
            position: sticky;
            top: 48px;
            padding: 12px 8px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}
        .sidebar-section-title {{
            font-size: 10px;
            text-transform: uppercase;
            font-weight: 700;
            color: #9ca3af;
            padding: 6px 12px 4px;
            letter-spacing: 0.5px;
        }}
        .sidebar-nav-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            border-radius: 6px;
            color: #374151;
            text-decoration: none;
            font-weight: 500;
            font-size: 12.5px;
            transition: all 0.15s ease;
            margin-bottom: 2px;
        }}
        .sidebar-nav-item:hover {{
            background: #f3f4f6;
            color: #111827;
        }}
        .sidebar-nav-item.active {{
            background: #e5e7eb;
            color: #111827;
            font-weight: 600;
        }}
        .frappe-card {{
            background: #ffffff;
            border: 1px solid var(--frappe-border);
            border-radius: 8px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
        }}
        .frappe-card-label {{
            font-size: 11px;
            font-weight: 600;
            color: var(--frappe-text-muted);
            margin-bottom: 4px;
            letter-spacing: 0.3px;
        }}
        .frappe-card-number {{
            font-size: 24px;
            font-weight: 700;
            color: #111827;
            line-height: 1.2;
            margin-bottom: 4px;
        }}
        .frappe-card-sub {{
            font-size: 11.5px;
        }}
        .btn-primary {{
            background-color: var(--frappe-btn-primary) !important;
            border-color: var(--frappe-btn-primary) !important;
            font-weight: 500;
        }}
        .btn-primary:hover {{
            background-color: var(--frappe-btn-hover) !important;
        }}
        .btn-default {{
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            color: #374151;
            font-weight: 500;
        }}
        .btn-default:hover {{
            background-color: #f9fafb;
            color: #111827;
        }}
        .frappe-shortcut-btn {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            padding: 8px 12px;
            border-radius: 6px;
            color: #374151;
            font-weight: 500;
            transition: all 0.15s ease;
        }}
        .frappe-shortcut-btn:hover {{
            border-color: #9ca3af;
            background: #f9fafb;
            color: #111827;
        }}
        .user-avatar {{
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #0284c7;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <header class="frappe-navbar">
        <div class="d-flex align-items-center gap-3">
            <div class="dropdown">
                <button class="app-switcher-btn dropdown-toggle" type="button" data-bs-toggle="dropdown">
                    <span style="font-size: 14px;">{'👕 Clothing ERP' if active_app == 'clothing_erp' else '📦 ERPNext'}</span>
                </button>
                <ul class="dropdown-menu shadow-sm">
                    <li><h6 class="dropdown-header text-uppercase small" style="font-size: 10px;">Select Application (Bundled)</h6></li>
                    <li><a class="dropdown-item {'fw-bold active' if active_app == 'clothing_erp' else ''}" href="/app">👕 Clothing ERP (Port 8000)</a></li>
                    <li><a class="dropdown-item {'fw-bold active' if active_app == 'erpnext' else ''}" href="/app/stock">📦 ERPNext (Auto-Started Backend)</a></li>
                </ul>
            </div>

            <div class="frappe-search-box d-none d-md-flex">
                <span>🔍 Search or type a command</span>
                <span class="kbd-hint">Ctrl + G</span>
            </div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <div class="dropdown">
                <button class="btn btn-sm dropdown-toggle py-1 px-2" style="{role_badge_style} font-size: 11.5px; font-weight: 600;" type="button" data-bs-toggle="dropdown">
                    <span>Perspective: <strong>{active_role}</strong></span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                    <li><h6 class="dropdown-header text-uppercase small" style="font-size: 10px;">Switch Test Role</h6></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Administrator')">👑 Administrator / Management</a></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Salesperson')">🛍️ Clothing Salesperson</a></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Warehouse Operator')">📦 Clothing Warehouse Operator</a></li>
                </ul>
            </div>

            <span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">ERPNext Backend: Online</span>

            <div class="d-flex align-items-center gap-2">
                <div class="user-avatar" title="Administrator">AD</div>
                <span class="d-none d-lg-inline small fw-semibold text-secondary">Avi</span>
            </div>
        </div>
    </header>

    <div class="d-flex">
        <aside class="frappe-sidebar d-none d-md-flex">
            <div class="sidebar-section-title">Clothing ERP Modules</div>
            <a href="/app" class="sidebar-nav-item {active_overview}">
                <span>🏠</span> Overview
            </a>
            {sales_nav_item}
            {warehouse_nav_item}

            <div class="sidebar-section-title mt-3">ERPNext App Catalogue</div>
            <a href="/app/item" class="sidebar-nav-item {active_erpnext_item}">
                <span>🏷️</span> Item (Garment Catalog)
            </a>
            <a href="/app/customer" class="sidebar-nav-item {active_erpnext_cust}">
                <span>🏬</span> Customer (Retailers)
            </a>
            <a href="/app/selling" class="sidebar-nav-item {'active' if view == 'selling' else ''}">
                <span>🛒</span> Selling (Orders)
            </a>
            <a href="/app/stock" class="sidebar-nav-item {'active' if view == 'stock' else ''}">
                <span>🏭</span> Stock (Warehouses)
            </a>
            <a href="/app/buying" class="sidebar-nav-item {'active' if view == 'buying' else ''}">
                <span>🚚</span> Buying (Suppliers)
            </a>
            <a href="/app/accounting" class="sidebar-nav-item {'active' if view == 'accounting' else ''}">
                <span>💰</span> Accounting (Ledger)
            </a>

            <div class="mt-auto pt-3 border-top small text-muted px-2">
                <div><strong>ERPNext &bull; Clothing ERP</strong></div>
                <div style="font-size: 11px;">Bundled on 127.0.0.1:8000</div>
            </div>
        </aside>

        <main class="flex-grow-1 p-4" style="min-height: calc(100vh - 48px); max-width: 1300px;">
            <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center pb-3 mb-4 border-bottom gap-2">
                <div>
                    <div class="text-secondary small mb-1">{breadcrumbs}</div>
                    <h1 class="h4 fw-bold text-dark mb-0">{module_title}</h1>
                </div>
                <div class="d-flex align-items-center">
                    {action_buttons}
                </div>
            </div>

            {content_body}
        </main>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function switchRole(role) {{
            fetch('/api/method/clothing_erp.api.switch_preview_role', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                body: 'role=' + encodeURIComponent(role)
            }})
            .then(res => res.json())
            .then(data => {{
                if (role === 'Salesperson') {{
                    location.href = '/app/salesperson';
                }} else if (role === 'Warehouse Operator') {{
                    location.href = '/app/warehouse';
                }} else {{
                    location.href = '/app';
                }}
            }})
            .catch(err => console.error(err));
        }}
    </script>
</body>
</html>
"""


class BundledGatewayHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Handle root and portals
        if path in ["/", "/clothing", "/clothing-erp", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_bundled_desk_html(view="overview").encode("utf-8"))

        elif path in ["/app", "/app/"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_bundled_desk_html(view="overview").encode("utf-8"))

        elif path in ["/app/salesperson", "/salesperson"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_bundled_desk_html(view="salesperson", active_role="Salesperson").encode("utf-8"))

        elif path in ["/app/warehouse", "/warehouse"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_bundled_desk_html(view="warehouse", active_role="Warehouse Operator").encode("utf-8"))

        elif path.startswith("/app/"):
            subview = path.replace("/app/", "").strip("/")
            is_erp = subview in ["selling", "stock", "buying", "accounting", "crm", "settings", "item", "customer"]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_bundled_desk_html(view=subview, active_app="erpnext" if is_erp else "clothing_erp").encode("utf-8"))

        # APIs for data consumed from ERPNext
        elif path == "/api/resource/Item":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": get_items()}, indent=2).encode("utf-8"))

        elif path == "/api/resource/Customer":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": get_customers()}, indent=2).encode("utf-8"))

        elif path == "/api/resource/Sales Order":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": get_sales_orders()}, indent=2).encode("utf-8"))

        elif path == "/api/method/clothing_erp.api.get_user_context":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_user_context(), indent=2).encode("utf-8"))

        elif path == "/api/method/clothing_erp.api.get_salesperson_dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_salesperson_dashboard(), indent=2).encode("utf-8"))

        elif path == "/api/method/clothing_erp.api.get_warehouse_dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_warehouse_dashboard(), indent=2).encode("utf-8"))

        elif path == "/api/method/clothing_erp.get_status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {
                "status": "online",
                "app": "clothing_erp",
                "version": "0.1.0",
                "bundled_erpnext_server": {
                    "url": f"http://127.0.0.1:{ERPNEXT_PORT}",
                    "online": check_erpnext_server(),
                    "version": "16.54.0",
                },
                "same_ip_host": True,
            }
            self.wfile.write(json.dumps(status, indent=2).encode("utf-8"))

        else:
            self.send_response(302)
            self.send_header("Location", "/app")
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/method/clothing_erp.api.switch_preview_role":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(body)
            role = params.get("role", ["Administrator"])[0]

            result = switch_preview_role(role)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        sys.stderr.write(f"[Bundled Gateway] {self.address_string()} - {format % args}\n")


def run():
    # 1. Auto-start the independent ERPNext backend server
    ensure_erpnext_running()

    # 2. Launch the Gateway server
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), BundledGatewayHandler) as httpd:
        print(f"[Gateway] Bundled Server running on http://127.0.0.1:{PORT}")
        print(f"[Gateway] ERPNext server running independently on http://127.0.0.1:{ERPNEXT_PORT}")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run()
