"""Create a fresh site without putting generated passwords in command arguments."""
import os
import frappe
from frappe.installer import _new_site

os.chdir("/home/frappe/frappe-bench/sites")
site = "clothing.local"
frappe.init(site, new_site=True)
try:
    _new_site(
        None, site,
        db_type="mariadb",
        db_root_username="clothing_installer",
        db_root_password=os.environ["FRAPPE_DB_ROOT_PASSWORD"],
        admin_password=os.environ["FRAPPE_ADMIN_PASSWORD"],
        mariadb_user_host_login_scope="localhost",
    )
finally:
    frappe.destroy()
