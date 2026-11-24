from collections import Counter
from frappe.utils import add_days, now_datetime
from alphax_calling.reporting import column, visible_calls


def execute(filters=None):
    columns = [column("Logged by", "executive", "Link", 210, "User"),
        column("Calls logged", "calls", "Int"), column("Reported answered", "answered", "Int", 170),
        column("Open callbacks from these calls", "callbacks", "Int", 230)]
    stats = {}
    rows = visible_calls({"creation": [">=", add_days(now_datetime(), -30)]},
        ["executive", "call_status", "callback_owner", "completed_at"])
    for row in rows:
        totals = stats.setdefault(row.executive, Counter())
        totals["calls"] += 1
        totals["answered"] += int(row.call_status == "Answered")
        totals["callbacks"] += int(bool(row.callback_owner and not row.completed_at))
    return columns, [dict(executive=user, **stats[user]) for user in sorted(stats)]
