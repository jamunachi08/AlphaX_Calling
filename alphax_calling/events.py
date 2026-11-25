"""Provider event ingestion: authenticated, idempotent, order-tolerant, browser-independent."""
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from alphax_calling import utils
from alphax_calling.api import ensure_missed_callback
from alphax_calling.config import get_settings
from alphax_calling.matching import find_leads_by_number

FIELDS = ["name", "lead", "direction", "call_status", "is_final", "final_source", "started_at", "answered_at",
          "ended_at", "talk_seconds", "answered_by", "executive", "callback_owner", "due_at", "provider_key",
          "provider_call_id", "review_status"]


class _Reject(Exception):
    pass


def _fail(code, message):
    frappe.local.response["http_status_code"] = code
    return {"ok": False, "error": message}


def _clean(value, limit=140):
    return str(value).strip()[:limit] if value not in (None, "") else ""


@frappe.whitelist(allow_guest=True, methods=["POST"])
@frappe.rate_limit(limit=1200, seconds=60)
def provider_event():
    cfg = get_settings()
    if not cfg.enabled or not cfg.webhook_secret:
        return _fail(503, "Provider events are not configured.")
    body = frappe.request.get_data() or b""
    if not utils.verify_signature(cfg.webhook_secret, frappe.get_request_header("X-AlphaX-Timestamp"), body,
                                  frappe.get_request_header("X-AlphaX-Signature")):
        return _fail(401, "Invalid signature.")
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        return _fail(400, "Body must be a JSON object.")
    frappe.set_user("Administrator")  # signature verified: act as the system
    try:
        return {"ok": True, **_process(data, cfg)}
    except _Reject as e:
        frappe.db.rollback()
        return _fail(422, str(e))


def _process(data, cfg):
    provider, account = _clean(data.get("provider")), _clean(data.get("account"))
    event_id, call_id = _clean(data.get("event_id")), _clean(data.get("call_id"))
    etype = data.get("event_type")
    try:
        tz = frappe.utils.get_system_timezone()
    except Exception:
        tz = "Asia/Riyadh"
    occurred = utils.parse_iso(data.get("occurred_at"), tz)
    if not (provider and event_id and call_id) or etype not in utils.EVENT_RANK or not occurred:
        raise _Reject("provider, event_id, call_id, a known event_type and occurred_at are required.")

    ev = frappe.get_doc({"doctype": "AX Call Event", "provider": provider, "provider_account": account,
                         "event_id": event_id, "event_type": etype, "call_id": call_id, "occurred_at": occurred,
                         "result": "Received", "payload": json.dumps(data, ensure_ascii=False)[:20000]})
    try:
        ev.insert(ignore_permissions=True, set_name=utils.event_name_for(provider, account, event_id))
    except frappe.DuplicateEntryError:
        frappe.clear_last_message()
        return {"result": "Duplicate"}

    pk = f"{provider}:{account}:{call_id}"
    ref = _clean(data.get("client_ref"))
    name = frappe.db.get_value("AX Lead Call", {"provider_key": pk}, "name")
    if not name and utils.is_uuid(ref) and frappe.db.exists("AX Lead Call", ref):
        name = ref
    row = frappe.db.get_value("AX Lead Call", name, FIELDS, as_dict=True, for_update=True) if name else None
    if row and row.provider_key and row.provider_key != pk:
        raise _Reject("client_ref is already bound to another provider call.")
    created = False
    if not row:
        name, created = _create_call(data, pk, provider, account, call_id, occurred, cfg)
        row = frappe.db.get_value("AX Lead Call", name, FIELDS, as_dict=True, for_update=True)

    action, updates = utils.plan_event(row, etype, occurred, data.get("status"), data.get("duration_seconds"))
    result = {"apply": "Applied", "attach": "Attached", "late": "Ignored Late"}[action]
    if action != "late":
        rec = frappe.get_doc("AX Lead Call", name)
        rec.update(updates)
        for f, v in (("provider", provider), ("provider_account", account), ("provider_call_id", call_id)):
            if not rec.get(f):
                rec.set(f, v)
        agent = _agent(data.get("agent"))
        if agent and rec.direction == "Inbound" and not rec.answered_by and etype in ("call.answered", "call.ended"):
            rec.answered_by = agent
        rec.last_event_at = now_datetime()
        if updates.get("final_source") == "Provider":
            ensure_missed_callback(rec)
        rec.flags.ignore_permissions = True
        rec.save()
        if updates.get("final_source") == "Provider" and rec.lead:
            _timeline(rec)
    if created and rec_lead_ok(name):
        _notify_incoming(name, _agent(data.get("agent")))
    frappe.db.set_value("AX Call Event", ev.name, {"result": result, "call": name}, update_modified=False)
    return {"result": result, "call": name}


