import uuid
from html import escape

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, get_fullname, getdate, now_datetime

from alphax_calling import utils
from alphax_calling.config import get_settings
from alphax_calling.matching import pick_callback_owner, visible_same_number

CALL_FIELDS = ["name", "lead", "executive", "answered_by", "direction", "call_status", "is_final",
               "final_source", "talk_seconds", "callback_owner", "due_at", "completed_at", "todo",
               "human_updated_at", "counterparty_number", "started_at"]
HISTORY_FIELDS = ["name", "creation", "direction", "call_status", "is_final", "final_source", "outcome",
                  "spoke", "talk_seconds", "executive", "answered_by", "callback_owner", "due_at",
                  "completed_at", "human_updated_at", "source", "reconcile_flag", "demo_at"]


def require_lead(name, permission):
    doc = frappe.get_doc("Lead", name)
    doc.check_permission(permission)
    return doc


def _key(request_id):
    try:
        return str(uuid.UUID(str(request_id)))
    except (ValueError, TypeError, AttributeError):
        frappe.throw(_("Invalid call reference."))


def _comment(lead_doc, parts):
    lead_doc.add_comment("Comment", "<br>".join(escape(p).replace("\n", "<br>") for p in parts if p))


def _check_callback(lead_doc, due_at, owner):
    if not due_at or get_datetime(due_at) <= now_datetime():
        frappe.throw(_("Choose a future callback time."))
    owner = owner or frappe.session.user
    if not frappe.db.get_value("User", owner, "enabled") or not frappe.has_permission(
            "Lead", ptype="write", doc=lead_doc, user=owner):
        frappe.throw(_("Choose an active callback owner with write access to the Lead."))
    return owner


def _create_todo(owner, lead_doc, due_at, assigned_by, description):
    todo = frappe.get_doc({"doctype": "ToDo", "allocated_to": owner, "reference_type": "Lead",
                           "reference_name": lead_doc.name, "description": description,
                           "date": getdate(due_at), "assigned_by": assigned_by,
                           "priority": "Medium", "status": "Open"})
    todo.insert(ignore_permissions=True)
    return todo.name


def _close_todo(name):
    if name and frappe.db.exists("ToDo", name):
        todo = frappe.get_doc("ToDo", name)
        if todo.status != "Closed":
            todo.status = "Closed"
            todo.flags.ignore_permissions = True
            todo.save()


def _create_demo_event(lead_doc, when, note):
    ev = frappe.get_doc({
        "doctype": "Event", "subject": _("Demo: {0}").format(lead_doc.get("lead_name") or lead_doc.name),
        "starts_on": when, "ends_on": add_to_date(get_datetime(when), hours=1),
        "event_category": "Meeting", "event_type": "Private", "status": "Open", "description": note or "",
        "event_participants": [{"reference_doctype": "Lead", "reference_docname": lead_doc.name}]})
    ev.insert(ignore_permissions=True)
    return ev.name


def ensure_missed_callback(rec, lead_doc=None, owner=None):
    """Give a missed inbound call exactly one callback owner. `rec` is an unsaved-changes doc."""
    if rec.callback_owner or rec.direction != "Inbound" or rec.call_status != "Unanswered" or not rec.lead:
        return False
    lead_doc = lead_doc or frappe.get_doc("Lead", rec.lead)
    owner = owner or pick_callback_owner(lead_doc)
    if not owner:
        rec.review_status, rec.review_reason = "Needs Review", _("Missed call has no callback owner.")
        return False
    due = add_to_date(now_datetime(), minutes=get_settings().missed_callback_minutes)
    rec.callback_owner, rec.due_at = owner, due
    rec.todo = _create_todo(owner, lead_doc, due, frappe.session.user, _("Return missed call"))
    return True


