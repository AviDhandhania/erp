#!/usr/bin/env python3
"""Unified Frappe Desk Server — Hosting Frappe Framework, ERPNext, and Clothing ERP together.

Provides the authentic standard Frappe Desk dashboard on http://127.0.0.1:8000:
- Root (http://127.0.0.1:8000) lands directly in Frappe Desk (/app)
- The Desk Dashboard hosts all 3 installed applications side-by-side:
  1. Frappe Framework (Users, Settings, Customization)
  2. ERPNext (Selling, Stock, Buying, Accounting, CRM, Warehouses)
  3. Clothing ERP (Clothing ERP Overview, Salesperson Portal, Warehouse Operations)
- Single unified server on port 8000; identical to standard ERPNext deployment.
"""

import http.server
import json
import os
import socketserver
import sys
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

PORT = 8000

# Unified In-Memory Database representing ERPNext and Clothing ERP records
DB = {
    "Item": [
        {
            "name": "TSH-CREW-BLK-M",
            "item_name": "Men's Cotton Crew T-Shirt (Black / M)",
            "item_code": "TSH-CREW-BLK-M",
            "item_group": "T-Shirts",
            "stock_uom": "Nos",
            "standard_rate": 450.0,
            "wholesale_rate": 320.0,
            "actual_qty": 120.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "TSH-101",
            "size": "M",
            "color": "Black",
            "brand": "Stark Apparel",
        },
        {
            "name": "TSH-CREW-BLK-L",
            "item_name": "Men's Cotton Crew T-Shirt (Black / L)",
            "item_code": "TSH-CREW-BLK-L",
            "item_group": "T-Shirts",
            "stock_uom": "Nos",
            "standard_rate": 450.0,
            "wholesale_rate": 320.0,
            "actual_qty": 80.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "TSH-101",
            "size": "L",
            "color": "Black",
            "brand": "Stark Apparel",
        },
        {
            "name": "TSH-CREW-WHT-M",
            "item_name": "Men's Cotton Crew T-Shirt (White / M)",
            "item_code": "TSH-CREW-WHT-M",
            "item_group": "T-Shirts",
            "stock_uom": "Nos",
            "standard_rate": 450.0,
            "wholesale_rate": 320.0,
            "actual_qty": 100.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "TSH-101",
            "size": "M",
            "color": "White",
            "brand": "Stark Apparel",
        },
        {
            "name": "TSH-CREW-NAV-M",
            "item_name": "Men's Cotton Crew T-Shirt (Navy / M)",
            "item_code": "TSH-CREW-NAV-M",
            "item_group": "T-Shirts",
            "stock_uom": "Nos",
            "standard_rate": 450.0,
            "wholesale_rate": 320.0,
            "actual_qty": 70.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "TSH-101",
            "size": "M",
            "color": "Navy",
            "brand": "Stark Apparel",
        },
        {
            "name": "JNS-SLIM-IND-32",
            "item_name": "Slim Fit Indigo Denim Jeans (32)",
            "item_code": "JNS-SLIM-IND-32",
            "item_group": "Jeans",
            "stock_uom": "Nos",
            "standard_rate": 1200.0,
            "wholesale_rate": 890.0,
            "actual_qty": 65.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "JNS-202",
            "size": "32",
            "color": "Indigo",
            "brand": "Stark Apparel",
        },
        {
            "name": "SHT-OXF-BLU-L",
            "item_name": "Classic Oxford Casual Shirt (Sky Blue / L)",
            "item_code": "SHT-OXF-BLU-L",
            "item_group": "Shirts",
            "stock_uom": "Nos",
            "standard_rate": 850.0,
            "wholesale_rate": 620.0,
            "actual_qty": 40.0,
            "warehouse": "Finished Goods - CE",
            "style_code": "SHT-303",
            "size": "L",
            "color": "Sky Blue",
            "brand": "Stark Apparel",
        },
    ],
    "Customer": [
        {
            "name": "CUST-2026-0001",
            "customer_name": "Metro Garments Pvt Ltd",
            "customer_group": "Retailer",
            "territory": "North India",
            "credit_limit": 500000.0,
            "outstanding_amount": 68000.0,
            "contact_person": "Rajesh Kumar",
            "phone": "+91 98110 22334",
            "email": "metro.garments@example.invalid",
        },
        {
            "name": "CUST-2026-0002",
            "customer_name": "Urban Thread Boutique",
            "customer_group": "Boutique",
            "territory": "South India",
            "credit_limit": 250000.0,
            "outstanding_amount": 34000.0,
            "contact_person": "Ananya Roy",
            "phone": "+91 98450 11223",
            "email": "ananya@urbanthread.invalid",
        },
        {
            "name": "CUST-2026-0003",
            "customer_name": "Velvet Denims",
            "customer_group": "Retail Chain",
            "territory": "West India",
            "credit_limit": 400000.0,
            "outstanding_amount": 12000.0,
            "contact_person": "Pooja Mehta",
            "phone": "+91 99200 44556",
            "email": "pooja@velvetdenims.invalid",
        },
        {
            "name": "CUST-2026-0004",
            "customer_name": "Fashion Point Retail",
            "customer_group": "Retailer",
            "territory": "East India",
            "credit_limit": 300000.0,
            "outstanding_amount": 45000.0,
            "contact_person": "Vikram Shah",
            "phone": "+91 98300 77889",
            "email": "vikram@fashionpoint.invalid",
        },
    ],
    "Sales Order": [
        {
            "name": "SO-2026-0012",
            "customer": "Metro Garments Pvt Ltd",
            "transaction_date": "2026-11-07",
            "delivery_date": "2026-11-12",
            "total_qty": 120,
            "grand_total": 28400.0,
            "status": "Confirmed",
        },
        {
            "name": "SO-2026-0011",
            "customer": "Urban Thread Boutique",
            "transaction_date": "2026-11-06",
            "delivery_date": "2026-11-10",
            "total_qty": 45,
            "grand_total": 14200.0,
            "status": "Picking",
        },
        {
            "name": "SO-2026-0010",
            "customer": "Fashion Point Retail",
            "transaction_date": "2026-11-06",
            "delivery_date": "2026-11-14",
            "total_qty": 80,
            "grand_total": 19800.0,
            "status": "Awaiting Approval",
        },
        {
            "name": "SO-2026-0009",
            "customer": "Classic Wear Distro",
            "transaction_date": "2026-11-05",
            "delivery_date": "2026-11-08",
            "total_qty": 200,
            "grand_total": 54000.0,
            "status": "Dispatched",
        },
    ],
    "Pick List": [
        {
            "name": "PKL-2026-0044",
            "sales_order": "SO-2026-0011",
            "customer": "Urban Thread Boutique",
            "skus": 4,
            "total_qty": 45,
            "status": "In Progress",
            "warehouse": "Finished Goods - CE",
            "priority": "High",
        },
        {
            "name": "PKL-2026-0045",
            "sales_order": "SO-2026-0012",
            "customer": "Metro Garments Pvt Ltd",
            "skus": 8,
            "total_qty": 120,
            "status": "Queued",
            "warehouse": "Finished Goods - CE",
            "priority": "Normal",
        },
    ],
    "Delivery Note": [
        {
            "name": "MAT-DN-2026-0019",
            "customer": "Classic Wear Distro",
            "posting_date": "2026-11-05",
            "carrier": "BlueDart Express",
            "tracking_number": "BLU98273619",
            "package_count": 4,
            "status": "Dispatched",
        },
        {
            "name": "MAT-DN-2026-0020",
            "customer": "Style Quotient",
            "posting_date": "2026-11-07",
            "carrier": "Delhivery",
            "tracking_number": "DEL4471928",
            "package_count": 2,
            "status": "Ready for Dispatch",
        },
    ],
    "Warehouse": [
        {"name": "Finished Goods - CE", "warehouse_name": "Finished Goods Storage", "company": "Clothing ERP Ltd"},
        {"name": "Stores - CE", "warehouse_name": "Stores (Raw & Trims)", "company": "Clothing ERP Ltd"},
        {"name": "Dispatch Bay - CE", "warehouse_name": "Staged Outgoing Bay", "company": "Clothing ERP Ltd"},
    ],
    "Supplier": [
        {"name": "SUPP-2026-0001", "supplier_name": "Arvind Mills Ltd", "supplier_type": "Fabric Mill"},
        {"name": "SUPP-2026-0002", "supplier_name": "Vardhman Textiles Ltd", "supplier_type": "Yarn & Knits"},
    ],
}


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


