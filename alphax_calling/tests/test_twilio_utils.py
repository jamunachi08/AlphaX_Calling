import base64
import hashlib
import hmac
import json
import unittest

from alphax_calling import twilio_utils as t


class TestTwilio(unittest.TestCase):
    def test_signature_matches_twilio_documented_example(self):
        params = {"CallSid": "CA1234567890ABCDE", "Caller": "+14158675310", "Digits": "1234",
                  "From": "+14158675310", "To": "+18005551212"}
        self.assertEqual(t.twilio_signature("https://mycompany.com/myapp.php?foo=1&bar=2", params, "12345"),
                         "GvWf1cFY/Q7PnoempGyD5oXAezc=")

    def test_valid_signature_rejects_tampering(self):
        p = {"a": "1"}
        sig = t.twilio_signature("https://x/y", p, "tok")
        self.assertTrue(t.valid_signature("https://x/y", p, "tok", sig))
        self.assertFalse(t.valid_signature("https://x/y", {"a": "2"}, "tok", sig))
        self.assertFalse(t.valid_signature("https://x/y", p, "tok", None))

    def test_identity_roundtrip(self):
        for u in ("a.b+c@alphax.sa", "Administrator"):
            i = t.identity_for(u)
            self.assertTrue(i.replace("_", "").isalnum())
            self.assertEqual(t.user_for("client:" + i), u)
        self.assertIsNone(t.user_for("garbage"))

    def test_access_token(self):
        tok = t.build_access_token("ACx", "SKy", "secret", "u1", "APz", now=1000)
        h, p, s = tok.split(".")
        pad = lambda x: x + "=" * (-len(x) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad(p)))
        self.assertEqual((payload["iss"], payload["sub"], payload["exp"]), ("SKy", "ACx", 4600))
        self.assertEqual(payload["grants"]["voice"]["outgoing"]["application_sid"], "APz")
        expect = base64.urlsafe_b64encode(hmac.new(b"secret", f"{h}.{p}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        self.assertEqual(s, expect)

    def test_twiml_escaping(self):
        x = t.outbound_twiml("+966551234567", "+15005550006", "https://s/a?x=1&y=2")
        self.assertIn("x=1&amp;y=2", x)
        self.assertIn("<Number", x)
        self.assertIn('<Parameter name="lead" value="LEAD-1"/>', t.inbound_twiml("u1", "https://s", "LEAD-1", "A&B"))
        self.assertIn("A&amp;B", t.inbound_twiml("u1", "https://s", "LEAD-1", "A&B"))

    def test_canonical_event(self):
        q = {"direction": "outbound", "frm": "+15005550006", "to": "+966551234567", "ref": "r1", "agent": "a@b.c"}
        f = {"CallSid": "CAchild", "ParentCallSid": "CAparent", "CallStatus": "completed", "CallDuration": "42",
             "AccountSid": "ACx", "Timestamp": "Wed, 25 Nov 2026 07:00:00 +0000"}
        e = t.canonical_event(f, q)
        self.assertEqual((e["event_type"], e["status"], e["call_id"], e["duration_seconds"]),
                         ("call.ended", "completed", "CAparent", "42"))
        self.assertEqual(e["occurred_at"], "2026-11-25T07:00:00+00:00")
        self.assertEqual(t.canonical_event({**f, "CallStatus": "in-progress"}, q)["event_type"], "call.answered")
        self.assertEqual(t.canonical_event({**f, "CallStatus": "busy"}, q)["status"], "busy")
        self.assertIsNone(t.canonical_event({**f, "CallStatus": "weird"}, q))
        self.assertIsNone(t.canonical_event({}, q))
        self.assertNotEqual(t.canonical_event({**f, "CallStatus": "ringing"}, q)["event_id"], e["event_id"])


if __name__ == "__main__":
    unittest.main()
