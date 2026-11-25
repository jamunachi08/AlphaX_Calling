#!/usr/bin/env python3
"""Fetch the carrier/SIP settings entered in AlphaX Calling Settings (signed GET). Standard library only.

  export ALPHAX_URL=https://crm.example.com ALPHAX_SECRET=...
  python3 alphax_fetch_config.py > bridge_config.json     # contains the SIP password: protect the file
"""
import hashlib
import hmac
import os
import sys
import time
import urllib.error
import urllib.request


def main():
    url, secret = os.environ.get("ALPHAX_URL"), os.environ.get("ALPHAX_SECRET")
    if not url or not secret:
        sys.exit("Set ALPHAX_URL and ALPHAX_SECRET.")
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b".", hashlib.sha256).hexdigest()
    req = urllib.request.Request(url.rstrip("/") + "/api/method/alphax_calling.setup.bridge_config",
                                 headers={"X-AlphaX-Timestamp": ts, "X-AlphaX-Signature": sig})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")


if __name__ == "__main__":
    main()
