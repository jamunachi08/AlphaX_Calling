"""Pure helpers. No Frappe import, so they can be unit-tested anywhere."""
import hashlib
import hmac
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

NAMESPACE = uuid.UUID("b1f0c6de-3a52-4c0e-9d57-6a1f2c0b7e11")
FINAL_STATUSES = ("Answered", "Unanswered", "Busy", "Failed")
NO_ANSWER_STATUSES = ("Unanswered", "Busy", "Failed")
OUTCOMES = ("", "Callback requested", "Demo agreed", "Information sent", "Wrong number", "No interest")
EVENT_RANK = {"call.initiated": 0, "call.ringing": 1, "call.answered": 2, "call.ended": 3}
LIVE_RANK = {"Dialing": 0, "Ringing": 1, "Answered": 2}
_STATUS_MAP = {
    "completed": "Answered", "answered": "Answered", "busy": "Busy",
    "no-answer": "Unanswered", "unanswered": "Unanswered", "cancelled": "Unanswered",
    "canceled": "Unanswered", "missed": "Unanswered", "declined": "Unanswered",
    "rejected": "Unanswered", "failed": "Failed", "error": "Failed",
}
_DIGITS = str.maketrans(
    "".join(chr(c) for c in list(range(0x660, 0x66A)) + list(range(0x6F0, 0x6FA))), "0123456789" * 2)


def normalize_phone(raw, default_cc="966"):
    """Return E.164 (+9665XXXXXXXX) or '' when the value is not a plausible number.

    Handles Arabic-Indic digits, 05XXXXXXXX, 5XXXXXXXX, 00966..., +966 (0) 5...
    """
    if not raw:
        return ""
    s = str(raw).translate(_DIGITS).strip()
    plus = s.startswith("+")
    s = re.sub(r"\D", "", s)
    if not s:
        return ""
    if plus:
        digits = s
    elif s.startswith("00"):
        digits = s[2:]
    elif s.startswith("0") and default_cc:
        digits = default_cc + s[1:]
    elif default_cc == "966" and re.fullmatch(r"5\d{8}", s):
        digits = "966" + s
    else:
        digits = s
    if default_cc == "966" and digits.startswith("9660"):
        digits = "966" + digits[4:]
    return "+" + digits if re.fullmatch(r"[1-9]\d{7,14}", digits) else ""


def is_saudi(number):
    return bool(number) and number.startswith("+966")


def next_working_slot(now, hour=10, weekend=(4, 5)):
    """Next working day at `hour`:00. Default weekend is Friday/Saturday (Python weekday 4, 5)."""
    d = (now + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while d.weekday() in weekend:
        d += timedelta(days=1)
    return d


def in_call_window(now, window="09:00-21:00", weekend=(4, 5)):
    """None when fine, else 'weekend' or 'hours'. Advisory only."""
    if now.weekday() in weekend:
        return "weekend"
    try:
        a, b = window.split("-")
        start = tuple(int(x) for x in a.split(":"))
        end = tuple(int(x) for x in b.split(":"))
        if not (start <= (now.hour, now.minute) < end):
            return "hours"
    except (ValueError, AttributeError):
        pass
    return None


def streak(statuses):
    """Leading run of no-answer results in a newest-first list of final statuses."""
    n = 0
    for s in statuses:
        if s in NO_ANSWER_STATUSES:
            n += 1
        else:
            break
    return n


def advice_keys(attempts, no_answer_streak, overdue_open, last_outcome, has_open_callback):
    keys = []
    if overdue_open:
        keys.append("overdue")
    if no_answer_streak >= 5:
        keys.append("stop_calling")
    elif no_answer_streak >= 3:
        keys.append("change_channel")
    if last_outcome == "Wrong number":
        keys.append("verify_number")
    elif last_outcome == "Information sent" and not has_open_callback:
        keys.append("schedule_followup")
    elif last_outcome == "Demo agreed":
        keys.append("confirm_demo")
    if not attempts:
        keys.append("first_call")
    return keys


def map_status(raw):
    if not raw:
        return None
    return _STATUS_MAP.get(re.sub(r"[\s_]+", "-", str(raw).strip().lower()))


def is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def call_name_for(provider_key):
    return str(uuid.uuid5(NAMESPACE, "call:" + provider_key))


def event_name_for(provider, account, event_id):
    return str(uuid.uuid5(NAMESPACE, f"event:{provider}:{account}:{event_id}"))


def sign(secret, timestamp, body):
    return hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()


def verify_signature(secret, timestamp, body, signature, now=None, tolerance=300):
    try:
        ts = int(str(timestamp).strip())
    except (TypeError, ValueError):
        return False
    if abs((time.time() if now is None else now) - ts) > tolerance or not signature:
        return False
    return hmac.compare_digest(sign(secret, str(timestamp).strip(), body), str(signature).strip().lower())


def parse_iso(value, tz_name="Asia/Riyadh"):
    """Parse ISO-8601 / epoch into a naive datetime in the site time zone."""
    from zoneinfo import ZoneInfo
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)


def _ended(current, occurred, mapped, duration, owns_status):
    answered_at = current.get("answered_at")
    try:
        duration = None if duration in (None, "") else max(0, int(float(duration)))
    except (TypeError, ValueError):
        duration = None
    status = mapped or ("Answered" if answered_at or (duration or 0) > 0 else "Unanswered")
    u = {"ended_at": occurred, "provider_status": status}
    if status == "Answered":
        if duration is None and answered_at:
            duration = max(0, int((occurred - answered_at).total_seconds()))
        if not answered_at and duration:
            u["answered_at"] = occurred - timedelta(seconds=duration)
    if owns_status:
        u.update(call_status=status, is_final=1, final_source="Provider",
                 talk_seconds=(duration or 0) if status == "Answered" else 0)
    else:  # the executive closed the record first: keep their status, flag a mismatch
        if status != current.get("call_status"):
            u["reconcile_flag"] = 1
        if status == "Answered" and current.get("call_status") == "Answered" and duration is not None:
            u["talk_seconds"] = duration
    return u


def plan_event(current, event_type, occurred, provider_status=None, duration=None):
    """Decide what a provider event may change. Returns (action, updates).

    action: 'apply' (normal progress), 'attach' (provider data added to a record the
    executive already closed) or 'late' (ignored: duplicate, out of order, or after the end).
    """
    mapped = map_status(provider_status)
    if current.get("final_source") == "Provider":
        return "late", {}
    if current.get("is_final"):
        if event_type != "call.ended" or current.get("ended_at"):
            return "late", {}
        return "attach", _ended(current, occurred, mapped, duration, False)
    if EVENT_RANK[event_type] < LIVE_RANK.get(current.get("call_status") or "Dialing", 0):
        return "late", {}
    started = current.get("started_at") or occurred
    if event_type == "call.initiated":
        return "apply", {"started_at": started}
    if event_type == "call.ringing":
        return "apply", {"started_at": started, "call_status": "Ringing"}
    if event_type == "call.answered":
        return "apply", {"started_at": started, "call_status": "Answered",
                         "answered_at": current.get("answered_at") or occurred}
    return "apply", _ended(current, occurred, mapped, duration, True)
