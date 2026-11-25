import frappe


def boot_session(bootinfo):
    from alphax_calling.twilio_adapter import ROLES, enabled
    bootinfo.alphax_browser_calling = int(enabled() and bool(set(frappe.get_roles()) & set(ROLES)))
