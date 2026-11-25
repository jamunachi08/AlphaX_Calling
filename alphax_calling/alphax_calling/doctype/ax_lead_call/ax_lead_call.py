import frappe
from frappe import _
from frappe.model.document import Document


class AXLeadCall(Document):
    def validate(self):
        if self.call_status != "Answered":
            self.talk_seconds = 0  # unanswered, busy, failed and live calls never carry talk time
            self.spoke = 0
        if self.callback_owner and not self.due_at:
            frappe.throw(_("A callback needs a due date."))
        if self.provider and self.provider_call_id:
            self.provider_key = f"{self.provider}:{self.provider_account or ''}:{self.provider_call_id}"
