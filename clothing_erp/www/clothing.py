"""Front door for the native authenticated Frappe app launcher."""
import frappe
no_cache = 1

def get_context(context):
    frappe.local.flags.redirect_location = (
        "/login?redirect-to=%2Fdesk%2Fdesktop" if frappe.session.user == "Guest" else "/desk/desktop"
    )
    raise frappe.Redirect
