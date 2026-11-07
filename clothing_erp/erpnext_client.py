"""ERPNext Client Connector for Clothing ERP.

Fetches data strictly from the independent ERPNext server running on port 8001.
Clothing ERP does not recreate ERPNext data structures; it consumes standard
ERPNext REST resources (Items, Customers, Sales Orders, Pick Lists, Warehouses).
"""

import json
import os
import urllib.error
import urllib.request

ERPNEXT_SERVER_URL = os.environ.get("ERPNEXT_SERVER_URL", "http://127.0.0.1:8001")


def _get(endpoint):
    """Execute GET request to ERPNext server."""
    url = f"{ERPNEXT_SERVER_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return {"error": str(e), "data": []}


def _post(endpoint, payload):
    """Execute POST request to ERPNext server."""
    url = f"{ERPNEXT_SERVER_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return {"error": str(e)}


def check_erpnext_server():
    """Verify if the independent ERPNext server is online."""
    res = _get("/api/method/erpnext.get_status")
    return res.get("status") == "online"


def get_erpnext_catalog():
    """Fetch ERPNext App Catalogue and active Workspaces."""
    return _get("/api/method/erpnext.get_catalog")


def get_items(filters=None):
    """Fetch garments and items from ERPNext Item master."""
    res = _get("/api/resource/Item")
    return res.get("data", [])


def get_customers():
    """Fetch retail shops and customer accounts from ERPNext Customer master."""
    res = _get("/api/resource/Customer")
    return res.get("data", [])


def get_sales_orders():
    """Fetch wholesale sales orders from ERPNext Sales Order."""
    res = _get("/api/resource/Sales Order")
    return res.get("data", [])


def get_pick_lists():
    """Fetch warehouse pick lists from ERPNext Pick List."""
    res = _get("/api/resource/Pick List")
    return res.get("data", [])


def get_delivery_notes():
    """Fetch dispatches from ERPNext Delivery Note."""
    res = _get("/api/resource/Delivery Note")
    return res.get("data", [])


def get_warehouses():
    """Fetch warehouses from ERPNext Warehouse master."""
    res = _get("/api/resource/Warehouse")
    return res.get("data", [])


def create_customer(customer_data):
    """Submit a newly approved retailer into ERPNext Customer doctype."""
    return _post("/api/resource/Customer", customer_data)


def create_sales_order(order_data):
    """Submit a confirmed wholesale order into ERPNext Sales Order doctype."""
    return _post("/api/resource/Sales Order", order_data)