@frappe.whitelist(methods=["POST"])
def log_call(lead, request_id, direction="Outbound", call_status="", outcome="", note="", due_at=None,
             callback_owner=None, spoke=0, talk_minutes=None, demo_at=None, schedule_callback=0,
             business_line=None):
    """Create a manual call record, or add the executive's update to a dialer/provider record.

    `request_id` is a browser UUID (new record) or the id of an existing record. Replays are no-ops.
    """
    lead_doc = require_lead(lead, "write")
    key = _key(request_id)
    user = frappe.session.user
    frappe.db.get_value("Lead", lead, "name", for_update=True)  # serialise retries per Lead
    ex = frappe.db.get_value("AX Lead Call", key, CALL_FIELDS, as_dict=True, for_update=True)
    if ex:
        if ex.lead != lead or user not in (ex.executive, ex.answered_by):
            frappe.throw(_("Call reference already used."))
        if ex.human_updated_at:
            return key
    locked = bool(ex and ex.final_source == "Provider")  # the carrier owns direction/result
    if locked:
        direction, call_status = ex.direction, ex.call_status
    if direction not in ("Inbound", "Outbound") or call_status not in utils.FINAL_STATUSES:
        frappe.throw(_("Choose a valid direction and result."))
    outcome = outcome or ""
    if outcome not in utils.OUTCOMES:
        frappe.throw(_("Choose a valid outcome."))
    if len(note or "") > 4000:
        frappe.throw(_("Keep the call note within 4,000 characters."))
    spoke = cint(spoke)
    if spoke and call_status != "Answered":
        frappe.throw(_("Only an answered call can be marked as spoken with the customer."))

    talk_seconds = ex.talk_seconds if locked else 0
    if call_status == "Answered" and not locked and talk_minutes not in (None, ""):
        if not 0 <= flt(talk_minutes) <= 600:
            frappe.throw(_("Talk time must be between 0 and 600 minutes."))
        talk_seconds = int(flt(talk_minutes) * 60)

    wants_callback = outcome == "Callback requested" or cint(schedule_callback)
    if wants_callback:
        callback_owner = _check_callback(lead_doc, due_at, callback_owner)
    if outcome == "Demo agreed" and (not demo_at or get_datetime(demo_at) <= now_datetime()):
        frappe.throw(_("Choose a future date and time for the demo."))

    values = dict(outcome=outcome, note=note or "", spoke=spoke, talk_seconds=talk_seconds,
                  human_updated_by=user, human_updated_at=now_datetime())
    if wants_callback:
        if ex and ex.callback_owner and not ex.completed_at:
            _close_todo(ex.todo)  # replace the earlier commitment
        values.update(callback_owner=callback_owner, due_at=due_at, completed_at=None, completed_by=None,
                      overdue_notified=0,
                      todo=_create_todo(callback_owner, lead_doc, due_at, user,
                                        _("Call back {0}").format(lead_doc.get("lead_name") or lead)))
    if outcome == "Demo agreed":
        values.update(demo_at=demo_at, event=_create_demo_event(lead_doc, demo_at, note))

    if ex:
        rec = frappe.get_doc("AX Lead Call", key)
        if not locked:
            values.update(direction=direction, call_status=call_status, is_final=1, final_source="Human")
        rec.update(values)
        rec.flags.ignore_permissions = True
        rec.save()
    else:
        rec = frappe.get_doc(dict(
            doctype="AX Lead Call", lead=lead, company=lead_doc.get("company"), business_line=business_line,
            executive=user, direction=direction, source="Manual Log", call_status=call_status, is_final=1,
            final_source="Human", counterparty_number=utils.normalize_phone(
                lead_doc.get("mobile_no") or lead_doc.get("phone"), get_settings().default_cc), **values))
        rec.insert(ignore_permissions=True, set_name=key)

    details = [_("{0} call: {1}").format(_(direction), _(call_status)) if not ex or not locked
               else _("Call outcome updated"), outcome, note]
    if spoke:
        details.append(_("Spoke with the customer"))
    if wants_callback:
        details.append(_("Callback: {0} · {1}").format(callback_owner, due_at))
    if outcome == "Demo agreed":
        details.append(_("Demo: {0} · Event {1}").format(demo_at, values["event"]))
    _comment(lead_doc, details)
    return rec.name


@frappe.whitelist(methods=["POST"])
def complete_callback(call):
    row = frappe.db.get_value("AX Lead Call", call, ["lead", "callback_owner", "completed_at", "todo"],
                              as_dict=True, for_update=True)
    if not row or not row.lead or row.callback_owner != frappe.session.user:
        frappe.throw(_("Only the callback owner can complete this callback."), frappe.PermissionError)
    lead = require_lead(row.lead, "write")
    if row.completed_at:
        return
    frappe.db.set_value("AX Lead Call", call, {"completed_at": now_datetime(), "completed_by": frappe.session.user})
    _close_todo(row.todo)
    lead.add_comment("Comment", _("Callback completed") + " · " + escape(call))


