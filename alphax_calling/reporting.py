import frappe
from frappe import _

CAP = 20000


def column(label, fieldname, fieldtype="Data", width=140, options=None):
    return dict(label=_(label), fieldname=fieldname, fieldtype=fieldtype, width=width, options=options)


def is_manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & {"Sales Manager", "System Manager"})


def visible_lead_names(names):
    """Subset of `names` the session user may read. get_list applies roles, user permissions and sharing."""
    names, out = sorted(set(n for n in names if n)), set()
    for i in range(0, len(names), 500):
        chunk = names[i:i + 500]
        out.update(frappe.get_list("Lead", filters={"name": ["in", chunk]}, pluck="name",
                                   limit_page_length=len(chunk)))
    return out


def visible_calls(filters, fields):
    """Call rows whose Lead the viewer may read. Calls with no Lead (review items) are never returned."""
    fields = sorted(set(fields) | {"lead"})
    rows = frappe.get_all("AX Lead Call", filters=filters, fields=fields, order_by="creation desc",
                          limit_page_length=CAP)
    if len(rows) >= CAP:
        frappe.msgprint(_("Report limited to the newest {0} calls. Narrow the dates."). format(CAP))
    visible = visible_lead_names(r.lead for r in rows)
    return [r for r in rows if r.lead in visible]
