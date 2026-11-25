"""Pure Twilio helpers (no Frappe import): access tokens, request signatures, TwiML, status mapping."""
import base64
import hashlib
import hmac
import json
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.sax.saxutils import escape, quoteattr

STATUS_EVENTS = "initiated ringing answered completed"
_LIVE = {"initiated": "call.initiated", "ringing": "call.ringing", "in-progress": "call.answered",
         "answered": "call.answered"}
_TERMINAL = ("completed", "busy", "no-answer", "failed", "canceled")


def identity_for(user):
    """Twilio client identities allow only letters, digits and underscore: hex-encode the user id."""
    return "u" + user.encode().hex()


def user_for(identity):
    identity = (identity or "").replace("client:", "", 1)
    try:
        return bytes.fromhex(identity[1:]).decode() if identity.startswith("u") else None
    except ValueError:
        return None


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def build_access_token(account_sid, api_key_sid, api_key_secret, identity, app_sid, ttl=3600, now=None):
    now = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT", "cty": "twilio-fpa;v=1"}
    payload = {"jti": f"{api_key_sid}-{now}", "iss": api_key_sid, "sub": account_sid, "exp": now + ttl,
               "grants": {"identity": identity, "voice": {"incoming": {"allow": True},
                                                            "outgoing": {"application_sid": app_sid}}}}
    signing = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(api_key_secret.encode(), signing.encode(), hashlib.sha256).digest()
    return signing + "." + _b64(sig)


def twilio_signature(url, params, auth_token):
    data = url + "".join(k + str(params[k]) for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()).decode()


def valid_signature(url, params, auth_token, signature):
    return bool(signature and auth_token) and hmac.compare_digest(
        twilio_signature(url, params, auth_token), str(signature))


def status_url(base, **query):
    return base.rstrip("/") + "/api/method/alphax_calling.twilio_adapter.status?" + urlencode(
        {k: v for k, v in query.items() if v not in (None, "")})


def outbound_twiml(number, caller_id, callback_url, timeout=45):
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Dial callerId={quoteattr(caller_id)} answerOnBridge="true" timeout="{int(timeout)}">'
            f'<Number statusCallbackEvent="{STATUS_EVENTS}" statusCallbackMethod="POST" '
            f'statusCallback={quoteattr(callback_url)}>{escape(number)}</Number></Dial></Response>')


def inbound_twiml(identity, callback_url, lead=None, lead_name=None, timeout=25):
    params = "".join(f"<Parameter name={quoteattr(k)} value={quoteattr(v)}/>"
                     for k, v in (("lead", lead), ("lead_name", lead_name)) if v)
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Dial answerOnBridge="true" timeout="{int(timeout)}">'
            f'<Client statusCallbackEvent="{STATUS_EVENTS}" statusCallbackMethod="POST" '
            f'statusCallback={quoteattr(callback_url)}>{escape(identity)}{params}</Client></Dial></Response>')


def reject_twiml(reason="rejected"):
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Reject reason={quoteattr(reason)}/></Response>'


def canonical_event(form, query):
    """Translate a Twilio status callback (+ our signed query string) into the provider-event payload."""
    status = (form.get("CallStatus") or "").lower()
    sid = form.get("CallSid") or ""
    if not sid:
        return None
    if status in _LIVE:
        etype, pstatus = _LIVE[status], None
    elif status in _TERMINAL:
        etype, pstatus = "call.ended", status
    else:
        return None
    occurred = None
    try:
        occurred = parsedate_to_datetime(form.get("Timestamp")).isoformat()
    except (TypeError, ValueError):
        pass
    return {"provider": "twilio", "account": form.get("AccountSid") or "", "event_id": f"{sid}:{status}",
            "event_type": etype, "call_id": form.get("ParentCallSid") or sid, "occurred_at": occurred,
            "direction": query.get("direction"), "from": query.get("frm"), "to": query.get("to"),
            "business_number": query.get("biz"), "client_ref": query.get("ref"), "status": pstatus,
            "duration_seconds": form.get("CallDuration"), "agent": query.get("agent")}
