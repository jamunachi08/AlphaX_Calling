import re

import frappe

from alphax_calling.config import get_settings
from alphax_calling.utils import normalize_phone


def _digits_sql(col):
    expr = f"`tabLead`.`{col}`"
    for ch in (" ", "-", "(", ")", ".", "+"):
        expr = f"REPLACE({expr}, '{ch}', '')"
    return expr


def find_leads_by_number(number, company=None, default_cc=None):
    """Names of ALL Leads (ignoring permissions) whose mobile/phone normalises to `number`.

    Callers must never show these names to a user without a per-Lead permission check.
    """
    if not number:
        return []
    cc = default_cc or get_settings().default_cc
    pattern = "%" + re.sub(r"\D", "", number)[-9:]
    rows = frappe.db.sql(
        f"select name, mobile_no, phone, company from `tabLead` "
        f"where {_digits_sql('mobile_no')} like %(p)s or {_digits_sql('phone')} like %(p)s limit 200",
        {"p": pattern}, as_dict=True)
    out = []
    for r in rows:
        if company and r.company and r.company != company:
            continue
        if number in (normalize_phone(r.mobile_no, cc), normalize_phone(r.phone, cc)):
            out.append(r.name)
    return out


def visible_same_number(number, exclude=None, user=None):
    """Other Leads with this number that `user` (default: session user) may read."""
    user = user or frappe.session.user
    return [n for n in find_leads_by_number(number)
            if n != exclude and frappe.has_permission("Lead", "read", doc=n, user=user)]


def pick_callback_owner(lead_doc, extra=None):
    """Lead owner, then the business number's inbound owner, then the default owner: first active user with write access."""
    for user in (lead_doc.get("lead_owner"), extra, get_settings().callback_owner):
        if user and frappe.db.get_value("User", user, "enabled") and frappe.has_permission(
                "Lead", ptype="write", doc=lead_doc, user=user):
            return user
    return None
