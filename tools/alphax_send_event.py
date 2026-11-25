#!/usr/bin/env python3
"""Send a signed test event to AlphaX Calling. Standard library only.

Examples
  export ALPHAX_URL=https://crm.example.com ALPHAX_SECRET=...        # secret from Settings > Generate secret
  # whole inbound call from a number, answered, 42 s
  python3 alphax_send_event.py scenario inbound-answered --from +966551234567 --to +966112223333 --agent user@example.com
  python3 alphax_send_event.py scenario outbound-busy --to +966551234567 --ref <attempt-id>
  python3 alphax_send_event.py scenario inbound-missed --from +966551234567 --to +966112223333
  python3 alphax_send_event.py replay --event-id e1 --call-id c1 --type call.answered   # run twice: second is Duplicate
Scenarios: inbound-answered, inbound-missed, outbound-answered, outbound-busy, outbound-noanswer
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

PATH = "/api/method/alphax_calling.events.provider_event"


def sign(secret, timestamp, body):
    return hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()


def post(url, secret, payload):
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    req = urllib.request.Request(url.rstrip("/") + PATH, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-AlphaX-Timestamp": ts, "X-AlphaX-Signature": sign(secret, ts, body)})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def iso(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()


def scenario(name, a):
    call = a.call_id or "t-" + uuid.uuid4().hex[:12]
    inbound = name.startswith("inbound")
    base = dict(provider=a.provider, account=a.account, call_id=call, direction="inbound" if inbound else "outbound",
                **{"from": a.frm if inbound else a.business, "to": a.business if inbound else a.to}, business_number=a.business)
    if a.ref:
        base["client_ref"] = a.ref
    if a.agent:
        base["agent"] = a.agent
    seq = [("call.initiated", 0, None, None), ("call.ringing", 2, None, None)]
    if name.endswith("answered"):
        seq += [("call.answered", 8, None, None), ("call.ended", 50, "completed", 42)]
    else:
        seq += [("call.ended", 30, {"missed": "no-answer", "busy": "busy", "noanswer": "no-answer"}[name.split("-")[1]], 0)]
    for i, (et, off, status, dur) in enumerate(seq):
        p = dict(base, event_id=f"{call}-{i}-{et}", event_type=et, occurred_at=iso(off))
        if status:
            p.update(status=status, duration_seconds=dur)
        print(et, *post(a.url, a.secret, p))
    print("call_id:", call)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["scenario", "replay"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--url", default=os.environ.get("ALPHAX_URL"))
    ap.add_argument("--secret", default=os.environ.get("ALPHAX_SECRET"))
    ap.add_argument("--provider", default="testbridge")
    ap.add_argument("--account", default="acct")
    ap.add_argument("--call-id")
    ap.add_argument("--from", dest="frm", default="+966551234567")
    ap.add_argument("--to", default="+966551234567")
    ap.add_argument("--business", default="+966112223333")
    ap.add_argument("--agent")
    ap.add_argument("--ref")
    ap.add_argument("--event-id")
    ap.add_argument("--type", default="call.ringing")
    a = ap.parse_args()
    if not a.url or not a.secret:
        sys.exit("Set ALPHAX_URL and ALPHAX_SECRET (or --url/--secret).")
    if a.mode == "scenario":
        if a.name not in ("inbound-answered", "inbound-missed", "outbound-answered", "outbound-busy", "outbound-noanswer"):
            sys.exit("Unknown scenario. See --help.")
        scenario(a.name, a)
    else:
        p = dict(provider=a.provider, account=a.account, call_id=a.call_id or "replay-call", event_id=a.event_id or "replay-evt",
                 event_type=a.type, occurred_at=iso(), direction="inbound", **{"from": a.frm, "to": a.business})
        print(*post(a.url, a.secret, p))


if __name__ == "__main__":
    main()
