import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from alphax_calling.reporting import column, is_manager, visible_calls, visible_lead_names


def execute(filters=None):
    filters = frappe._dict(filters or {})
    cond = {"callback_owner": ["is", "set"], "completed_at": ["is", "not set"]}
    if not (filters.scope == "Team" and is_manager()):
        cond["callback_owner"] = frappe.session.user
    rows = visible_calls(cond, ["due_at", "callback_owner", "note", "outcome", "call_status"])
    leads = {r.name: r for r in frappe.get_all("Lead", filters={"name": ["in", list(visible_lead_names(r.lead for r in rows))]},
             fields=["name", "lead_name", "mobile_no"], limit_page_length=0)} if rows else {}
    now, today = now_datetime(), getdate()
    data, counts = [], {"Overdue": 0, "Due today": 0, "Upcoming": 0}
    for r in sorted(rows, key=lambda r: r.due_at):
        state = "Overdue" if r.due_at < now else ("Due today" if getdate(r.due_at) == today else "Upcoming")
        counts[state] += 1
        lead = leads.get(r.lead, {})
        data.append(dict(state=_(state), due_at=r.due_at, hours_overdue=round((now - r.due_at).total_seconds() / 3600, 1)
                    if state == "Overdue" else 0, lead=r.lead, lead_name=lead.get("lead_name"),
                    mobile_no=lead.get("mobile_no"), callback_owner=r.callback_owner, outcome=r.outcome, note=r.note))
    columns = [column("Status", "state", "Data", 100), column("Callback due", "due_at", "Datetime", 165),
               column("Hours overdue", "hours_overdue", "Float", 120),
               column("Lead", "lead", "Link", 160, "Lead"), column("Lead name", "lead_name", "Data", 180),
               column("Mobile", "mobile_no", "Data", 130), column("Callback owner", "callback_owner", "Link", 180, "User"),
               column("Outcome", "outcome", "Data", 140), column("Notes", "note", "Small Text", 300)]
    summary = [dict(value=counts["Overdue"], label=_("Overdue"), datatype="Int", indicator="Red"),
               dict(value=counts["Due today"], label=_("Due today"), datatype="Int", indicator="Orange"),
               dict(value=counts["Upcoming"], label=_("Upcoming"), datatype="Int", indicator="Blue")]
    return columns, data, None, None, summary
