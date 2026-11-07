#!/usr/bin/env python3
"""Standalone HTTP server for Clothing ERP portal preview.

Serves the Clothing ERP homepage with all 7 navigation placeholders
(Admin, Products, Sales, Retailers, Warehouse, Suppliers, Reports)
and interactive Desk view placeholders.
"""

import http.server
import json
import os
import socketserver
import sys
from urllib.parse import urlparse

# Ensure local clothing_erp package is importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from clothing_erp.www.clothing import get_navigation_items, get_context

PORT = 8000

ICONS = {
    "admin": "🛡️",
    "products": "🏷️",
    "sales": "🛒",
    "retailers": "🏬",
    "warehouse": "📦",
    "suppliers": "🏭",
    "reports": "📊",
}


def render_homepage():
    context = {}
    get_context(context)
    items = context.get("navigation_items", get_navigation_items())

    items_html = ""
    for item in items:
        icon = ICONS.get(item["id"], "📌")
        items_html += f"""
        <div class="col-12 col-md-6 col-lg-4 mb-4">
            <div class="card h-100 shadow-sm border-0 rounded-3 module-card">
                <div class="card-body p-4 d-flex flex-column">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div class="module-icon fs-2 p-2 bg-light rounded-3">{icon}</div>
                        <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1">{item.get('badge', 'Module')}</span>
                    </div>
                    <h3 class="h5 fw-bold text-dark mb-2">{item['label']}</h3>
                    <p class="text-secondary small mb-4 flex-grow-1">{item['description']}</p>
                    <div class="pt-3 border-top d-flex justify-content-between align-items-center">
                        <span class="badge bg-secondary-subtle text-secondary">{item['doctype']}</span>
                        <a href="{item['url']}" class="btn btn-sm btn-outline-primary fw-semibold px-3">
                            Enter {item['label']} &rarr;
                        </a>
                    </div>
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clothing ERP — Distribution Portal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{
            background-color: #f8fafc;
            color: #1e293b;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .clothing-hero {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            border-radius: 16px;
            padding: 3.5rem 2rem;
            margin-bottom: 2.5rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
        }}
        .module-card {{
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            background: #ffffff;
            border: 1px solid #e2e8f0 !important;
        }}
        .module-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 16px 24px -6px rgba(0, 0, 0, 0.08) !important;
            border-color: #94a3b8 !important;
        }}
        .navbar-brand-badge {{
            font-size: 0.75rem;
            vertical-align: middle;
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-3">
        <div class="container">
            <a class="navbar-brand fw-bold d-flex align-items-center gap-2" href="/">
                <span class="fs-4">👕</span>
                <span>Clothing ERP</span>
                <span class="badge bg-primary navbar-brand-badge ms-2">Stage 1 Foundation</span>
            </a>
            <div class="d-flex align-items-center gap-2">
                <a href="/app" class="btn btn-outline-light btn-sm fw-semibold">Open Desk</a>
                <span class="text-white-50 small ms-2">Port: 8000</span>
            </div>
        </div>
    </nav>

    <main class="container py-4">
        <!-- Hero Section -->
        <div class="clothing-hero text-center">
            <span class="badge bg-primary text-white px-3 py-2 rounded-pill mb-3 fw-semibold">Stage 1: Development Environment & Foundation</span>
            <h1 class="display-5 fw-bold mb-3">Clothing ERP Portal</h1>
            <p class="lead text-light opacity-90 mx-auto mb-4" style="max-width: 680px;">
                Open-source apparel distribution and wholesale supply chain platform powered by Frappe Framework & ERPNext.
            </p>
            <div class="d-flex justify-content-center gap-3">
                <a href="/app" class="btn btn-primary px-4 py-2 fw-semibold shadow">Go to Desk View</a>
                <a href="/api/method/clothing_erp.get_status" class="btn btn-outline-light px-4 py-2 fw-semibold">API Health Status</a>
            </div>
        </div>

        <!-- Section Header -->
        <div class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom">
            <div>
                <h2 class="h4 fw-bold text-dark mb-1">Operational Workspaces</h2>
                <p class="text-secondary small mb-0">Core navigation placeholders for apparel wholesale, inventory, and partner management</p>
            </div>
            <span class="badge bg-secondary-subtle text-secondary px-3 py-2 fs-6">7 Modules Active</span>
        </div>

        <!-- Navigation Grid -->
        <div class="row">
            {items_html}
        </div>

        <!-- Stage Architecture Box -->
        <div class="alert alert-info border-0 shadow-sm d-flex align-items-center p-4 mt-3 rounded-3" role="alert">
            <div class="fs-2 me-3">ℹ️</div>
            <div>
                <h3 class="h6 fw-bold mb-1">Stage 1 Architecture Rules Enforced</h3>
                <p class="small mb-0 text-secondary">
                    All custom functionality resides strictly in the independent <code>clothing_erp</code> application.
                    Upstream ERPNext and Frappe core code remain untouched. Business modules (products, sales, warehouse logic) will be implemented in subsequent stages.
                </p>
            </div>
        </div>
    </main>

    <footer class="container py-4 mt-4 border-top text-center text-secondary small">
        <p class="mb-1">Clothing ERP &bull; Custom Frappe App &bull; Target Version: Frappe & ERPNext v16</p>
        <p class="text-muted">Repository: <code>clothing_erp</code> on branch <code>main</code></p>
    </footer>
</body>
</html>
"""