@frappe.whitelist(methods=["POST"])
def reschedule_callback(call, due_at):
    row = frappe.db.get_value("AX Lead Call", call, ["lead", "callback_owner", "completed_at", "todo"],
                              as_dict=True, for_update=True)
    if not row or not row.lead or row.callback_owner != frappe.session.user:
        frappe.throw(_("Only the callback owner can reschedule this callback."), frappe.PermissionError)
    lead = require_lead(row.lead, "write")
    if row.completed_at:
        frappe.throw(_("This callback is already completed."))
    _check_callback(lead, due_at, row.callback_owner)
    frappe.db.set_value("AX Lead Call", call, {"due_at": due_at, "overdue_notified": 0})
    if row.todo and frappe.db.exists("ToDo", row.todo):
        frappe.db.set_value("ToDo", row.todo, "date", getdate(due_at))
    lead.add_comment("Comment", _("Callback rescheduled") + " · " + escape(str(due_at)))


@frappe.whitelist()
def my_open_callbacks(lead):
    require_lead(lead, "write")
    return frappe.get_all("AX Lead Call", filters={"lead": lead, "callback_owner": frappe.session.user,
                          "completed_at": ["is", "not set"]}, fields=["name", "due_at"], order_by="due_at asc")


def _history(lead, limit=200):
    return frappe.get_all("AX Lead Call", filters={"lead": lead}, fields=HISTORY_FIELDS,
                          order_by="creation desc", limit_page_length=limit)


def _advice_text(key):
    return {
        "overdue": _("A callback on this Lead is overdue. Complete or reschedule it first."),
        "stop_calling": _("Five attempts in a row went unanswered. Stop calling; send a message and review the Lead status."),
        "change_channel": _("Three attempts in a row went unanswered. Try a different time of day or another channel."),
        "verify_number": _("The last call reported a wrong number. Verify the number before calling again."),
        "schedule_followup": _("Information was sent but no follow-up is scheduled. Schedule a callback."),
        "confirm_demo": _("A demo was agreed. Confirm the details with the customer the day before."),
        "first_call": _("No calls yet. Call within your working window."),
    }[key]


@frappe.whitelist()
def lead_panel(lead):
    """Call summary, history, advice and the user's pending items for the Lead form."""
    require_lead(lead, "read")
    user, now = frappe.session.user, now_datetime()
    rows = _history(lead)
    finals = [r for r in rows if r.is_final]
    streak = utils.streak([r.call_status for r in finals])
    open_cb = [r for r in rows if r.callback_owner and not r.completed_at]
    overdue = [r for r in open_cb if r.due_at and r.due_at < now]
    last_outcome = next((r.outcome for r in rows if r.outcome), "")
    names = {}

    def who(u):
        if u and u not in names:
            names[u] = get_fullname(u)
        return names.get(u, "")

    history = [dict(r, executive_name=who(r.executive or r.answered_by), owner_name=who(r.callback_owner))
               for r in rows[:25]]
    pending = [dict(name=r.name, direction=r.direction, call_status=r.call_status,
                    final_source=r.final_source, creation=r.creation)
               for r in rows if not r.human_updated_at and user in (r.executive, r.answered_by)][:5]
    return {
        "summary": {"attempts": len(rows), "answered": sum(r.call_status == "Answered" for r in finals),
                    "spoke": sum(cint(r.spoke) for r in rows), "streak": streak,
                    "open_callbacks": len(open_cb), "overdue_callbacks": len(overdue),
                    "mine_open": sum(r.callback_owner == user for r in open_cb)},
        "advice": [_advice_text(k) for k in utils.advice_keys(
            len(rows), streak, len(overdue), last_outcome, bool(open_cb))],
        "history": history, "pending": pending,
        "suggested_due": utils.next_working_slot(now, 10, get_settings().weekend).strftime("%Y-%m-%d %H:%M:%S"),
    }


@frappe.whitelist()
def opportunity_calls(opportunity):
    opp = frappe.get_doc("Opportunity", opportunity)
    opp.check_permission("read")
    if opp.get("opportunity_from") != "Lead" or not opp.get("party_name"):
        return {"history": []}
    return lead_panel(opp.party_name)  # enforces Lead read permission