def rec_lead_ok(name):
    return bool(frappe.db.get_value("AX Lead Call", name, "lead")) and \
        frappe.db.get_value("AX Lead Call", name, "direction") == "Inbound"


def _agent(user):
    user = _clean(user)
    return user if user and frappe.db.get_value("User", user, "enabled") else None


def _create_call(data, pk, provider, account, call_id, occurred, cfg):
    direction = {"inbound": "Inbound", "outbound": "Outbound"}.get(str(data.get("direction", "")).lower())
    if not direction:
        raise _Reject("direction must be inbound or outbound.")
    inbound = direction == "Inbound"
    cp = utils.normalize_phone(data.get("from" if inbound else "to"), cfg.default_cc)
    biz = utils.normalize_phone(data.get("business_number") or data.get("to" if inbound else "from"), cfg.default_cc)
    line = cfg.business_lines.get(biz) or {}
    lead, review, reason = None, "", ""
    if inbound:
        matches = find_leads_by_number(cp, line.get("company"), cfg.default_cc)
        if len(matches) == 1:
            lead = matches[0]
        else:
            review = "Needs Review"
            reason = _("Several Leads share the caller number.") if matches else _("No Lead matches the caller number.")
    else:
        review, reason = "Needs Review", _("Outbound call has no Lead reference.")
    rec = frappe.get_doc(dict(
        doctype="AX Lead Call", lead=lead, company=line.get("company") or (
            frappe.db.get_value("Lead", lead, "company") if lead else None),
        business_line=line.get("business_line"), direction=direction, source="Provider Event",
        call_status="Dialing", is_final=0, provider=provider, provider_account=account, provider_call_id=call_id,
        counterparty_number=cp, business_number=biz, review_status=review, review_reason=reason,
        started_at=occurred, last_event_at=now_datetime()))
    name = utils.call_name_for(pk)
    try:
        rec.insert(ignore_permissions=True, set_name=name)
        return name, True
    except frappe.DuplicateEntryError:  # a parallel delivery created it first
        frappe.clear_last_message()
        return name, False


def _timeline(rec):
    lead = frappe.get_doc("Lead", rec.lead)
    parts = [_("{0} call (carrier): {1}").format(_(rec.direction), _(rec.call_status))]
    if rec.talk_seconds:
        parts.append(_("Talk time: {0} s").format(rec.talk_seconds))
    if rec.callback_owner:
        parts.append(_("Callback: {0} · {1}").format(rec.callback_owner, rec.due_at))
    lead.add_comment("Comment", "<br>".join(frappe.utils.escape_html(str(p)) for p in parts))


def _notify_incoming(name, agent):
    lead = frappe.db.get_value("AX Lead Call", name, "lead")
    target = agent or frappe.db.get_value("Lead", lead, "lead_owner")
    if target and frappe.db.get_value("User", target, "enabled") and frappe.has_permission(
            "Lead", "read", doc=lead, user=target):
        frappe.publish_realtime("alphax_incoming_call", {
            "lead": lead, "lead_name": frappe.db.get_value("Lead", lead, "lead_name"), "call": name},
            user=target, after_commit=True)
