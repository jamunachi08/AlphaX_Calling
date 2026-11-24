import frappe


def column(label, fieldname, fieldtype="Data", width=140, options=None):
    return dict(label=frappe._(label), fieldname=fieldname, fieldtype=fieldtype, width=width, options=options)


def visible_calls(filters, fields):
    # get_list applies Lead role, user, sharing and assignment restrictions.
    cursor = ""
    while True:
        leads = frappe.get_list("Lead", filters={"name": [">", cursor]},
            fields=["name"], order_by="name asc", page_length=500)
        if not leads:
            return
        names = [lead.name for lead in leads]
        yield from frappe.get_all("AX Lead Call", filters={**filters, "lead": ["in", names]}, fields=fields)
        cursor = names[-1]
        if len(names) < 500:
            return
