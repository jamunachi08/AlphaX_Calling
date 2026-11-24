import uuid
from html import escape

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


def require_lead(name, permission):
    doc = frappe.get_doc("Lead", name)
    doc.check_permission(permission)
    return doc


@frappe.whitelist(methods=["POST"])
def log_call(lead, request_id, direction, call_status, outcome="", note="", due_at=None, callback_owner=None):
    lead_doc = require_lead(lead, "write")
    try:
        key = str(uuid.UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        frappe.throw(_("Invalid call reference."))

    # Serialize retries on this Lead. Both the history item and timeline comment
    # commit together at the end of the request.
    frappe.db.get_value("Lead", lead, "name", for_update=True)
    existing = frappe.db.get_value("AX Lead Call", key, ["lead", "executive"], as_dict=True, for_update=True)
    if existing:
        if existing.lead != lead or existing.executive != frappe.session.user:
            frappe.throw(_("Call reference already used."))
        return key

    if direction not in ("Inbound", "Outbound") or call_status not in ("Answered", "Unanswered", "Busy", "Failed"):
        frappe.throw(_("Choose a valid direction and result."))
    if outcome not in ("", "Callback requested", "Demo agreed", "Information sent", "Wrong number", "No interest"):
        frappe.throw(_("Choose a valid outcome."))
    if outcome == "Callback requested":
        if not due_at or get_datetime(due_at) <= now_datetime():
            frappe.throw(_("Choose a future callback time."))
        callback_owner = callback_owner or frappe.session.user
        if not frappe.db.get_value("User", callback_owner, "enabled") or not frappe.has_permission(
            "Lead", ptype="write", doc=lead_doc, user=callback_owner
        ):
            frappe.throw(_("Choose an active callback owner with write access to the Lead."))
    else:
        due_at = callback_owner = None
    if len(note or "") > 4000:
        frappe.throw(_("Keep the call note within 4,000 characters."))
    record = frappe.get_doc(dict(doctype="AX Lead Call", lead=lead, executive=frappe.session.user,
        direction=direction, call_status=call_status, outcome=outcome, note=note,
        callback_owner=callback_owner, due_at=due_at))
    record.insert(ignore_permissions=True, set_name=key)
    details = [f"{direction} call (manually logged): {call_status}", outcome, note]
    if due_at:
        details.append(f"Callback: {callback_owner} · {due_at}")
    lead_doc.add_comment("Comment", "<br>".join(escape(s) for s in details if s))
    return record.name


@frappe.whitelist(methods=["POST"])
def complete_callback(call):
    row = frappe.db.get_value("AX Lead Call", call,
        ["lead", "callback_owner", "completed_at"], as_dict=True, for_update=True)
    if not row or row.callback_owner != frappe.session.user:
        frappe.throw(_("Only the callback owner can complete this callback."), frappe.PermissionError)
    lead = require_lead(row.lead, "write")
    if row.completed_at:
        return
    frappe.db.set_value("AX Lead Call", call, {"completed_at": now_datetime(), "completed_by": frappe.session.user})
    lead.add_comment("Comment", _("Callback completed") + " · " + escape(call))


@frappe.whitelist()
def my_open_callbacks(lead):
    require_lead(lead, "write")
    return frappe.get_all("AX Lead Call", filters={"lead": lead, "callback_owner": frappe.session.user,
        "completed_at": ["is", "not set"]}, fields=["name", "due_at"], order_by="due_at asc")


@frappe.whitelist()
def dial_number(lead, fieldname):
    import re

    doc = require_lead(lead, "write")
    block_field = frappe.conf.get("alphax_calling_do_not_call_field")
    if block_field and (not doc.meta.has_field(block_field) or doc.get(block_field)):
        frappe.throw(_("Dialing is blocked by the contact preference setting."))
    if fieldname not in ("mobile_no", "phone"):
        frappe.throw(_("Choose a Lead phone field."))
    number = re.sub(r"[\s().-]", "", doc.get(fieldname) or "")
    if not re.fullmatch(r"\+?[0-9]{3,15}", number):
        frappe.throw(_("Enter a valid phone number on the Lead before dialing."))
    return number
