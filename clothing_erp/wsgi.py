"""Single-site entry points for IP access without trusting an incoming site header."""
import os
from frappe.app import application as frappe_application, application_with_statics


def _single_site(handler):
    def application(environ, start_response):
        environ["HTTP_X_FRAPPE_SITE_NAME"] = os.environ.get("FRAPPE_SITE", "clothing.local")
        return handler(environ, start_response)
    return application


application = _single_site(frappe_application)
def create_development_application():
    return _single_site(application_with_statics())
