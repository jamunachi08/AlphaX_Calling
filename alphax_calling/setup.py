"""Setup, readiness, connection tests and release gate for AX Calling Settings."""
import json
import secrets
import sys
import uuid

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from alphax_calling import utils
from alphax_calling.config import BRIDGE, MANUAL, TWILIO, get_settings
from alphax_calling.guide import ACCEPTANCE, get_guide, urls

DOC = "AX Calling Settings"


# ---------------------------------------------------------------- post-migrate
def after_migrate():
    try:
        ensure_defaults()
    except Exception:
        frappe.log_error(title="AlphaX Calling: default settings failed")
    try:
        ensure_workspace()
    except Exception:
        frappe.log_error(title="AlphaX Calling: workspace creation failed")


def ensure_defaults():
    doc = frappe.get_doc(DOC)
    have = {r.test_name for r in doc.get("acceptance_tests")}
    for name, cond in ACCEPTANCE:
        if name not in have:
            doc.append("acceptance_tests", {"test_name": name, "pass_condition": cond, "result": "Not run"})
    doc.flags.ignore_permissions = True
    doc.save()


def ensure_workspace():
    if frappe.db.exists("Workspace", "AlphaX Calling"):
        return
    items = [("Settings", "DocType", "AX Calling Settings", ""), ("Callback Queue", "Report", "AX Callback Queue", ""),
             ("Executive Calls", "Report", "AX Executive Calls", ""),
             ("Review Queue", "DocType", "AX Lead Call", json.dumps({"review_status": "Needs Review"})),
             ("Provider Events", "DocType", "AX Call Event", "")]
    content = [{"id": "ax_h", "type": "header", "data": {"text": '<span class="h4"><b>AlphaX Calling</b></span>', "col": 12}}]
    content += [{"id": f"ax_{i}", "type": "shortcut", "data": {"shortcut_name": lbl, "col": 3}}
                for i, (lbl, *_rest) in enumerate(items)]
    frappe.get_doc({
        "doctype": "Workspace", "name": "AlphaX Calling", "label": "AlphaX Calling", "title": "AlphaX Calling",
        "module": "AlphaX Calling", "public": 1, "is_hidden": 0, "content": json.dumps(content),
        "shortcuts": [{"label": lbl, "type": typ, "link_to": link, "doc_view": "List" if typ == "DocType" else "",
                       "stats_filter": flt or None} for lbl, typ, link, flt in items]}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- helpers
def _admin():
    frappe.only_for("System Manager")


def _save_single(fields):
    doc = frappe.get_doc(DOC)
    doc.update(fields)
    doc.flags.ignore_permissions = True
    doc.save()
    return doc


@frappe.whitelist()
def get_urls():
    _admin()
    return urls()


@frappe.whitelist()
def guide():
    _admin()
    return get_guide()


@frappe.whitelist()
def capture_versions():
    _admin()
    out = [f"frappe {frappe.__version__}"]
    try:
        out.append("erpnext " + frappe.get_attr("erpnext.__version__"))
    except Exception:
        out.append("erpnext (not detected)")
    out.append("alphax_calling " + frappe.get_attr("alphax_calling.__version__"))
    out.append("python " + sys.version.split()[0])
    out.append("site time zone " + frappe.utils.get_system_timezone())
    text = "\n".join(out) + "\ncaptured " + str(now_datetime())[:16]
    _save_single({"tested_versions": text})
    return text


@frappe.whitelist(methods=["POST"])
def generate_secret():
    """Create and store a new signing secret. Returned once; store it in the bridge's secret manager."""
    _admin()
    value = secrets.token_hex(32)
    _save_single({"webhook_secret": value})
    return value


# ---------------------------------------------------------------- readiness
def _check(key, label, status, detail, fix=""):
    return {"key": key, "label": label, "status": status, "detail": detail, "fix": fix}


@frappe.whitelist()
def readiness():
    _admin()
    s, d = get_settings(), frappe.get_doc(DOC)
    c = []
    try:
        from frappe.utils.scheduler import is_scheduler_disabled
        sched_off = is_scheduler_disabled(verbose=False)
    except Exception:
        sched_off = bool(frappe.conf.get("pause_scheduler"))
    c.append(_check("scheduler", _("Scheduler"), "fail" if sched_off else "ok",
                    _("Scheduler is off.") if sched_off else _("Scheduler is running."),
                    _("Run: bench --site SITE enable-scheduler. Overdue alerts and reconciliation depend on it.")))
    https = (s.public_url or frappe.utils.get_url()).startswith("https://")
    c.append(_check("https", _("HTTPS"), "ok" if https else "fail",
                    _("Site address is HTTPS.") if https else _("The public address is not HTTPS."),
                    _("Browsers need HTTPS for the microphone, and providers need it for webhooks. Set host_name or Public HTTPS URL.")))
    tz = frappe.utils.get_system_timezone()
    c.append(_check("tz", _("Time zone"), "ok" if tz == "Asia/Riyadh" else "warn", tz,
                    _("Set System Settings to Asia/Riyadh so call times, windows and due dates match Saudi working hours.")))
    c.append(_check("enabled", _("Calling enabled"), "ok" if s.enabled else "fail",
                    _("Enabled.") if s.enabled else _("The master switch is off."), _("Tick Calling enabled.")))

    prov = s.provider
    if prov == MANUAL:
        c.append(_check("provider", _("Provider"), "warn", _("Manual mode: no audio, no carrier events."),
                        _("Choose Twilio for the pilot or Carrier SIP Bridge for production.")))
    elif prov == TWILIO:
        missing = [k for k, v in s.twilio.items() if not v]
        c.append(_check("provider", _("Twilio settings"), "fail" if missing else "ok",
                        _("Missing: {0}").format(", ".join(missing)) if missing else _("All Twilio fields are set."),
                        _("Fill the Twilio section. See the guide, step 2.")))
        c.append(_check("pilot_only", _("Production suitability"), "warn",
                        _("Twilio trial cannot present a Saudi business number and only reaches verified numbers."),
                        _("Use Carrier SIP Bridge with a CST-licensed carrier for production.")))
    else:
        cr = s.carrier
        missing = [lbl for lbl, v in (("SIP server", cr.get("sip_server")), ("authentication", cr.get("auth_mode")),
                                      ("signing secret", s.webhook_secret)) if not v]
        c.append(_check("provider", _("Carrier SIP settings"), "fail" if missing else "ok",
                        _("Missing: {0}").format(", ".join(missing)) if missing else _("Carrier SIP details are set."),
                        _("Fill the Carrier SIP Bridge section and press Generate secret.")))
        if s.webhook_secret and len(s.webhook_secret) < 32:
            c.append(_check("secret", _("Signing secret"), "warn", _("The secret is short."), _("Press Generate secret.")))

    if prov != MANUAL:
        rows = d.get("business_lines")
        active = [r for r in rows if r.active]
        bad = [r.number for r in active if not (r.company and r.caller_id_registered)]
        c.append(_check("lines", _("Business numbers"), "fail" if not active else ("warn" if bad else "ok"),
                        _("No active business number.") if not active else (
                            _("Missing company or caller-ID registration: {0}").format(", ".join(bad)) if bad
                            else _("{0} active number(s).").format(len(active))),
                        _("Add the number with its company and confirm the caller ID is registered to that company.")))
    owner = s.callback_owner
    ok_owner = bool(owner and frappe.db.get_value("User", owner, "enabled"))
    c.append(_check("owner", _("Default callback owner"), "ok" if ok_owner else "warn",
                    owner if ok_owner else _("Not set."),
                    _("Needed so a missed call never lacks an owner when the Lead owner is unavailable.")))

    for key, label, ok in (("carrier_name", _("Licensed carrier recorded"), d.carrier_name and d.contract_ref),
                           ("region", _("Hosting region recorded"), d.data_region),
                           ("retention", _("Retention confirmed"), d.retention_confirmed),
                           ("privacy", _("Privacy / PDPL review"), d.privacy_notice_confirmed)):
        c.append(_check(key, label, "ok" if ok else ("warn" if prov == MANUAL else "fail"),
                        _("Recorded.") if ok else _("Not recorded."), _("Complete the Carrier, compliance and data section.")))
    c.append(_check("recording", _("Recording"), "ok", _("Recording is disabled (pilot requirement)."), ""))

    tested = d.last_test_at
    c.append(_check("tested", _("Connection test"), "ok" if tested and "FAIL" not in (d.last_test_result or "") else "warn",
                    (d.last_test_result or _("Never run."))[:300], _("Press Test connection.")))
    if prov != MANUAL:
        since = add_to_date(now_datetime(), hours=-24)
        n = frappe.db.count("AX Call Event", {"creation": [">", since]})
        late = frappe.db.count("AX Call Event", {"creation": [">", since], "result": "Ignored Late"})
        total = frappe.db.count("AX Call Event")
        c.append(_check("events", _("Provider events"), "ok" if n else "warn",
                        _("{0} events in 24 h ({1} ignored as late).").format(n, late) if total else _("No event received yet."),
                        _("Place a test call, or use tools/alphax_send_event.py.")))
    review = frappe.db.count("AX Lead Call", {"review_status": "Needs Review"})
    recon = frappe.db.count("AX Lead Call", {"reconcile_flag": 1})
    c.append(_check("review", _("Review queue"), "ok" if not review else "warn",
                    _("{0} call(s) need review.").format(review), _("A Sales Manager links them from the AX Lead Call list.")))
    c.append(_check("recon", _("Reconciliation"), "ok" if not recon else "warn",
                    _("{0} call(s) flagged.").format(recon), _("Compare with the provider's call-detail records.")))

    res = [r.result for r in d.get("acceptance_tests")]
    passed = res.count("Pass")
    c.append(_check("acceptance", _("Acceptance tests"), "fail" if "Fail" in res else ("ok" if passed == len(res) and res else "warn"),
                    _("{0} of {1} passed.").format(passed, len(res)), _("Run the tests and record evidence.")))
    c.append(_check("approved", _("Pilot approval"), "ok" if d.approved_by else "warn",
                    _("Approved by {0}.").format(d.approved_by) if d.approved_by else _("Not yet approved."), ""))
    summary = {k: sum(x["status"] == k for x in c) for k in ("ok", "warn", "fail")}
    return {"checks": c, "summary": summary, "urls": urls(),
            "ready": summary["fail"] == 0 and bool(res) and passed == len(res)}


@frappe.whitelist(methods=["POST"])
def approve_pilot():
    _admin()
    r = readiness()
    if not r["ready"]:
        frappe.throw(_("Clear every failed check and pass all acceptance tests before approving."))
    _save_single({"approved_by": frappe.session.user, "approved_on": now_datetime()})
    return True


# ---------------------------------------------------------------- connection tests
def _twilio_test(s):
    import requests
    t, steps = s.twilio, []

    def step(name, ok, detail):
        steps.append({"step": name, "ok": bool(ok), "detail": detail})

    missing = [k for k, v in t.items() if not v]
    if missing:
        step("Settings", False, "Missing: " + ", ".join(missing))
        return steps
    base = f"https://api.twilio.com/2010-04-01/Accounts/{t['account_sid']}"
    try:
        r = requests.get(base + ".json", auth=(t["account_sid"], t["auth_token"]), timeout=15)
        j = r.json() if r.ok else {}
        step("Account and auth token", r.ok and j.get("status") == "active",
             f"HTTP {r.status_code}; status {j.get('status')}; type {j.get('type')}")
        r = requests.get(f"{base}/Applications/{t['twiml_app_sid']}.json", auth=(t["api_key_sid"], t["api_key_secret"]), timeout=15)
        j = r.json() if r.ok else {}
        want = urls(s.public_url)["twilio_voice"]
        step("API key and TwiML App", r.ok, f"HTTP {r.status_code}")
        if r.ok:
            step("TwiML Voice URL", j.get("voice_url") == want and (j.get("voice_method") or "").upper() == "POST",
                 f"is {j.get('voice_url')} {j.get('voice_method')}; expected {want} POST")
        num = t["caller_id"]
        found = False
        for kind in ("IncomingPhoneNumbers", "OutgoingCallerIds"):
            r = requests.get(f"{base}/{kind}.json", params={"PhoneNumber": num}, auth=(t["account_sid"], t["auth_token"]), timeout=15)
            found = found or (r.ok and bool(r.json().get(
                "incoming_phone_numbers" if kind == "IncomingPhoneNumbers" else "outgoing_caller_ids")))
        step("Caller ID is owned or verified", found, num)
    except requests.RequestException as e:
        step("Network", False, type(e).__name__)
    return steps


def _bridge_test(s):
    steps = []
    steps.append({"step": "Signing secret", "ok": bool(s.webhook_secret) and len(s.webhook_secret) >= 32,
                  "detail": "set and long enough" if s.webhook_secret else "not set"})
    ts, body = "1700000000", b"{}"
    steps.append({"step": "Signature round-trip", "ok": utils.verify_signature(
        s.webhook_secret or "x", ts, body, utils.sign(s.webhook_secret or "x", ts, body), now=1700000001), "detail": ""})
    from alphax_calling import events
    frappe.db.savepoint("ax_selftest")
    try:
        res = events._process({"provider": "selftest", "event_id": uuid.uuid4().hex, "call_id": uuid.uuid4().hex,
                               "event_type": "call.ringing", "direction": "inbound", "from": "+966000000000",
                               "to": "+966000000001", "occurred_at": now_datetime().isoformat()}, s)
        steps.append({"step": "Event pipeline (rolled back)", "ok": res.get("result") == "Applied", "detail": str(res.get("result"))})
    except Exception as e:
        steps.append({"step": "Event pipeline", "ok": False, "detail": f"{type(e).__name__}: {e}"})
    finally:
        frappe.db.rollback(save_point="ax_selftest")
    return steps


@frappe.whitelist(methods=["POST"])
def test_connection():
    _admin()
    s = get_settings()
    if s.provider == TWILIO:
        steps = _twilio_test(s)
    elif s.provider == BRIDGE:
        steps = _bridge_test(s)
    else:
        steps = [{"step": "Manual mode", "ok": True, "detail": "Nothing to test; dialing uses tel: links."}]
    ok = all(x["ok"] for x in steps)
    summary = ("OK" if ok else "FAIL") + " · " + "; ".join(
        f"{x['step']}: {'ok' if x['ok'] else 'FAIL ' + x['detail']}" for x in steps)
    frappe.db.set_single_value(DOC, "last_test_at", now_datetime())
    frappe.db.set_single_value(DOC, "last_test_result", summary[:1000])
    return {"ok": ok, "steps": steps}


# ---------------------------------------------------------------- bridge pulls its settings from here
@frappe.whitelist(allow_guest=True, methods=["GET"])
@frappe.rate_limit(limit=60, seconds=60)
def bridge_config():
    s = get_settings()
    if not s.webhook_secret or not utils.verify_signature(
            s.webhook_secret, frappe.get_request_header("X-AlphaX-Timestamp"), b"",
            frappe.get_request_header("X-AlphaX-Signature")):
        frappe.local.response["http_status_code"] = 401
        return {"ok": False}
    return {"ok": True, "provider": s.provider, "carrier": s.carrier, "default_country_code": s.default_cc,
            "business_lines": s.business_lines, "events_url": urls(s.public_url)["provider_events"]}