def _dial_warnings(doc, number, cfg):
    out = []
    window = utils.in_call_window(now_datetime(), cfg.window, cfg.weekend)
    if window == "weekend":
        out.append(_("Today is a weekend day."))
    elif window == "hours":
        out.append(_("This is outside the call window ({0}).").format(cfg.window))
    if cfg.default_cc == "966" and not utils.is_saudi(number):
        out.append(_("This is not a Saudi number ({0}). Check the country code.").format(number))
    others = visible_same_number(number, exclude=doc.name)
    if others:
        out.append(_("The same number is on {0} other Lead(s) you can access: {1}.").format(
            len(others), ", ".join(others[:5])))
    streak = utils.streak([r.call_status for r in _history(doc.name, 20) if r.is_final])
    if streak >= 3:
        out.append(_("The last {0} attempts on this Lead were not answered.").format(streak))
    return out


@frappe.whitelist(methods=["POST"])
def dial_number(lead, fieldname, confirmed=0):
    """Validate, record a dial attempt and return the E.164 number for the tel: link."""
    doc = require_lead(lead, "write")
    cfg = get_settings()
    if cfg.dnc_field and (not doc.meta.has_field(cfg.dnc_field) or doc.get(cfg.dnc_field)):
        frappe.throw(_("Dialing is blocked by the contact preference setting."))
    if doc.get("status") == "Do Not Contact":
        frappe.throw(_("This Lead is marked Do Not Contact."))
    if fieldname not in ("mobile_no", "phone"):
        frappe.throw(_("Choose a Lead phone field."))
    number = utils.normalize_phone(doc.get(fieldname), cfg.default_cc)
    if not number:
        frappe.throw(_("Enter a valid phone number on the Lead before dialing."))
    warnings = _dial_warnings(doc, number, cfg)
    if warnings and not cint(confirmed):
        return {"needs_confirmation": 1, "warnings": warnings}
    user, now = frappe.session.user, now_datetime()
    recent = frappe.db.get_value("AX Lead Call", {
        "lead": lead, "executive": user, "call_status": "Dialing", "counterparty_number": number,
        "human_updated_at": ["is", "not set"], "started_at": [">", add_to_date(now, minutes=-2)]}, "name")
    if not recent:  # a double click must not create two attempts
        rec = frappe.get_doc(dict(
            doctype="AX Lead Call", lead=lead, company=doc.get("company"), executive=user, direction="Outbound",
            source="Dialer Tap", call_status="Dialing", is_final=0, counterparty_number=number, started_at=now))
        rec.insert(ignore_permissions=True, set_name=str(uuid.uuid4()))
        recent = rec.name
    return {"number": number, "attempt": recent, "warnings": warnings}


@frappe.whitelist(methods=["POST"])
def resolve_review(call, lead, callback_owner=None):
    """Sales Manager: tie a review item to a Lead and, for a missed call, fix its callback owner."""
    frappe.only_for(("Sales Manager", "System Manager"))
    lead_doc = require_lead(lead, "write")
    frappe.db.get_value("AX Lead Call", call, "name", for_update=True)
    rec = frappe.get_doc("AX Lead Call", call)
    if rec.review_status != "Needs Review":
        frappe.throw(_("This call is not waiting for review."))
    if rec.lead and rec.lead != lead:
        frappe.throw(_("This call is already linked to a different Lead."))
    if callback_owner and not (frappe.db.get_value("User", callback_owner, "enabled") and frappe.has_permission(
            "Lead", ptype="write", doc=lead_doc, user=callback_owner)):
        frappe.throw(_("Choose an active callback owner with write access to the Lead."))
    rec.lead = lead
    rec.company = rec.company or lead_doc.get("company")
    ensure_missed_callback(rec, lead_doc, callback_owner)
    if rec.direction == "Inbound" and rec.call_status == "Unanswered" and not rec.callback_owner:
        frappe.throw(_("Choose a callback owner for this missed call."))
    rec.review_status, rec.review_reason = "Resolved", ""
    rec.reviewed_by, rec.reviewed_at = frappe.session.user, now_datetime()
    rec.flags.ignore_permissions = True
    rec.save()
    _comment(lead_doc, [_("{0} call linked after manager review: {1}").format(_(rec.direction), _(rec.call_status))])
    return rec.name
