import frappe


def _is_admin(user):
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def query_conditions(user=None):
    """Sales Managers may only list review items (calls not yet tied to a Lead)."""
    if _is_admin(user or frappe.session.user):
        return ""
    return "(`tabAX Lead Call`.`lead` is null or `tabAX Lead Call`.`lead` = '')"


def has_permission(doc, ptype=None, user=None, debug=False, **kwargs):
    if _is_admin(user or frappe.session.user):
        return True
    return not doc.get("lead")
