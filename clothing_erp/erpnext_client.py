"""Native ERPNext queries under the current Frappe session's permissions."""
import frappe

def get_items(filters=None):
    return frappe.get_list("Item", filters=filters or {}, fields=["name", "item_name", "item_group", "image"], limit=50)

def get_customers():
    return frappe.get_list("Customer", fields=["name", "customer_name"], limit=50)

def get_sales_orders():
    return frappe.get_list("Sales Order", fields=["name", "customer", "transaction_date", "total_qty", "grand_total", "status"], order_by="modified desc", limit=20)

def get_pick_lists():
    return frappe.get_list("Pick List", fields=["name", "customer", "status"], order_by="modified desc", limit=20)

def get_delivery_notes():
    return frappe.get_list("Delivery Note", fields=["name", "customer", "status"], order_by="modified desc", limit=20)

def get_warehouses():
    return frappe.get_list("Warehouse", fields=["name", "warehouse_name"], limit=50)
