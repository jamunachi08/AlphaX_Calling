"""Integration tests. Run on a STAGING bench only:
    bench --site <site> run-tests --app alphax_calling --module alphax_calling.tests.test_calling
They create and delete fictional Leads and users. NOT yet executed by the author: treat the first run as part of acceptance.
"""
import json
import time
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from alphax_calling import api, events, utils


def make_lead(mobile, **kw):
    doc = frappe.get_doc(dict(doctype="Lead", first_name="Test", last_name=uuid.uuid4().hex[:6],
                              mobile_no=mobile, **kw)).insert(ignore_permissions=True)
    return doc.name


def post_event(secret, **body):
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    frappe.local.request = frappe._dict(get_data=lambda: raw)
    hdr = {"X-AlphaX-Timestamp": ts, "X-AlphaX-Signature": utils.sign(secret, ts, raw)}
    original = frappe.get_request_header
    frappe.get_request_header = lambda k, d=None: hdr.get(k, d)
    try:
        return events.provider_event()
    finally:
        frappe.get_request_header = original


class TestCalling(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.conf.alphax_calling_webhook_secret = "test-secret"

    def tearDown(self):
        frappe.db.rollback()

    def test_log_call_is_idempotent(self):
        lead, rid = make_lead("0551110001"), str(uuid.uuid4())
        a = api.log_call(lead, rid, "Outbound", "Answered", "Information sent", "x", spoke=1, talk_minutes=2)
        b = api.log_call(lead, rid, "Outbound", "Answered", "Information sent", "x", spoke=1, talk_minutes=2)
        self.assertEqual(a, b)
        self.assertEqual(frappe.db.count("AX Lead Call", {"lead": lead}), 1)

    def test_unanswered_has_zero_talk(self):
        lead = make_lead("0551110002")
        name = api.log_call(lead, str(uuid.uuid4()), "Outbound", "Unanswered", talk_minutes=5)
        self.assertEqual(frappe.db.get_value("AX Lead Call", name, "talk_seconds"), 0)

    def test_callback_needs_future_time_and_creates_one_todo(self):
        lead, rid = make_lead("0551110003"), str(uuid.uuid4())
        with self.assertRaises(frappe.ValidationError):
            api.log_call(lead, str(uuid.uuid4()), "Outbound", "Answered", "Callback requested",
                         due_at=add_to_date(now_datetime(), hours=-1))
        due = add_to_date(now_datetime(), days=1)
        api.log_call(lead, rid, "Outbound", "Answered", "Callback requested", due_at=due)
        api.log_call(lead, rid, "Outbound", "Answered", "Callback requested", due_at=due)
        self.assertEqual(frappe.db.count("ToDo", {"reference_type": "Lead", "reference_name": lead}), 1)

    def test_demo_creates_event(self):
        lead = make_lead("0551110004")
        name = api.log_call(lead, str(uuid.uuid4()), "Outbound", "Answered", "Demo agreed",
                            demo_at=add_to_date(now_datetime(), days=2))
        self.assertTrue(frappe.db.exists("Event", frappe.db.get_value("AX Lead Call", name, "event")))

    def test_dial_attempt_normalises_and_dedupes(self):
        lead = make_lead("0551110005")
        r1 = api.dial_number(lead, "mobile_no", confirmed=1)
        r2 = api.dial_number(lead, "mobile_no", confirmed=1)
        self.assertEqual(r1["number"], "+966551110005")
        self.assertEqual(r1["attempt"], r2["attempt"])

    def test_provider_events_dedupe_and_late(self):
        lead = make_lead("0551110006")
        attempt = api.dial_number(lead, "mobile_no", confirmed=1)["attempt"]
        base = dict(provider="t", account="a", call_id="c1", direction="outbound", client_ref=attempt)
        t = "2026-11-24T10:00:%02d+03:00"
        post_event("test-secret", event_id="e1", event_type="call.answered", occurred_at=t % 8, **base)
        dup = post_event("test-secret", event_id="e1", event_type="call.answered", occurred_at=t % 8, **base)
        self.assertEqual(dup["result"], "Duplicate")
        post_event("test-secret", event_id="e2", event_type="call.ended", occurred_at=t % 38,
                   status="completed", **base)
        late = post_event("test-secret", event_id="e3", event_type="call.ringing", occurred_at=t % 40, **base)
        self.assertEqual(late["result"], "Ignored Late")
        row = frappe.db.get_value("AX Lead Call", attempt, ["call_status", "talk_seconds", "is_final"], as_dict=True)
        self.assertEqual((row.call_status, row.talk_seconds, row.is_final), ("Answered", 30, 1))

    def test_shared_inbound_number_goes_to_review(self):
        make_lead("0551110007"), make_lead("+966 55 111 0007")
        r = post_event("test-secret", event_id="s1", event_type="call.ringing", provider="t", account="a",
                       call_id="c2", direction="inbound", occurred_at="2026-11-24T10:00:00+03:00",
                       **{"from": "+966551110007", "to": "+966112223333"})
        self.assertEqual(frappe.db.get_value("AX Lead Call", r["call"], ["review_status", "lead"], as_dict=True),
                         frappe._dict(review_status="Needs Review", lead=None))

    def test_bad_signature_rejected(self):
        frappe.local.request = frappe._dict(get_data=lambda: b"{}")
        original = frappe.get_request_header
        frappe.get_request_header = lambda k, d=None: {"X-AlphaX-Timestamp": str(int(time.time())),
                                                       "X-AlphaX-Signature": "bad"}.get(k, d)
        try:
            self.assertFalse(events.provider_event()["ok"])
        finally:
            frappe.get_request_header = original


class TestSettings(FrappeTestCase):
    def test_validation_and_readiness(self):
        from alphax_calling import setup
        from alphax_calling.config import get_settings
        doc = frappe.get_doc("AX Calling Settings")
        doc.twilio_account_sid = "XX123"
        with self.assertRaises(frappe.ValidationError):
            doc.save()
        doc = frappe.get_doc("AX Calling Settings")
        doc.provider = "Carrier SIP Bridge"
        doc.append("business_lines", {"number": "011 222 3333", "company": frappe.defaults.get_global_default("company"),
                                      "caller_id_registered": 1, "active": 1})
        doc.save()
        self.assertIn("+966112223333", get_settings().business_lines)
        r = setup.readiness()
        self.assertIn("checks", r)
        self.assertFalse(r["ready"])  # no acceptance evidence yet

    def test_bridge_selftest_rolls_back(self):
        from alphax_calling import setup
        before = frappe.db.count("AX Lead Call")
        steps = setup._bridge_test(frappe._dict(webhook_secret="x" * 64, default_cc="966", business_lines={},
                                                enabled=True, callback_owner=None, missed_callback_minutes=60))
        self.assertEqual(frappe.db.count("AX Lead Call"), before)
        self.assertTrue(steps[-1]["ok"], steps)
