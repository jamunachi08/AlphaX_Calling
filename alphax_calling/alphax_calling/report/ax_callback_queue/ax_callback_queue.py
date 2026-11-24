import frappe
from alphax_calling.reporting import column, visible_calls


def execute(filters=None):
    columns = [column("Callback due", "due_at", "Datetime", 165),
        column("Lead", "lead", "Link", 200, "Lead"), column("Callback owner", "callback_owner", "Link", 190, "User"),
        column("Notes", "note", "Small Text", 340)]
    filters = {"callback_owner": frappe.session.user, "completed_at": ["is", "not set"]}
    rows = visible_calls(filters, ["lead", "due_at", "callback_owner", "note"])
    return columns, sorted(rows, key=lambda row: row.due_at)