def render_desk_page(path):
    subpath = path.replace("/app/", "")
    title = subpath.replace("-", " ").title() if subpath else "Desk Overview"
    icon = ICONS.get(subpath.replace("item", "products").replace("customer", "retailers").replace("sales-order", "sales").replace("stock-entry", "warehouse").replace("supplier", "suppliers").replace("query-report", "reports").replace("user", "admin"), "📁")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Clothing ERP Desk</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        .sidebar {{ width: 240px; background: #ffffff; border-right: 1px solid #e2e8f0; min-height: 100vh; }}
        .desk-nav a {{ color: #475569; text-decoration: none; padding: 0.6rem 1rem; border-radius: 6px; display: flex; align-items: center; gap: 0.5rem; }}
        .desk-nav a:hover, .desk-nav a.active {{ background-color: #f1f5f9; color: #0284c7; font-weight: 600; }}
    </style>
</head>
<body class="d-flex">
    <!-- Sidebar -->
    <aside class="sidebar p-3 d-flex flex-column">
        <a href="/" class="d-flex align-items-center gap-2 mb-4 text-decoration-none text-dark fw-bold fs-5">
            <span>👕</span>
            <span>Clothing ERP</span>
        </a>
        <div class="text-uppercase small fw-bold text-muted px-2 mb-2">Workspaces</div>
        <nav class="desk-nav d-flex flex-column gap-1">
            <a href="/app" class="{'active' if not subpath else ''}">🏠 Overview</a>
            <a href="/app/user" class="{'active' if subpath == 'user' else ''}">🛡️ Admin</a>
            <a href="/app/item" class="{'active' if subpath == 'item' else ''}">🏷️ Products (Item)</a>
            <a href="/app/sales-order" class="{'active' if subpath == 'sales-order' else ''}">🛒 Sales (Orders)</a>
            <a href="/app/customer" class="{'active' if subpath == 'customer' else ''}">🏬 Retailers (Customer)</a>
            <a href="/app/stock-entry" class="{'active' if subpath == 'stock-entry' else ''}">📦 Warehouse (Stock)</a>
            <a href="/app/supplier" class="{'active' if subpath == 'supplier' else ''}">🏭 Suppliers</a>
            <a href="/app/query-report" class="{'active' if subpath == 'query-report' else ''}">📊 Reports</a>
        </nav>
        <div class="mt-auto pt-3 border-top small text-muted">
            <a href="/" class="btn btn-sm btn-outline-secondary w-100">&larr; Back to Portal</a>
        </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-grow-1 p-5">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1 class="h3 fw-bold text-dark mb-1">{icon} {title} Workspace</h1>
                    <p class="text-secondary small mb-0">Module route: <code>{path}</code> &bull; Upstream DocType mapping</p>
                </div>
                <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2">Stage 1 Placeholder Active</span>
            </div>

            <div class="card shadow-sm border-0 rounded-3 mb-4">
                <div class="card-body p-4">
                    <h2 class="h5 fw-bold text-dark mb-2">Operational Module Foundation</h2>
                    <p class="text-secondary mb-3">
                        This view confirms the navigation hook and route registration for <strong>{title}</strong>.
                        Per Stage 1 rules, business logic and data schema will be populated in subsequent stages without modifying upstream core code.
                    </p>
                    <div class="p-3 bg-light rounded-2 font-monospace small">
                        <div><strong>App:</strong> clothing_erp v0.1.0</div>
                        <div><strong>DocType Mapping:</strong> {subpath.capitalize() if subpath else 'Workspace'}</div>
                        <div><strong>Access Control:</strong> System Manager, Clothing ERP User</div>
                    </div>
                </div>
            </div>
        </div>
    </main>
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

        if path in ["/", "/clothing", "/clothing-erp", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_homepage().encode("utf-8"))

        elif path.startswith("/app"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_desk_page(path).encode("utf-8"))

        elif path == "/api/method/clothing_erp.get_status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "status": "online",
                "app": "clothing_erp",
                "version": "0.1.0",
                "stage": "Stage 1: Development Environment and Custom App Foundation",
                "modules": [item["id"] for item in get_navigation_items()],
                "upstream_erpnext_modified": False,
            }
            self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def log_message(self, format, *args):
        # Clean logging
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
