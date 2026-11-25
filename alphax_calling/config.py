"""Central settings. Source of truth: the 'AX Calling Settings' form. site_config.json keys remain a fallback."""
import frappe

from alphax_calling.utils import normalize_phone

WEEKENDS = {"Fri-Sat": (4, 5), "Thu-Fri": (3, 4), "Sat-Sun": (5, 6), "Fri only": (4,), "None": ()}
MANUAL, TWILIO, BRIDGE = "Manual (phone app)", "Twilio", "Carrier SIP Bridge"


def _doc():
    try:
        return frappe.get_cached_doc("AX Calling Settings")
    except Exception:  # DocType not migrated yet
        return None


def get_settings():
    c, d = frappe.conf, _doc()

    def pick(field, conf_key, default=None):
        v = d.get(field) if d else None
        return v if v not in (None, "", 0) else c.get(conf_key, default)

    def secret(field):
        return (d.get_password(field, raise_exception=False) if d else None) or None

    cc = str(pick("default_country_code", "alphax_calling_default_country_code", "966"))
    start = (d.call_window_start if d else None) or "09:00"
    end = (d.call_window_end if d else None) or "21:00"
    lines = {}
    for row in (d.get("business_lines") if d else None) or []:
        n = normalize_phone(row.number, cc)
        if n and row.active:
            lines[n] = {"company": row.company, "business_line": row.business_line,
                        "inbound_owner": row.inbound_owner, "caller_id_registered": row.caller_id_registered}
    for n, v in (c.get("alphax_calling_business_lines") or {}).items():
        lines.setdefault(n, v)
    tw_conf = c.get("alphax_calling_twilio") or {}
    twilio = {"account_sid": (d.twilio_account_sid if d else None) or tw_conf.get("account_sid"),
              "auth_token": secret("twilio_auth_token") or tw_conf.get("auth_token"),
              "api_key_sid": (d.twilio_api_key_sid if d else None) or tw_conf.get("api_key_sid"),
              "api_key_secret": secret("twilio_api_key_secret") or tw_conf.get("api_key_secret"),
              "twiml_app_sid": (d.twilio_twiml_app_sid if d else None) or tw_conf.get("twiml_app_sid"),
              "caller_id": (d.twilio_caller_id if d else None) or tw_conf.get("caller_id")}
    webhook_secret = secret("webhook_secret") or c.get("alphax_calling_webhook_secret")
    provider = (d.provider if d and d.provider else None) or (
        TWILIO if tw_conf else BRIDGE if webhook_secret else MANUAL)
    carrier = {k[8:]: (secret(k) if k == "carrier_password" else d.get(k)) for k in (
        "carrier_sip_server", "carrier_sip_port", "carrier_transport", "carrier_auth_mode", "carrier_username",
        "carrier_password", "carrier_outbound_proxy", "carrier_allowed_ips", "carrier_codecs",
        "carrier_max_channels", "carrier_support_contact")} if d else {}
    return frappe._dict(
        enabled=bool(d.enabled) if d else True, provider=provider, default_cc=cc,
        window=f"{start}-{end}" if d else c.get("alphax_calling_call_window") or "09:00-21:00",
        weekend=WEEKENDS.get(d.weekend, (4, 5)) if d and d.weekend else tuple(c.get("alphax_calling_weekend_days") or (4, 5)),
        dnc_field=pick("do_not_call_field", "alphax_calling_do_not_call_field"),
        callback_owner=pick("default_callback_owner", "alphax_calling_default_callback_owner"),
        missed_callback_minutes=int(pick("missed_callback_minutes", "alphax_calling_missed_callback_minutes", 60)),
        retention_days=int(pick("event_retention_days", "alphax_calling_event_retention_days", 180)),
        public_url=pick("public_url", "alphax_calling_public_url"), business_lines=lines,
        webhook_secret=webhook_secret, twilio=twilio, carrier=carrier)
