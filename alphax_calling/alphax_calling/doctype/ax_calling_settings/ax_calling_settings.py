import re

import frappe
from frappe import _
from frappe.model.document import Document

from alphax_calling.utils import normalize_phone

PREFIX = (("twilio_account_sid", "AC", "Account SID"), ("twilio_api_key_sid", "SK", "API key SID"),
          ("twilio_twiml_app_sid", "AP", "TwiML App SID"))


class AXCallingSettings(Document):
    def validate(self):
        cc = re.sub(r"\D", "", self.default_country_code or "") or "966"
        self.default_country_code = cc
        for f in ("call_window_start", "call_window_end"):
            if self.get(f) and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", self.get(f)):
                frappe.throw(_("Use HH:MM (24-hour) for the call window."))
        for field, prefix, label in PREFIX:
            v = (self.get(field) or "").strip()
            self.set(field, v)
            if v and not v.startswith(prefix):
                frappe.throw(_("{0} must start with {1}.").format(label, prefix))
        if self.twilio_caller_id:
            n = normalize_phone(self.twilio_caller_id, cc)
            if not n:
                frappe.throw(_("Caller ID must be a valid phone number."))
            self.twilio_caller_id = n
        seen = set()
        for row in self.business_lines:
            n = normalize_phone(row.number, cc)
            if not n:
                frappe.throw(_("Row {0}: invalid business number.").format(row.idx))
            if n in seen:
                frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, n))
            seen.add(n)
            row.number = n
        self.recording_policy = "Recording disabled"

    def on_update(self):
        frappe.clear_cache()  # the browser-calling flag is part of the boot cache
