# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class QualityInspectionReadingItem(Document):
    def validate(self):
        target = flt(self.spec_target)
        actual = flt(self.actual_reading)
        tol_plus = flt(self.tolerance_plus)
        tol_minus = flt(self.tolerance_minus)

        self.variance = round(actual - target, 4)

        upper_bound = target + tol_plus
        lower_bound = target - tol_minus

        if actual > upper_bound or actual < lower_bound:
            self.reading_status = "Out of Spec"
        else:
            self.reading_status = "In Spec"
