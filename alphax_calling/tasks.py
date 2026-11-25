import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, now_datetime

from alphax_calling.config import get_settings


def notify_overdue_callbacks():
    rows = frappe.get_all("AX Lead Call", filters={
        "callback_owner": ["is", "set"], "completed_at": ["is", "not set"],
        "due_at": ["<", now_datetime()], "overdue_notified": 0},
        fields=["name", "lead", "callback_owner", "due_at"], limit_page_length=200)
    for r in rows:
        try:
            if r.lead and frappe.db.get_value("User", r.callback_owner, "enabled"):
                frappe.get_doc({
                    "doctype": "Notification Log", "type": "Alert", "for_user": r.callback_owner,
                    "document_type": "Lead", "document_name": r.lead,
                    "subject": _("Overdue callback on Lead {0}").format(r.lead),
                }).insert(ignore_permissions=True)
            frappe.db.set_value("AX Lead Call", r.name, "overdue_notified", 1, update_modified=False)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="AlphaX Calling: overdue notification failed")


def flag_stale_provider_calls():
    """Provider-tracked calls that never reached an end event are flagged for reconciliation."""
    for name in frappe.get_all("AX Lead Call", filters={
            "provider_call_id": ["is", "set"], "is_final": 0, "reconcile_flag": 0,
            "last_event_at": ["<", add_to_date(now_datetime(), hours=-4)]}, pluck="name", limit_page_length=500):
        frappe.db.set_value("AX Lead Call", name, "reconcile_flag", 1, update_modified=False)
    frappe.db.commit()


def purge_old_events():
    frappe.db.delete("AX Call Event", {"creation": ["<", add_days(now_datetime(), -get_settings().retention_days)]})
    frappe.db.commit()
