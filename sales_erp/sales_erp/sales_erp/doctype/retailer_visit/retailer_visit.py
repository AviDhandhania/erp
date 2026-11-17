"""Retailer Visit controller and supervisory review service."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.security import (
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)
from sales_erp.supervision import (
    assert_rsm_supervises_asm,
    get_active_supervising_rsm,
    get_territory_supervision,
)

EVIDENCE_FIELDS = (
    "customer",
    "salesperson",
    "rsm",
    "visit_date",
    "visit_type",
    "visitor_role",
    "outcome",
    "notes",
    "follow_up_date",
    "financial_assessment",
    "customer_footfall",
    "stock_condition",
    "dealer_feedback",
    "checkin_latitude",
    "checkin_longitude",
    "checkin_accuracy_meters",
    "checkin_timestamp",
    "checkin_status",
    "checkin_consent",
    "evidence_photo",
    "evidence_caption",
)


class RetailerVisit(Document):
    def validate(self):
        user = get_current_user()
        roles = get_user_roles()
        admin = is_clothing_admin(user)

        # 1. Retailer Access Check
        if not admin and not has_retailer_access(self.customer, user):
            frappe.throw(_("You do not have access to this retailer."), frappe.PermissionError)

        # 2. Immutability of Evidence & Review Fields for Existing Documents
        if not self.is_new():
            stored = frappe.db.get_value(
                "Retailer Visit",
                self.name,
                [
                    "customer",
                    "salesperson",
                    "rsm",
                    "visit_date",
                    "visit_type",
                    "visitor_role",
                    "outcome",
                    "notes",
                    "follow_up_date",
                    "financial_assessment",
                    "customer_footfall",
                    "stock_condition",
                    "dealer_feedback",
                    "review_status",
                    "reviewed_by",
                    "reviewed_on",
                    "review_notes",
                ],
                as_dict=True,
            )
            if stored:
                # ASM cannot edit submitted reports
                if ROLE_SALESPERSON in roles and not is_sales_manager(user) and not admin:
                    frappe.throw(
                        _("Area Sales Managers cannot edit submitted visit reports."),
                        frappe.PermissionError,
                    )

                # Evidence immutability: once submitted or reviewed, original visit evidence cannot be altered
                if not getattr(self.flags, "in_review_service", False):
                    for field in EVIDENCE_FIELDS:
                        old_val = stored.get(field)
                        new_val = getattr(self, field, None)
                        # Normalize datetimes/dates for comparison if needed
                        if field in ("visit_date", "follow_up_date"):
                            old_str = str(getdate(old_val)) if old_val else ""
                            new_str = str(getdate(new_val)) if new_val else ""
                            if old_str != new_str:
                                frappe.throw(
                                    _("Visit evidence field '{0}' is immutable once submitted.").format(field),
                                    frappe.PermissionError,
                                )
                        elif field == "customer_footfall":
                            if cint(old_val) != cint(new_val):
                                frappe.throw(
                                    _("Visit evidence field '{0}' is immutable once submitted.").format(field),
                                    frappe.PermissionError,
                                )
                        else:
                            if (old_val or "") != (new_val or ""):
                                frappe.throw(
                                    _("Visit evidence field '{0}' is immutable once submitted.").format(field),
                                    frappe.PermissionError,
                                )

                    # Non-review services cannot alter review status
                    if stored.review_status != self.review_status:
                        frappe.throw(
                            _("Review status can only be modified through the authorized review service."),
                            frappe.PermissionError,
                        )

        # 3. ASM vs RSM Identity and Visit Type Scoping
        if ROLE_SALESPERSON in roles and not is_sales_manager(user) and not admin:
            self.salesperson = user
            self.visitor_role = "Area Sales Manager"

            if self.visit_type == "RSM Periodic Review":
                frappe.throw(
                    _("Area Sales Managers cannot file an RSM Periodic Review."),
                    frappe.PermissionError,
                )

            # Auto-populate supervising RSM from active ASM Supervision
            supervising_rsm = get_active_supervising_rsm(self.salesperson)
            if supervising_rsm:
                self.rsm = supervising_rsm
            else:
                customer_territory = frappe.db.get_value("Customer", self.customer, "territory")
                if customer_territory:
                    supervision = get_territory_supervision(customer_territory)
                    if supervision and supervision.rsm:
                        self.rsm = supervision.rsm

            if not self.review_status:
                self.review_status = "Submitted"

        elif is_sales_manager(user) and not admin:
            # RSM visiting: visitor identity MUST be forced to logged-in assigned RSM
            self.salesperson = user
            self.visitor_role = "Regional Sales Manager"
            self.rsm = user
            if not self.review_status:
                self.review_status = "Submitted"

        # 4. Required RSM Assessment Fields for Periodic Review
        if self.visit_type == "RSM Periodic Review":
            if not self.financial_assessment:
                frappe.throw(_("Financial Assessment is required for an RSM Periodic Review."))
            if self.customer_footfall is None or cint(self.customer_footfall) < 0:
                frappe.throw(_("Daily Customer Footfall must be a valid non-negative number."))
            if not self.stock_condition:
                frappe.throw(_("Stock Condition is required for an RSM Periodic Review."))
            if not (self.dealer_feedback or "").strip():
                frappe.throw(_("Dealer Feedback is required for an RSM Periodic Review."))

        # 5. Follow-up Date Validations
        if self.outcome == "Follow-up Required" and not self.follow_up_date:
            frappe.throw(_("Follow-up Date is required for this outcome."))
        if self.follow_up_date and getdate(self.follow_up_date) < getdate(nowdate()):
            frappe.throw(_("Follow-up Date cannot be in the past."))

    def on_update(self):
        # Fulfill/close ASM visit obligation if this is an ASM visit
        if self.visitor_role == "Area Sales Manager":
            try:
                from sales_erp.cadence import close_asm_visit_obligation
                obligation_type = None
                if self.visit_type == "Stock Review":
                    obligation_type = "Quarterly Stock Review"
                elif self.visit_type == "General Visit":
                    obligation_type = "Monthly General Visit"
                elif self.visit_type == "Sample & Order Taking":
                    obligation_type = "Monthly Sample & Order"

                if obligation_type:
                    close_asm_visit_obligation(self.customer, visit_doc=self, obligation_type=obligation_type)
            except Exception:
                pass

        # Fulfill/close RSM visit obligation if this is a genuine qualifying RSM visit
        if (
            self.visitor_role == "Regional Sales Manager"
            and self.visit_type == "RSM Periodic Review"
            and self.rsm == self.salesperson
            and is_sales_manager(self.rsm)
        ):
            try:
                from sales_erp.cadence import close_rsm_visit_obligation
                close_rsm_visit_obligation(self.customer, self.rsm, qualifying_visit=self.name)
            except Exception:
                pass

            # If the RSM recommended a credit limit change, record a pending credit limit request
            if flt(self.recommended_credit_limit) > 0:
                from sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request import (
                    get_customer_current_credit_limit,
                )
                current_limit = get_customer_current_credit_limit(self.customer)
                if flt(self.recommended_credit_limit) != flt(current_limit):
                    if not frappe.db.exists(
                        "Retailer Credit Limit Request",
                        {"source_visit": self.name, "status": "Pending Approval"},
                    ):
                        req = frappe.get_doc(
                            {
                                "doctype": "Retailer Credit Limit Request",
                                "customer": self.customer,
                                "proposed_credit_limit": flt(self.recommended_credit_limit),
                                "source_visit": self.name,
                                "reason": f"Recommended in RSM visit {self.name}: {self.dealer_feedback or self.notes or 'Periodic review assessment'}",
                                "proposer": self.rsm,
                            }
                        )
                        req.flags.ignore_permissions = True
                        req.insert()


@frappe.whitelist(methods=["POST"])
def review_visit(name, status, notes=None):
    """Supervisory review of a Retailer Visit with row-locking and role separation."""
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    admin = is_clothing_admin(user)

    # Row-lock transition
    rows = frappe.db.sql(
        "SELECT name, review_status, salesperson, visitor_role, rsm FROM `tabRetailer Visit` WHERE name = %s FOR UPDATE",
        (name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Retailer Visit {0} does not exist.").format(name), frappe.DoesNotExistError)

    current = rows[0]

    # Separation of review roles:
    if current.visitor_role == "Regional Sales Manager":
        # Only Administrator can review visits performed by an RSM
        if not admin:
            frappe.throw(
                _("Only administrators can review visits performed by Regional Sales Managers."),
                frappe.PermissionError,
            )
        valid_statuses = {"Reviewed by Admin", "Action Required"}
        if status not in valid_statuses:
            frappe.throw(
                _("Invalid review status '{0}' for an RSM visit. Must be one of: {1}").format(
                    status, ", ".join(valid_statuses)
                ),
                frappe.ValidationError,
            )
    else:
        # Visit performed by ASM
        if not admin:
            assert_rsm_supervises_asm(user, current.salesperson)
        valid_statuses = {"Reviewed by RSM", "Reviewed by Admin", "Action Required"}
        if status not in valid_statuses:
            frappe.throw(
                _("Invalid review status '{0}'. Must be one of: {1}").format(
                    status, ", ".join(valid_statuses)
                ),
                frappe.ValidationError,
            )

    doc = frappe.get_doc("Retailer Visit", name)
    doc.flags.in_review_service = True
    doc.review_status = status
    doc.reviewed_by = user
    doc.reviewed_on = now_datetime()
    doc.review_notes = (notes or "").strip()
    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "review_status": doc.review_status,
        "reviewed_by": doc.reviewed_by,
        "reviewed_on": doc.reviewed_on,
        "review_notes": doc.review_notes,
    }


def _haversine_distance(lat1, lon1, lat2, lon2):
    import math
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@frappe.whitelist(methods=["POST"])
def record_visit_checkin(
    visit_name,
    latitude,
    longitude,
    accuracy_meters=None,
    timestamp=None,
    consent=True,
    device_id=None,
):
    """Record GPS check-in verification for a retailer visit."""
    from sales_erp.api_security import check_rate_limit, record_security_audit_event, validate_float, validate_string
    check_rate_limit("record_visit_checkin", limit=60, window_seconds=60)
    visit_name = validate_string(visit_name, "Visit Name", max_len=140, required=True)
    lat = validate_float(latitude, "Latitude", min_val=-90.0, max_val=90.0)
    lon = validate_float(longitude, "Longitude", min_val=-180.0, max_val=180.0)
    accuracy = validate_float(accuracy_meters, "Accuracy", min_val=0.0) if accuracy_meters is not None else None
    device_ref = validate_string(device_id, "Device ID", max_len=140) if device_id else None

    visit = frappe.get_doc("Retailer Visit", visit_name)
    visit.check_permission("write")

    user = get_current_user()
    if visit.salesperson != user and not is_clothing_admin(user) and not is_sales_manager(user):
        frappe.throw(_("Only the visiting sales manager can record check-in."), frappe.PermissionError)

    from sales_erp.settings import get_sales_settings
    cfg = get_sales_settings()
    tolerance = cfg.get("geolocation_tolerance_meters", 500)

    now = now_datetime()
    if timestamp:
        from frappe.utils import time_diff_in_seconds
        diff = time_diff_in_seconds(str(now), str(timestamp))
        if diff < -300:
            frappe.throw(_("Check-in timestamp cannot be in the future."), frappe.ValidationError)
        if diff > 86400:
            frappe.throw(_("Check-in timestamp has expired (older than 24 hours)."), frappe.ValidationError)

    checkin_status = "Verified"
    # Check customer coordinates if available
    cust_coords = frappe.db.get_value("Customer", visit.customer, ["latitude", "longitude"], as_dict=True) if frappe.db.has_column("Customer", "latitude") else None
    if cust_coords and cust_coords.latitude and cust_coords.longitude:
        dist = _haversine_distance(lat, lon, flt(cust_coords.latitude), flt(cust_coords.longitude))
        if dist > tolerance:
            checkin_status = "Out of Radius"

    visit.flags.in_review_service = True
    visit.db_set({
        "checkin_latitude": lat,
        "checkin_longitude": lon,
        "checkin_accuracy_meters": accuracy or 0.0,
        "checkin_timestamp": timestamp or now,
        "checkin_status": checkin_status,
        "checkin_consent": 1 if consent else 0,
        "checkin_device_id": device_ref,
    })

    record_security_audit_event(
        "Visit Check-in Verified",
        "Retailer Visit",
        visit.name,
        {"latitude": lat, "longitude": lon, "status": checkin_status},
    )

    return {
        "visit": visit.name,
        "checkin_status": checkin_status,
        "latitude": lat,
        "longitude": lon,
    }

