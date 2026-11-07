#!/usr/bin/env python3
"""Clothing ERP — ERPNext-Identical Desk & Portal Preview Server (Stage 2).

Provides the exact Frappe/ERPNext Desk UI/UX on http://localhost:8000:
- Top Frappe Navbar with App Switcher (Clothing ERP, ERPNext, Frappe)
- Global Search bar (Ctrl + G) and User Avatar
- Left Desk Sidebar with Workspaces (Clothing ERP, Salesperson Portal, Warehouse Operations)
- Frappe Number Cards (KPIs), Shortcuts, and Quick Lists
- Live Role Perspective Switcher (Administrator, Salesperson, Warehouse Operator)
- Interactive APIs for user context, role switching, and operational dashboards.
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


def get_erpnext_desk_html(view="overview", active_role=None):
    """Generate exact ERPNext Desk HTML with Frappe design language and operational dashboards."""
    ctx = get_user_context()
    if not active_role:
        active_role = ctx["active_role"]

    sales_data = get_salesperson_dashboard()
    warehouse_data = get_warehouse_dashboard()

    # Determine visible workspaces based on role
    show_sales = active_role in ["Salesperson", "Sales Manager", "Administrator"]
    show_warehouse = active_role in ["Warehouse Operator", "Warehouse Manager", "Administrator"]
    show_admin = active_role in ["Administrator"]

    # Role badge colors
    role_badges = {
        "Administrator": "background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe;",
        "Salesperson": "background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;",
        "Warehouse Operator": "background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0;",
    }
    role_badge_style = role_badges.get(active_role, "background: #f3f4f6; color: #374151;")

    # Status badge styling helper
    def status_badge(status):
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

    # Build View-specific Content
    if view == "salesperson" or (view == "overview" and active_role == "Salesperson"):
        page_title = "Salesperson Portal"
        page_subtitle = "Operational workspace for wholesale garment sales, order placement, and retail accounts"
        breadcrumbs = "Home / Clothing ERP / Salesperson Portal"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="alert('Stage 4: Retailer Directory & Registration')">+ Register Retailer</button>
            <button class="btn btn-primary btn-sm" onclick="alert('Stage 5: Size-Colour Matrix Order Creation')">+ New Sales Order</button>
        """

        # Metrics HTML
        m = sales_data["metrics"]
        kpi_html = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TODAY'S ORDERS</div>
                    <div class="frappe-card-number">{m['today_orders_count']}</div>
                    <div class="frappe-card-sub text-success">↑ 14% vs yesterday &bull; ₹{m['today_orders_value']:,.0f}</div>
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
                    <div class="frappe-card-sub text-secondary">Active accounts in territory</div>
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

        # Orders Table HTML
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
                        <h2 class="h6 fw-bold mb-0">Recent Wholesale Orders</h2>
                        <a href="/app/sales-order" class="text-decoration-none small text-secondary">View All &rarr;</a>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb;">
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
                            <span>🏷️ Browse Garment Catalog</span>
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

    elif view == "warehouse" or (view == "overview" and active_role == "Warehouse Operator"):
        page_title = "Warehouse Operations"
        page_subtitle = "Operational workspace for picking, barcode verification, packing, and dispatch confirmation"
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
                    <div class="frappe-card-sub text-secondary">Active tasks assigned to you</div>
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
                    <div class="frappe-card-sub text-secondary">Packed with shipping labels</div>
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
                <td><button class="btn btn-sm btn-outline-dark py-0 px-2" style="font-size: 11px;" onclick="alert('Pick List: {p['pick_list']}')">Pick</button></td>
            </tr>
            """

        content_body = f"""
        {kpi_html}

        <div class="row g-4">
            <div class="col-12 col-lg-8">
                <div class="frappe-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="h6 fw-bold mb-0">Assigned Picking Tasks</h2>
                        <span class="badge bg-light text-dark border">Zone A &bull; Finished Goods</span>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr class="text-secondary small text-uppercase" style="border-bottom: 1px solid #e5e7eb;">
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
                            <button class="btn btn-sm btn-success w-100 mt-2 py-1" onclick="alert('Confirm dispatch for MAT-DN-2026-0019')">Confirm Dispatch &rarr;</button>
                        </div>
                        <div class="p-3 rounded" style="background: #f9fafb; border: 1px solid #e5e7eb;">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <span class="fw-bold small">MAT-DN-2026-0020</span>
                                {status_badge("Ready for Dispatch")}
                            </div>
                            <div class="text-secondary small">Retailer: Style Quotient</div>
                            <div class="text-secondary small">Carrier: Delhivery (2 boxes)</div>
                            <button class="btn btn-sm btn-success w-100 mt-2 py-1" onclick="alert('Confirm dispatch for MAT-DN-2026-0020')">Confirm Dispatch &rarr;</button>
                        </div>
                    </div>
                </div>

                <div class="frappe-card p-4">
                    <h2 class="h6 fw-bold mb-2">Barcode Scan Station</h2>
                    <p class="text-secondary small mb-3">Scan product hangtag or carton barcode to verify SKU.</p>
                    <div class="input-group mb-2">
                        <input type="text" class="form-control form-control-sm" placeholder="Scan SKU / Barcode..." id="barcode-input">
                        <button class="btn btn-dark btn-sm" onclick="alert('Scanned SKU: ' + (document.getElementById('barcode-input').value || 'TSH-BLK-M'))">Verify</button>
                    </div>
                    <div class="small text-muted">Supports EAN-13, Code-128 & QR.</div>
                </div>
            </div>
        </div>
        """

    else:
        # Default / Management Overview
        page_title = "Clothing ERP Overview"
        page_subtitle = "Unified management workspace for wholesale apparel supply chain and distribution"
        breadcrumbs = "Home / Clothing ERP / Overview"
        action_buttons = """
            <button class="btn btn-default btn-sm me-2" onclick="location.href='/app/salesperson'">Salesperson Portal</button>
            <button class="btn btn-primary btn-sm" onclick="location.href='/app/warehouse'">Warehouse Operations</button>
        """

        content_body = f"""
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">TODAY'S ORDERS</div>
                    <div class="frappe-card-number">{sales_data['metrics']['today_orders_count']}</div>
                    <div class="frappe-card-sub text-success">₹{sales_data['metrics']['today_orders_value']:,.0f} &bull; 8 wholesale orders</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">MONTHLY TURNOVER</div>
                    <div class="frappe-card-number">₹{sales_data['metrics']['month_sales_value']:,.0f}</div>
                    <div class="frappe-card-sub text-secondary">76% of monthly budget</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">PENDING PICKING</div>
                    <div class="frappe-card-number text-warning">{warehouse_data['metrics']['assigned_pick_lists']}</div>
                    <div class="frappe-card-sub text-secondary">Orders awaiting fulfillment</div>
                </div>
            </div>
            <div class="col-12 col-sm-6 col-lg-3">
                <div class="frappe-card p-3">
                    <div class="frappe-card-label">ACTIVE RETAILERS</div>
                    <div class="frappe-card-number text-primary">{sales_data['metrics']['assigned_retailers_count']}</div>
                    <div class="frappe-card-sub text-secondary">Boutiques and store networks</div>
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
                                <div class="text-secondary small">Mobile-first ordering & retailer visit tracking</div>
                            </div>
                        </div>
                        <a href="/app/salesperson" class="btn btn-sm btn-outline-dark">Open Portal &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Tailored for field sales representatives. Enables rapid catalog browsing, size-colour variant matrix ordering, customer-specific wholesale price lookup, and visit logging.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Salesperson</span>
                        <span class="badge bg-light text-dark border">DocTypes: Sales Order, Customer</span>
                        <span class="badge bg-light text-dark border">Stage 2 Foundation Ready</span>
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
                                <div class="text-secondary small">Task-driven picking, packing & barcode verification</div>
                            </div>
                        </div>
                        <a href="/app/warehouse" class="btn btn-sm btn-outline-dark">Open Operations &rarr;</a>
                    </div>
                    <p class="text-secondary small mb-3">
                        Tailored for warehouse and fulfillment staff. Streamlines picking list assignments, barcode scanning, carton packaging verification, and dispatch handoff to carriers.
                    </p>
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-light text-dark border">Role: Clothing Warehouse Operator</span>
                        <span class="badge bg-light text-dark border">DocTypes: Pick List, Delivery Note</span>
                        <span class="badge bg-light text-dark border">Stage 2 Foundation Ready</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="alert alert-light border shadow-sm p-4 mt-4 rounded-3 d-flex align-items-center">
            <div class="fs-2 me-3">🛡️</div>
            <div>
                <h4 class="h6 fw-bold mb-1">Architecture & Coexistence Rule</h4>
                <div class="text-secondary small">
                    This custom app (<code>clothing_erp</code>) runs seamlessly on the same site and IP alongside standard ERPNext.
                    Management can use standard ERPNext Desk without modification, while operational staff access their dedicated, high-speed interfaces.
                </div>
            </div>
        </div>
        """

    active_overview = "active" if view == "overview" else ""
    active_sales = "active" if view == "salesperson" else ""
    active_warehouse = "active" if view == "warehouse" else ""

    sales_nav_item = f'<a href="/app/salesperson" class="sidebar-nav-item {active_sales}"><span>🛍️</span> Salesperson Portal</a>' if show_sales else ''
    warehouse_nav_item = f'<a href="/app/warehouse" class="sidebar-nav-item {active_warehouse}"><span>📦</span> Warehouse Operations</a>' if show_warehouse else ''

    # Assemble complete ERPNext-identical Desk layout
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title} — ERPNext Desk &bull; Clothing ERP</title>
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
        /* Top Frappe Navbar */
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
        /* Left Desk Sidebar */
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
        /* Desk Cards and KPIs */
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
    <!-- Top Frappe Navbar -->
    <header class="frappe-navbar">
        <div class="d-flex align-items-center gap-3">
            <div class="dropdown">
                <button class="app-switcher-btn dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    <span style="font-size: 14px;">👕</span>
                    <span>Clothing ERP</span>
                </button>
                <ul class="dropdown-menu shadow-sm">
                    <li><h6 class="dropdown-header text-uppercase small" style="font-size: 10px;">Installed Apps (Same IP)</h6></li>
                    <li><a class="dropdown-item active fw-bold" href="/app">👕 Clothing ERP (v0.1.0)</a></li>
                    <li><a class="dropdown-item" href="/app/item">📦 ERPNext (v16.54.0)</a></li>
                    <li><a class="dropdown-item" href="/app/user">⚡ Frappe Framework (v16.55.2)</a></li>
                </ul>
            </div>

            <div class="frappe-search-box d-none d-md-flex">
                <span>🔍 Search or type a command</span>
                <span class="kbd-hint">Ctrl + G</span>
            </div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <!-- Perspective Role Switcher (Allows live testing of Stage 2 Roles) -->
            <div class="dropdown">
                <button class="btn btn-sm dropdown-toggle py-1 px-2" style="{role_badge_style} font-size: 11.5px; font-weight: 600;" type="button" data-bs-toggle="dropdown">
                    <span>Perspective: <strong>{active_role}</strong></span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                    <li><h6 class="dropdown-header text-uppercase small" style="font-size: 10px;">Switch Test Role (Stage 2)</h6></li>
                    <li><a class="dropdown-item" href="javascript:void(0)" onclick="switchRole('Administrator')">👑 Administrator / Management</a></li>
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
        <!-- Left Desk Sidebar -->
        <aside class="frappe-sidebar d-none d-md-flex">
            <div class="sidebar-section-title">Operational Workspaces</div>
            <a href="/app" class="sidebar-nav-item {active_overview}">
                <span>🏠</span> Overview
            </a>
            {sales_nav_item}
            {warehouse_nav_item}

            <div class="sidebar-section-title mt-3">ERPNext Core Modules</div>
            <a href="/app/item" class="sidebar-nav-item {'active' if view == 'item' else ''}">
                <span>🏷️</span> Item (Catalog)
            </a>
            <a href="/app/sales-order" class="sidebar-nav-item {'active' if view == 'sales-order' else ''}">
                <span>🛒</span> Sales Order
            </a>
            <a href="/app/customer" class="sidebar-nav-item {'active' if view == 'customer' else ''}">
                <span>🏬</span> Customer (Retailers)
            </a>
            <a href="/app/stock-entry" class="sidebar-nav-item {'active' if view == 'stock-entry' else ''}">
                <span>🏭</span> Stock Movements
            </a>
            <a href="/app/supplier" class="sidebar-nav-item {'active' if view == 'supplier' else ''}">
                <span>🚚</span> Suppliers
            </a>
            <a href="/app/query-report" class="sidebar-nav-item {'active' if view == 'query-report' else ''}">
                <span>📊</span> Reports
            </a>

            <div class="mt-auto pt-3 border-top small text-muted px-2">
                <div><strong>Clothing ERP</strong></div>
                <div style="font-size: 11px;">Stage 2 &bull; Same IP Host</div>
            </div>
        </aside>

        <!-- Main Desk Canvas -->
        <main class="flex-grow-1 p-4" style="min-height: calc(100vh - 48px); max-width: 1300px;">
            <!-- Page Header -->
            <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center pb-3 mb-4 border-bottom gap-2">
                <div>
                    <div class="text-secondary small mb-1">{breadcrumbs}</div>
                    <h1 class="h4 fw-bold text-dark mb-0">{page_title}</h1>
                    <div class="text-secondary small">{page_subtitle}</div>
                </div>
                <div class="d-flex align-items-center">
                    {action_buttons}
                </div>
            </div>

            <!-- Page Body Content -->
            {content_body}
        </main>
    </div>

    <!-- Bootstrap Bundle JS -->
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


class ClothingERPRequestHandler(http.server.BaseHTTPRequestHandler):
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
            self.wfile.write(get_erpnext_desk_html(view="overview").encode("utf-8"))

        elif path in ["/app", "/app/"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_erpnext_desk_html(view="overview").encode("utf-8"))

        elif path in ["/app/salesperson", "/salesperson"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_erpnext_desk_html(view="salesperson", active_role="Salesperson").encode("utf-8"))

        elif path in ["/app/warehouse", "/warehouse"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_erpnext_desk_html(view="warehouse", active_role="Warehouse Operator").encode("utf-8"))

        elif path.startswith("/app/"):
            subview = path.replace("/app/", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_erpnext_desk_html(view=subview).encode("utf-8"))

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
                "stage": "Stage 2: Roles and Operational Interface Foundation",
                "roles": [
                    ROLE_SALESPERSON,
                    ROLE_WAREHOUSE_OPERATOR,
                    ROLE_SALES_MANAGER,
                    ROLE_WAREHOUSE_MANAGER,
                    ROLE_BUSINESS_ADMIN,
                ],
                "active_workspaces": ["Clothing ERP", "Salesperson Portal", "Warehouse Operations"],
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
        sys.stderr.write(f"[Clothing ERP Server] {self.address_string()} - {format % args}\n")


def run():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), ClothingERPRequestHandler) as httpd:
        print(f"[Clothing ERP] Server running on http://localhost:{PORT}")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run()
