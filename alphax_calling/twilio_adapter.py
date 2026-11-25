"""Twilio Voice adapter: browser calling (WebRTC) plus call events into the same AX Lead Call record.

Configured in the AX Calling Settings form (site_config key `alphax_calling_twilio` still works as a fallback).
"""

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime
from frappe.utils.data import add_to_date

from alphax_calling import events, twilio_utils as tu, utils
from alphax_calling.config import get_settings
from alphax_calling.matching import find_leads_by_number

ROLES = ("Sales User", "Sales Manager", "System Manager")
REQUIRED = ("account_sid", "auth_token", "api_key_sid", "api_key_secret", "twiml_app_sid", "caller_id")


def _cfg():
    return get_settings().twilio


def enabled():
    s = get_settings()
    return bool(s.enabled and s.provider == "Twilio" and all(s.twilio.get(k) for k in REQUIRED))


def _base():
    return (get_settings().public_url or get_url()).rstrip("/")


def _xml(body, status=200):
    frappe.local.response.update({"type": "download", "filename": "twiml.xml", "filecontent": body.encode(),
                                  "display_content_as": "inline"})
    frappe.local.response["http_status_code"] = status


def _verified_form():
    """Return the POST form if the Twilio signature is valid, else None."""
    qs = frappe.request.query_string.decode()
    url = _base() + frappe.request.path + ("?" + qs if qs else "")
    form = frappe.request.form.to_dict()
    ok = enabled() and tu.valid_signature(url, form, _cfg()["auth_token"],
                                          frappe.get_request_header("X-Twilio-Signature"))
    return form if ok else None


@frappe.whitelist()
def get_token():
    frappe.only_for(ROLES)
    if not enabled():
        frappe.throw(_("Browser calling is not configured."))
    c, user = _cfg(), frappe.session.user
    return {"token": tu.build_access_token(c["account_sid"], c["api_key_sid"], c["api_key_secret"],
                                           tu.identity_for(user), c["twiml_app_sid"], 3600),
            "identity": tu.identity_for(user), "expires_in": 3600}


def _post(payload):
    try:
        events._process(payload, get_settings())
    except events._Reject:
        frappe.log_error(title="AlphaX Calling: Twilio event rejected", message=str(payload))


@frappe.whitelist(allow_guest=True, methods=["POST"])
@frappe.rate_limit(limit=600, seconds=60)
def voice():
    """TwiML App / phone number Voice URL: browser-outbound and PSTN-inbound."""
    form = _verified_form()
    if form is None:
        return _xml("<Response/>", 403)
    frappe.set_user("Administrator")
    cfg, c = get_settings(), _cfg()
    caller = form.get("From") or form.get("Caller") or ""
    if caller.startswith("client:"):
        return _outbound(form, c, cfg)
    return _inbound(form, c, cfg)


def _outbound(form, c, cfg):
    user, number = tu.user_for(form.get("From") or form.get("Caller")), utils.normalize_phone(form.get("To"), cfg.default_cc)
    attempt = form.get("AttemptId")
    row = frappe.db.get_value("AX Lead Call", attempt, ["executive", "counterparty_number", "call_status", "started_at"],
                              as_dict=True) if utils.is_uuid(attempt) else None
    # The browser may only dial the attempt it registered via dial_number (permission, DNC and number checks done there).
    if not (user and row and row.executive == user and row.call_status == "Dialing" and number
            and row.counterparty_number == number and row.started_at > add_to_date(now_datetime(), minutes=-5)):
        return _xml(tu.reject_twiml("rejected"))
    cb = tu.status_url(_base(), direction="outbound", frm=c["caller_id"], to=number, ref=attempt, agent=user)
    return _xml(tu.outbound_twiml(number, c["caller_id"], cb))


def _inbound(form, c, cfg):
    sid = form.get("CallSid")
    customer = utils.normalize_phone(form.get("From"), cfg.default_cc)
    biz = utils.normalize_phone(form.get("To"), cfg.default_cc)
    line = cfg.business_lines.get(biz) or {}
    leads = find_leads_by_number(customer, line.get("company"), cfg.default_cc) if customer else []
    lead = leads[0] if len(leads) == 1 else None
    agent = None
    for user in (frappe.db.get_value("Lead", lead, "lead_owner") if lead else None, line.get("inbound_owner"),
                 cfg.callback_owner):
        if user and frappe.db.get_value("User", user, "enabled") and (
                not lead or frappe.has_permission("Lead", "read", doc=lead, user=user)):
            agent = user
            break
    base = {"provider": "twilio", "account": form.get("AccountSid") or "", "call_id": sid, "direction": "inbound",
            "from": customer or form.get("From"), "to": biz or form.get("To"), "business_number": biz,
            "occurred_at": now_datetime().isoformat(), "agent": agent}
    _post(dict(base, event_id=f"{sid}:voice", event_type="call.initiated"))
    if not agent:  # nobody to ring: record the missed call so it gets a callback owner
        _post(dict(base, event_id=f"{sid}:noagent", event_type="call.ended", status="no-answer"))
        return _xml(tu.reject_twiml("busy"))
    cb = tu.status_url(_base(), direction="inbound", frm=customer or form.get("From"), to=biz or form.get("To"),
                       agent=agent)
    return _xml(tu.inbound_twiml(tu.identity_for(agent), cb, lead,
                                 frappe.db.get_value("Lead", lead, "lead_name") if lead else None))


@frappe.whitelist(allow_guest=True, methods=["POST"])
@frappe.rate_limit(limit=1200, seconds=60)
def status():
    """statusCallback for <Number>/<Client>: feeds the common event pipeline."""
    form = _verified_form()
    if form is None:
        frappe.local.response["http_status_code"] = 403
        return {"ok": False}
    frappe.set_user("Administrator")
    payload = tu.canonical_event(form, frappe.request.args.to_dict())
    if payload:
        _post(payload)
    return {"ok": True}