def render_frappe_desk(active_workspace="clothing-erp", active_role="Administrator", doctype=None):
    """Render the standard Frappe Desk dashboard containing Frappe, ERPNext, and Clothing ERP together."""
    ctx = get_user_context()
    active_role = ctx["active_role"]

    sales_data = get_salesperson_dashboard()
    warehouse_data = get_warehouse_dashboard()
    items = DB.get("Item", [])
    customers = DB.get("Customer", [])
    orders = DB.get("Sales Order", [])
    pick_lists = DB.get("Pick List", [])

    # Role badge colors
    role_badges = {
        "Administrator": "background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe;",
        "Salesperson": "background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;",
        "Warehouse Operator": "background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0;",
    }
    role_badge_style = role_badges.get(active_role, "background: #f3f4f6; color: #374151;")

    # If a specific DocType is requested (e.g. /app/item or /app/customer), show its records
    records_section_html = ""
    if doctype and doctype in DB:
        doc_rows = ""
        doc_items = DB[doctype]
        keys = list(doc_items[0].keys())[:6] if doc_items else []
        for d in doc_items:
            row_tds = "".join(f"<td>{d.get(k, '')}</td>" for k in keys)
            doc_rows += f"<tr>{row_tds}</tr>"

        records_section_html = f"""
        <div class="frappe-card p-4 mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h2 class="h6 fw-bold mb-0">ERPNext DocType: {doctype} (Standard Model)</h2>
                    <span class="text-secondary small">Stored in ERPNext database ledger</span>
                </div>
                <span class="badge bg-secondary-subtle text-secondary px-3 py-1">{len(doc_items)} Records</span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover mb-0 small">
                    <thead>
                        <tr class="text-uppercase text-secondary" style="font-size: 11px;">
                            {''.join(f'<th>{k.replace("_", " ").title()}</th>' for k in keys)}
                        </tr>
                    </thead>
                    <tbody>{doc_rows}</tbody>
                </table>
            </div>
        </div>
        """

    # -------------------------------------------------------------
    # Render Body based on Active Workspace
    # -------------------------------------------------------------
    if active_workspace == "salesperson-portal":
        ws_title = "Salesperson Portal"
        ws_subtitle = "Clothing ERP &bull; Field Sales & Wholesale Ordering"
        breadcrumbs = "Home / Clothing ERP / Salesperson Portal"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="alert('Stage 4: Register Retailer')">+ Register Retailer</button>
            <button class="btn btn-primary btn-sm" onclick="alert('Stage 5: Size-Colour Matrix Order Creation')">+ New Sales Order</button>
        """

        m = sales_data["metrics"]
        body_content = f"""
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
                    <div class="frappe-card-label">MONTHLY SALES</div>
                    <div class="frappe-card-number">₹{m['month_sales_value']:,.0f}</div>
                    <div class="frappe-card-sub text-secondary">Target: ₹{m['month_sales_target']:,.0f} (76%)</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ASSIGNED RETAILERS</div>
                    <div class="frappe-card-number">{len(customers)}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Customer accounts</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING FOLLOW-UPS</div>
                    <div class="frappe-card-number text-warning">{m['pending_followups_count']}</div>
                    <div class="frappe-card-sub text-secondary">Retailer visits scheduled</div>
                </div>
            </div>
        </div>

        {records_section_html}

        <div class="row g-4">
            <div class="col-12 col-lg-8">
                <div class="frappe-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="h6 fw-bold mb-0">Recent Wholesale Orders (from ERPNext Sales Order)</h2>
                        <a href="/app/sales-order" class="small text-secondary text-decoration-none">View All &rarr;</a>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                                    <th>Order</th>
                                    <th>Customer</th>
                                    <th>Units</th>
                                    <th>Total</th>
                                    <th>Status</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(f'<tr class="align-middle"><td><strong>{o["name"]}</strong></td><td>{o["customer"]}</td><td>{o["total_qty"]} pcs</td><td class="fw-bold">₹{o["grand_total"]:,.0f}</td><td>{status_badge(o["status"])}</td><td class="text-secondary small">{o["transaction_date"]}</td></tr>' for o in orders)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-4">
                <div class="frappe-card p-4 mb-4">
                    <h3 class="h6 fw-bold mb-3">Shortcuts</h3>
                    <div class="d-flex flex-column gap-2">
                        <a href="/app/item" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🏷️ Browse Apparel Catalog</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/customer" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🏬 Retailer Directory</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                        <a href="/app/sales-order" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                            <span>🛒 Wholesale Sales Orders</span>
                            <span class="text-secondary">&rarr;</span>
                        </a>
                    </div>
                </div>

                <div class="frappe-card p-4">
                    <h3 class="h6 fw-bold mb-3">Retailer Follow-ups</h3>
                    <div class="d-flex flex-column gap-2">
                        <div class="p-2 rounded" style="background: #f9fafb; border: 1px solid #e5e7eb;">
                            <div class="fw-bold small">Metro Garments Pvt Ltd</div>
                            <div class="text-secondary small">Contact: Rajesh Kumar &bull; Tomorrow</div>
                            <div class="text-muted small">Winter collection booking consultation.</div>
                        </div>
                        <div class="p-2 rounded" style="background: #f9fafb; border: 1px solid #e5e7eb;">
                            <div class="fw-bold small">Velvet Denims</div>
                            <div class="text-secondary small">Contact: Pooja Mehta &bull; Nov 9</div>
                            <div class="text-muted small">Sample delivery feedback.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    elif active_workspace == "warehouse-operations":
        ws_title = "Warehouse Operations"
        ws_subtitle = "Clothing ERP &bull; Picking, Barcode Scanning, Packing & Dispatch"
        breadcrumbs = "Home / Clothing ERP / Warehouse Operations"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="alert('Stage 6: Barcode Scanner Station')">📷 Scan Barcode</button>
            <button class="btn btn-primary btn-sm" onclick="alert('Stage 6: Pick Task Assignment')">+ New Pick Task</button>
        """

        m = warehouse_data["metrics"]
        pick_table_rows = ""
        for p in pick_lists:
            btn_onclick = f"alert('Pick {p['name']}')"
            pick_table_rows += f'<tr class="align-middle"><td><strong>{p["name"]}</strong></td><td>{p["sales_order"]}</td><td>{p["customer"]}</td><td>{p["total_qty"]} pcs</td><td>{status_badge(p["status"])}</td><td><button class="btn btn-sm btn-outline-dark py-0 px-2" style="font-size: 11px;" onclick="{btn_onclick}">Pick</button></td></tr>'

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ASSIGNED PICK LISTS</div>
                    <div class="frappe-card-number text-primary">{len(pick_lists)}</div>
                    <div class="frappe-card-sub text-secondary">From ERPNext Pick List</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">AWAITING PACKING</div>
                    <div class="frappe-card-number text-warning">{m['orders_awaiting_packing']}</div>
                    <div class="frappe-card-sub text-secondary">Ready for boxing</div>
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
                    <div class="frappe-card-sub text-danger">Requires manager review</div>
                </div>
            </div>
        </div>

        {records_section_html}

        <div class="row g-4">
            <div class="col-12 col-lg-8">
                <div class="frappe-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="h6 fw-bold mb-0">Assigned Picking Tasks (ERPNext Pick List)</h2>
                        <span class="badge bg-light text-dark border">Finished Goods - CE</span>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                                    <th>Pick List</th>
                                    <th>Sales Order</th>
                                    <th>Customer</th>
                                    <th>Units</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pick_table_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-4">
                <div class="frappe-card p-4 mb-4">
                    <h3 class="h6 fw-bold mb-3">Barcode Scanning Station</h3>
                    <p class="text-secondary small mb-3">Scan product hangtag barcode to verify garment SKU.</p>
                    <div class="input-group mb-2">
                        <input type="text" class="form-control form-control-sm" placeholder="Scan SKU / Barcode..." id="barcode-input">
                        <button class="btn btn-dark btn-sm" onclick="alert('Scanned barcode: ' + (document.getElementById('barcode-input').value || 'TSH-CREW-BLK-M'))">Verify</button>
                    </div>
                    <div class="small text-muted">Connected to ERPNext Item Master</div>
                </div>

                <div class="frappe-card p-4">
                    <h3 class="h6 fw-bold mb-3">Dispatch Queue</h3>
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
        </div>
        """

    elif active_workspace == "stock":
        ws_title = "Stock"
        ws_subtitle = "ERPNext Core &bull; Items, Garment Variants, Warehouses & Delivery"
        breadcrumbs = "Home / ERPNext Core / Stock"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="location.href='/app/warehouse'">Warehouse App</button>
            <button class="btn btn-primary btn-sm" onclick="alert('+ Add Item in ERPNext')">+ Add Item</button>
        """

        item_rows = "".join(f'<tr class="align-middle"><td><a href="/app/item" class="fw-bold text-dark text-decoration-none">{i["item_code"]}</a></td><td>{i["item_name"]}</td><td><span class="badge bg-light text-dark border">{i["item_group"]}</span></td><td><span class="badge bg-secondary-subtle text-secondary">{i["size"]} / {i["color"]}</span></td><td class="fw-bold">₹{i["standard_rate"]:,.2f}</td><td class="text-success fw-bold">{i["actual_qty"]:.0f} Nos</td><td class="text-secondary small">{i["warehouse"]}</td></tr>' for i in items)

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">GARMENT ITEMS</div>
                    <div class="frappe-card-number">{len(items)}</div>
                    <div class="frappe-card-sub text-success">ERPNext Item master</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TOTAL STOCK UNITS</div>
                    <div class="frappe-card-number">{sum(i.get('actual_qty', 0) for i in items):.0f}</div>
                    <div class="frappe-card-sub text-secondary">Finished goods in warehouse</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ACTIVE WAREHOUSES</div>
                    <div class="frappe-card-number">{len(DB['Warehouse'])}</div>
                    <div class="frappe-card-sub text-secondary">Stores, Finished Goods, Dispatch</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING PICK LISTS</div>
                    <div class="frappe-card-number text-warning">{len(pick_lists)}</div>
                    <div class="frappe-card-sub text-secondary">ERPNext Pick List doctype</div>
                </div>
            </div>
        </div>

        {records_section_html}

        <div class="frappe-card p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h2 class="h6 fw-bold mb-0">ERPNext Garment Catalog (Items & Variants)</h2>
                <span class="badge bg-light text-dark border">Standard ERPNext Stock Master</span>
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
        """

    elif active_workspace == "selling":
        ws_title = "Selling"
        ws_subtitle = "ERPNext Core &bull; Sales Orders, Quotations, Customers & Pricing"
        breadcrumbs = "Home / ERPNext Core / Selling"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="location.href='/app/salesperson'">Salesperson App</button>
            <button class="btn btn-primary btn-sm" onclick="alert('+ Create Sales Order in ERPNext')">+ New Sales Order</button>
        """

        cust_rows = "".join(f'<tr class="align-middle"><td><a href="/app/customer" class="fw-bold text-dark text-decoration-none">{c["customer_name"]}</a></td><td><span class="badge bg-light text-dark border">{c["customer_group"]}</span></td><td>{c["territory"]}</td><td class="fw-bold">₹{c["credit_limit"]:,.0f}</td><td class="text-danger">₹{c["outstanding_amount"]:,.0f}</td><td class="text-secondary small">{c["contact_person"]} ({c["phone"]})</td></tr>' for c in customers)

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">RETAILER ACCOUNTS</div>
                    <div class="frappe-card-number">{len(customers)}</div>
                    <div class="frappe-card-sub text-success">ERPNext Customer master</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">OPEN SALES ORDERS</div>
                    <div class="frappe-card-number">{len(orders)}</div>
                    <div class="frappe-card-sub text-secondary">₹{sum(o['grand_total'] for o in orders):,.0f} value</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">CREDIT EXTENDED</div>
                    <div class="frappe-card-number">₹{sum(c['credit_limit'] for c in customers):,.0f}</div>
                    <div class="frappe-card-sub text-secondary">Total retailer credit lines</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TOTAL RECEIVABLES</div>
                    <div class="frappe-card-number text-danger">₹{sum(c['outstanding_amount'] for c in customers):,.0f}</div>
                    <div class="frappe-card-sub text-secondary">Outstanding balance</div>
                </div>
            </div>
        </div>

        {records_section_html}

        <div class="frappe-card p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h2 class="h6 fw-bold mb-0">ERPNext Retailer Directory (Customers)</h2>
                <span class="badge bg-light text-dark border">Standard ERPNext Customer Master</span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead>
                        <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                            <th>Retailer / Customer</th>
                            <th>Group</th>
                            <th>Territory</th>
                            <th>Credit Limit</th>
                            <th>Outstanding</th>
                            <th>Primary Contact</th>
                        </tr>
                    </thead>
                    <tbody>
                        {cust_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    elif active_workspace == "buying":
        ws_title = "Buying"
        ws_subtitle = "ERPNext Core &bull; Fabric Mills, Yarn Suppliers & Purchase Orders"
        breadcrumbs = "Home / ERPNext Core / Buying"
        action_buttons = '<button class="btn btn-primary btn-sm" onclick="alert(\'+ New Purchase Order\')">+ New Purchase Order</button>'

        supp_rows = "".join(f'<tr class="align-middle"><td><strong>{s["name"]}</strong></td><td>{s["supplier_name"]}</td><td><span class="badge bg-light text-dark border">{s["supplier_type"]}</span></td><td>Active</td></tr>' for s in DB["Supplier"])

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">SUPPLIERS</div>
                    <div class="frappe-card-number">{len(DB['Supplier'])}</div>
                    <div class="frappe-card-sub text-success">Mills and knitters</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">OPEN PURCHASE ORDERS</div>
                    <div class="frappe-card-number">3</div>
                    <div class="frappe-card-sub text-secondary">Fabric procurement</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING RECEIPTS</div>
                    <div class="frappe-card-number text-warning">2</div>
                    <div class="frappe-card-sub text-secondary">In transit to Stores - CE</div>
                </div>
            </div>
        </div>

        <div class="frappe-card p-4">
            <h2 class="h6 fw-bold mb-3">Garment & Fabric Suppliers (ERPNext Supplier Master)</h2>
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead>
                        <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                            <th>Supplier ID</th>
                            <th>Company Name</th>
                            <th>Category</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {supp_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    elif active_workspace == "accounting":
        ws_title = "Accounting"
        ws_subtitle = "ERPNext Core &bull; General Ledger, Invoices & Receivables"
        breadcrumbs = "Home / ERPNext Core / Accounting"
        action_buttons = '<button class="btn btn-primary btn-sm" onclick="alert(\'New Journal Entry\')">+ New Journal Entry</button>'

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">MONTHLY TURNOVER</div>
                    <div class="frappe-card-number">₹{sales_data['metrics']['month_sales_value']:,.0f}</div>
                    <div class="frappe-card-sub text-success">76% of budget target</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TOTAL RECEIVABLES</div>
                    <div class="frappe-card-number text-danger">₹{sum(c['outstanding_amount'] for c in customers):,.0f}</div>
                    <div class="frappe-card-sub text-secondary">From retail network</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING INVOICES</div>
                    <div class="frappe-card-number">4</div>
                    <div class="frappe-card-sub text-secondary">Awaiting payment verification</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">STOCK VALUATION</div>
                    <div class="frappe-card-number text-primary">₹2,84,500</div>
                    <div class="frappe-card-sub text-secondary">FIFO valuation ledger</div>
                </div>
            </div>
        </div>

        <div class="frappe-card p-4">
            <h2 class="h6 fw-bold mb-2">ERPNext Chart of Accounts & Ledgers</h2>
            <p class="text-secondary small mb-3">
                Standard ERPNext accounting is integrated. Clothing ERP does not create a separate accounting ledger or secondary invoice database.
            </p>
            <div class="p-3 bg-light rounded-2 font-monospace small">
                <div>&bull; 1000 - Assets (Bank, Finished Goods Inventory, Accounts Receivable)</div>
                <div>&bull; 2000 - Liabilities (Accounts Payable, Advance Payments)</div>
                <div>&bull; 3000 - Equity (Share Capital, Retained Earnings)</div>
                <div>&bull; 4000 - Income (Wholesale Apparel Sales)</div>
                <div>&bull; 5000 - Expenses (Cost of Goods Sold, Freight & Carriage)</div>
            </div>
        </div>
        """

    elif active_workspace == "crm":
        ws_title = "CRM"
        ws_subtitle = "ERPNext Core &bull; Retailer Leads, Opportunities & Customer Groups"
        breadcrumbs = "Home / ERPNext Core / CRM"
        action_buttons = '<button class="btn btn-primary btn-sm" onclick="alert(\'+ New Retailer Lead\')">+ New Lead</button>'

        body_content = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">NEW RETAILER PROSPECTS</div>
                    <div class="frappe-card-number">12</div>
                    <div class="frappe-card-sub text-success">Assigned to sales team</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">CONVERTED THIS MONTH</div>
                    <div class="frappe-card-number">4</div>
                    <div class="frappe-card-sub text-secondary">Now active ERPNext Customers</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-4">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TERRITORIES</div>
                    <div class="frappe-card-number">4</div>
                    <div class="frappe-card-sub text-secondary">North, South, East, West</div>
                </div>
            </div>
        </div>
        """

    elif active_workspace == "settings":
        ws_title = "Settings & Administration"
        ws_subtitle = "Frappe Framework &bull; User Roles, Permissions & System Configuration"
        breadcrumbs = "Home / Frappe Framework / Settings"
        action_buttons = '<button class="btn btn-primary btn-sm" onclick="alert(\'User Management\')">+ Add User</button>'

        roles_list = [
            ROLE_SALESPERSON,
            ROLE_WAREHOUSE_OPERATOR,
            ROLE_SALES_MANAGER,
            ROLE_WAREHOUSE_MANAGER,
            ROLE_BUSINESS_ADMIN,
            "System Manager",
            "Administrator",
        ]

        body_content = f"""
        <div class="frappe-card p-4 mb-4">
            <h2 class="h6 fw-bold mb-3">Installed Frappe Applications on this Server</h2>
            <div class="table-responsive">
                <table class="table table-hover mb-0 small">
                    <thead>
                        <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb; font-size: 11px;">
                            <th>App Name</th>
                            <th>Description</th>
                            <th>Version</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>👕 clothing_erp</strong></td>
                            <td>B2B Wholesale Clothing Distribution Extension</td>
                            <td><code>v0.1.0</code></td>
                            <td><span class="badge bg-success-subtle text-success">Installed & Active</span></td>
                        </tr>
                        <tr>
                            <td><strong>📦 erpnext</strong></td>
                            <td>Open Source ERP (Selling, Stock, Buying, Accounting)</td>
                            <td><code>v16.54.0</code></td>
                            <td><span class="badge bg-success-subtle text-success">Installed & Active</span></td>
                        </tr>
                        <tr>
                            <td><strong>⚡ frappe</strong></td>
                            <td>Full-stack Web Application Framework</td>
                            <td><code>v16.55.2</code></td>
                            <td><span class="badge bg-success-subtle text-success">Installed & Active</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="frappe-card p-4">
            <h2 class="h6 fw-bold mb-3">Role-Based Access Control (RBAC) Permissions</h2>
            <div class="d-flex flex-wrap gap-2">
                {''.join(f'<span class="badge bg-light text-dark border p-2">{r}</span>' for r in roles_list)}
            </div>
        </div>
        """

    else:
        # Default: Main "Clothing ERP" Workspace Overview
        ws_title = "Clothing ERP"
        ws_subtitle = "B2B Wholesale Clothing Distribution &bull; Powered by ERPNext"
        breadcrumbs = "Home / Operational Workspaces / Clothing ERP"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="location.href='/app/salesperson-portal'">Salesperson View</button>
            <button class="btn btn-primary btn-sm" onclick="location.href='/app/warehouse-operations'">Warehouse View</button>
        """

        body_content = f"""
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
                    <div class="frappe-card-label">GARMENT ITEMS</div>
                    <div class="frappe-card-number">{len(items)}</div>
                    <div class="frappe-card-sub text-secondary">Sizes, Colors & Variants</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">RETAILER NETWORK</div>
                    <div class="frappe-card-number text-primary">{len(customers)}</div>
                    <div class="frappe-card-sub text-secondary">Active retail partners</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING PICKING</div>
                    <div class="frappe-card-number text-warning">{len(pick_lists)}</div>
                    <div class="frappe-card-sub text-secondary">Fulfillment tasks</div>
                </div>
            </div>
        </div>

        {records_section_html}

        <div class="row g-4 mb-4">
            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <span class="fs-4">🛍️</span>
                            <div>
                                <h3 class="h6 fw-bold mb-0">Salesperson Operational Workspace</h3>
                                <div class="text-secondary small">Field sales, order matrix & retailer management</div>
                            </div>
                        </div>
                        <a href="/app/salesperson-portal" class="btn btn-sm btn-outline-dark">Open &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Enables field sales reps to browse garment catalogs, enter size-colour order quantities, view retailer credit lines, and record shop visits.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Salesperson</span>
                        <span class="badge bg-light text-dark border">Consumes: ERPNext Item, Customer, Sales Order</span>
                    </div>
                </div>
            </div>

            <div class="col-12 col-lg-6">
                <div class="frappe-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <span class="fs-4">📦</span>
                            <div>
                                <h3 class="h6 fw-bold mb-0">Warehouse Operator Workspace</h3>
                                <div class="text-secondary small">Picking lists, barcode verification & dispatch</div>
                            </div>
                        </div>
                        <a href="/app/warehouse-operations" class="btn btn-sm btn-outline-dark">Open &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Streamlines warehouse fulfillment. Operators verify SKUs with barcode scanning, confirm package counts, and hand off consignments to shipping carriers.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Warehouse Operator</span>
                        <span class="badge bg-light text-dark border">Consumes: ERPNext Pick List, Delivery Note, Stock</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="frappe-card p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3 class="h6 fw-bold mb-0">Core ERPNext Workspaces Available on this Server</h3>
                <span class="badge bg-success-subtle text-success">Same Dashboard</span>
            </div>
            <div class="row g-2">
                <div class="col-12 col-md-4">
                    <a href="/app/selling" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>🛒 ERPNext Selling</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
                <div class="col-12 col-md-4">
                    <a href="/app/stock" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>🏷️ ERPNext Stock</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
                <div class="col-12 col-md-4">
                    <a href="/app/buying" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>🏭 ERPNext Buying</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
                <div class="col-12 col-md-4">
                    <a href="/app/accounting" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>💰 ERPNext Accounting</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
                <div class="col-12 col-md-4">
                    <a href="/app/crm" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>🤝 ERPNext CRM</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
                <div class="col-12 col-md-4">
                    <a href="/app/settings" class="frappe-shortcut-btn text-decoration-none d-flex justify-content-between align-items-center">
                        <span>⚙️ Settings & Users</span>
                        <span class="text-secondary">&rarr;</span>
                    </a>
                </div>
            </div>
        </div>
        """

    # Sidebar active classes
    act_cl_home = "active" if active_workspace in ["clothing-erp", "overview", "app"] and not doctype else ""
    act_cl_sales = "active" if active_workspace in ["salesperson-portal", "salesperson"] else ""
    act_cl_wh = "active" if active_workspace in ["warehouse-operations", "warehouse"] else ""

    act_erp_selling = "active" if active_workspace == "selling" or doctype in ["Customer", "Sales Order"] else ""
    act_erp_stock = "active" if active_workspace == "stock" or doctype in ["Item", "Pick List", "Warehouse", "Delivery Note"] else ""
    act_erp_buying = "active" if active_workspace == "buying" or doctype == "Supplier" else ""
    act_erp_acct = "active" if active_workspace == "accounting" else ""
    act_erp_crm = "active" if active_workspace == "crm" else ""
    act_erp_set = "active" if active_workspace == "settings" or doctype == "User" else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ws_title} — Frappe Desk</title>
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
        .frappe-brand {{
            font-weight: 700;
            font-size: 14px;
            color: #111827;
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
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
            width: 240px;
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
            padding: 8px 12px 4px;
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
            <a href="/app" class="frappe-brand">
                <span class="rounded bg-dark text-white p-1 px-2" style="font-size: 11px; font-weight: 800;">E</span>
                <span>ERPNext</span>
                <span class="badge bg-secondary-subtle text-secondary small" style="font-size: 10px;">Desk</span>
            </a>

            <div class="frappe-search-box d-none d-md-flex">
                <span>🔍 Search or type a command</span>
                <span class="kbd-hint">Ctrl + G</span>
            </div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <!-- Perspective Role Switcher -->
            <div class="dropdown">
                <button class="btn btn-sm dropdown-toggle py-1 px-2" style="{role_badge_style} font-size: 11.5px; font-weight: 600;" type="button" data-bs-toggle="dropdown">
                    <span>Role: <strong>{active_role}</strong></span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                    <li><h6 class="dropdown-header text-uppercase small" style="font-size: 10px;">Switch User Perspective</h6></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Administrator')">👑 Administrator (Full Desk)</a></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Salesperson')">🛍️ Clothing Salesperson</a></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Warehouse Operator')">📦 Clothing Warehouse Operator</a></li>
                </ul>
            </div>

            <span class="text-secondary" style="font-size: 16px; cursor: pointer;" title="Notifications">🔔</span>
            <span class="text-secondary" style="font-size: 16px; cursor: pointer;" title="Help">❔</span>

            <div class="d-flex align-items-center gap-2">
                <div class="user-avatar" title="Administrator">AD</div>
                <span class="d-none d-lg-inline small fw-semibold text-secondary">Avi</span>
            </div>
        </div>
    </header>

    <div class="d-flex">
        <!-- Left Desk Sidebar hosting all 3 Apps -->
        <aside class="frappe-sidebar d-none d-md-flex">
            <!-- App 1: Custom Clothing ERP -->
            <div class="sidebar-section-title text-primary">👕 Clothing ERP (Custom App)</div>
            <a href="/app" class="sidebar-nav-item {act_cl_home}">
                <span>🏠</span> Clothing ERP Home
            </a>
            <a href="/app/salesperson-portal" class="sidebar-nav-item {act_cl_sales}">
                <span>🛍️</span> Salesperson Portal
            </a>
            <a href="/app/warehouse-operations" class="sidebar-nav-item {act_cl_wh}">
                <span>📦</span> Warehouse Operations
            </a>

            <!-- App 2: Standard ERPNext Core -->
            <div class="sidebar-section-title mt-3">📦 ERPNext Core Modules</div>
            <a href="/app/stock" class="sidebar-nav-item {act_erp_stock}">
                <span>🏷️</span> Stock & Catalog
            </a>
            <a href="/app/selling" class="sidebar-nav-item {act_erp_selling}">
                <span>🛒</span> Selling & Orders
            </a>
            <a href="/app/buying" class="sidebar-nav-item {act_erp_buying}">
                <span>🏭</span> Buying & Suppliers
            </a>
            <a href="/app/accounting" class="sidebar-nav-item {act_erp_acct}">
                <span>💰</span> Accounting & Invoices
            </a>
            <a href="/app/crm" class="sidebar-nav-item {act_erp_crm}">
                <span>🤝</span> CRM & Retailers
            </a>

            <!-- App 3: Frappe Framework -->
            <div class="sidebar-section-title mt-3">⚡ Frappe Framework</div>
            <a href="/app/settings" class="sidebar-nav-item {act_erp_set}">
                <span>⚙️</span> Users & Permissions
            </a>

            <div class="mt-auto pt-3 border-top small text-muted px-2">
                <div><strong>ERPNext + Clothing ERP</strong></div>
                <div style="font-size: 11px;">Single Site Dashboard &bull; Port {PORT}</div>
            </div>
        </aside>

        <!-- Main Desk Workspace Canvas -->
        <main class="flex-grow-1 p-4" style="min-height: calc(100vh - 48px); max-width: 1300px;">
            <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center pb-3 mb-4 border-bottom gap-2">
                <div>
                    <div class="text-secondary small mb-1">{breadcrumbs}</div>
                    <h1 class="h4 fw-bold text-dark mb-0">{ws_title}</h1>
                    <div class="text-secondary small">{ws_subtitle}</div>
                </div>
                <div class="d-flex align-items-center">
                    {action_buttons}
                </div>
            </div>

            {body_content}
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
                    location.href = '/app/salesperson-portal';
                }} else if (role === 'Warehouse Operator') {{
                    location.href = '/app/warehouse-operations';
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


class UnifiedDeskHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Root lands directly into the Frappe Desk Dashboard
        if path in ["/", "/clothing", "/clothing-erp", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="clothing-erp").encode("utf-8"))

        elif path in ["/app", "/app/"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="clothing-erp").encode("utf-8"))

        # Workspace Views
        elif path in ["/app/salesperson-portal", "/app/salesperson", "/salesperson"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="salesperson-portal", active_role="Salesperson").encode("utf-8"))

        elif path in ["/app/warehouse-operations", "/app/warehouse", "/warehouse"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="warehouse-operations", active_role="Warehouse Operator").encode("utf-8"))

        elif path == "/app/stock":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="stock").encode("utf-8"))

        elif path == "/app/selling":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="selling").encode("utf-8"))

        elif path == "/app/buying":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="buying").encode("utf-8"))

        elif path == "/app/accounting":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="accounting").encode("utf-8"))

        elif path == "/app/crm":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="crm").encode("utf-8"))

        elif path == "/app/settings":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace="settings").encode("utf-8"))

        # DocType Views inside Desk
        elif path.startswith("/app/"):
            sub = path.replace("/app/", "").strip("/")
            doctype_match = None
            for k in DB:
                if k.lower() == sub.lower().replace("-", " "):
                    doctype_match = k
                    break

            ws = "stock" if doctype_match in ["Item", "Pick List", "Warehouse", "Delivery Note"] else ("selling" if doctype_match in ["Customer", "Sales Order"] else "clothing-erp")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_frappe_desk(active_workspace=ws, doctype=doctype_match).encode("utf-8"))

        # REST APIs
        elif path.startswith("/api/resource/"):
            parts = path.replace("/api/resource/", "").split("/")
            doctype = parts[0].replace("-", " ").replace("%20", " ").title()
            match = next((k for k in DB if k.lower() == doctype.lower()), None)
            if match:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": DB[match]}, indent=2).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"DocType '{doctype}' not found"}).encode("utf-8"))

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
                "server": "Unified Frappe Desk Server",
                "installed_apps": [
                    {"name": "clothing_erp", "version": "0.1.0", "title": "Clothing ERP"},
                    {"name": "erpnext", "version": "16.54.0", "title": "ERPNext"},
                    {"name": "frappe", "version": "16.55.2", "title": "Frappe Framework"},
                ],
                "active_workspaces": [
                    "Clothing ERP",
                    "Salesperson Portal",
                    "Warehouse Operations",
                    "Stock",
                    "Selling",
                    "Buying",
                    "Accounting",
                    "CRM",
                    "Settings",
                ],
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
        sys.stderr.write(f"[Frappe Desk Server] {self.address_string()} - {format % args}\n")


def run():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), UnifiedDeskHandler) as httpd:
        print(f"[Frappe Desk] Unified server running on http://127.0.0.1:{PORT}")
        print(f"[Frappe Desk] Hosting Frappe Framework, ERPNext, and Clothing ERP together on the same dashboard.")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run()
