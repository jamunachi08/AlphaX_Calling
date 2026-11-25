from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate, add_to_date

from alphax_calling.reporting import column, visible_calls

CALL_COLS = ["executive", "answered_by", "business_line", "call_status", "is_final", "final_source", "spoke",
             "talk_seconds", "outcome", "human_updated_at", "creation"]


def _who(r):
    return r.get("executive") or r.get("answered_by") or _("Unassigned")


def execute(filters=None):
    f = frappe._dict(filters or {})
    start, end = getdate(f.from_date or add_days(nowdate(), -30)), getdate(f.to_date or nowdate())
    base = []
    for key in ("company", "business_line"):
        if f.get(key):
            base.append([key, "=", f[key]])
    calls = visible_calls(base + [["creation", ">=", start], ["creation", "<", add_days(end, 1)]], CALL_COLS)
    open_cb = visible_calls(base + [["callback_owner", "is", "set"], ["completed_at", "is", "not set"]],
                            ["callback_owner", "business_line", "due_at"])
    now, grace = now_datetime(), add_to_date(now_datetime(), minutes=-15)
    S = defaultdict(lambda: defaultdict(int))
    reached = defaultdict(set)
    for r in calls:
        who = _who(r)
        if f.executive and who != f.executive:
            continue
        s, k = S[(who, r.business_line or "")], (who, r.business_line or "")
        s["attempts"] += 1
        if r.is_final and r.call_status == "Answered":
            s["answered"] += 1
        if cint(r.spoke):
            s["spoke"] += 1
            reached[k].add(r.lead)
        s["talk"] += cint(r.talk_seconds)
        s["demos"] += r.outcome == "Demo agreed"
        if not r.human_updated_at and (r.call_status == "Dialing" or r.final_source == "Provider") and r.creation < grace:
            s["awaiting"] += 1
    for r in open_cb:
        if f.executive and r.callback_owner != f.executive:
            continue
        s = S[(r.callback_owner, r.business_line or "")]
        s["open"] += 1
        s["overdue"] += bool(r.due_at and r.due_at < now)
    data = []
    for (who, bl), s in sorted(S.items()):
        data.append(dict(executive=who, business_line=bl, attempts=s["attempts"], answered=s["answered"],
                         answer_rate=round(100.0 * s["answered"] / s["attempts"], 1) if s["attempts"] else 0,
                         spoke=s["spoke"], leads_reached=len(reached[(who, bl)]), talk_minutes=round(s["talk"] / 60, 1),
                         demos=s["demos"], open_callbacks=s["open"], overdue_callbacks=s["overdue"],
                         awaiting_update=s["awaiting"]))
    columns = [column("Executive", "executive", "Data", 190), column("Business line", "business_line", "Data", 130),
               column("Attempts", "attempts", "Int", 90), column("Answered (reported)", "answered", "Int", 130),
               column("Answer rate %", "answer_rate", "Percent", 110),
               column("Customer conversations (confirmed)", "spoke", "Int", 190),
               column("Unique Leads reached", "leads_reached", "Int", 150), column("Talk minutes", "talk_minutes", "Float", 110),
               column("Demos agreed", "demos", "Int", 110), column("Open callbacks", "open_callbacks", "Int", 120),
               column("Overdue callbacks", "overdue_callbacks", "Int", 130),
               column("Awaiting executive update", "awaiting_update", "Int", 170)]
    chart = {"data": {"labels": [d["executive"] for d in data],
                      "datasets": [{"name": _("Attempts"), "values": [d["attempts"] for d in data]},
                                   {"name": _("Customer conversations"), "values": [d["spoke"] for d in data]}]},
             "type": "bar"} if data else None
    msg = _("Answered comes from the carrier or the executive and may include voicemail. "
            "Customer conversations are confirmed by the executive and are the human-contact measure.")
    return columns, data, msg, chart
