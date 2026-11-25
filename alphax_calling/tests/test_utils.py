"""Pure-logic tests. Run anywhere:  python -m unittest alphax_calling.tests.test_utils"""
import time
import unittest
from datetime import datetime

from alphax_calling import utils as u


class TestPhone(unittest.TestCase):
    def test_saudi_formats(self):
        for raw in ("0551234567", "+966 55 123 4567", "00966551234567", "551234567",
                    "+966 (0) 55 123 4567", "966551234567",
                    "\u0660\u0665\u0665\u0661\u0662\u0663\u0664\u0665\u0666\u0667"):
            self.assertEqual(u.normalize_phone(raw), "+966551234567", raw)

    def test_landline_and_invalid(self):
        self.assertEqual(u.normalize_phone("011 234 5678"), "+966112345678")
        self.assertEqual(u.normalize_phone("12"), "")
        self.assertEqual(u.normalize_phone(""), "")
        self.assertEqual(u.normalize_phone("abc"), "")

    def test_foreign(self):
        self.assertEqual(u.normalize_phone("+1 415 555 2671"), "+14155552671")
        self.assertFalse(u.is_saudi("+14155552671"))


class TestScheduling(unittest.TestCase):
    def test_weekend_skip(self):  # Thu 26 Nov 2026 -> Fri/Sat skipped -> Sun 29 Nov
        self.assertEqual(u.next_working_slot(datetime(2026, 11, 26, 15)), datetime(2026, 11, 29, 10))
        self.assertEqual(u.next_working_slot(datetime(2026, 11, 25, 15)), datetime(2026, 11, 26, 10))

    def test_window(self):
        self.assertEqual(u.in_call_window(datetime(2026, 11, 27, 11)), "weekend")  # Friday
        self.assertEqual(u.in_call_window(datetime(2026, 11, 25, 22)), "hours")
        self.assertIsNone(u.in_call_window(datetime(2026, 11, 25, 11)))


class TestAdvice(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(u.streak(["Busy", "Unanswered", "Answered", "Failed"]), 2)
        self.assertIn("stop_calling", u.advice_keys(6, 5, 0, "", False))
        self.assertIn("change_channel", u.advice_keys(3, 3, 0, "", False))
        self.assertIn("overdue", u.advice_keys(3, 0, 1, "", True))
        self.assertEqual(u.advice_keys(0, 0, 0, "", False), ["first_call"])


class TestSignature(unittest.TestCase):
    def test_roundtrip_and_tamper(self):
        body, ts = b'{"a":1}', str(int(time.time()))
        sig = u.sign("s3cret", ts, body)
        self.assertTrue(u.verify_signature("s3cret", ts, body, sig))
        self.assertFalse(u.verify_signature("s3cret", ts, b'{"a":2}', sig))
        self.assertFalse(u.verify_signature("other", ts, body, sig))
        old = str(int(time.time()) - 4000)
        self.assertFalse(u.verify_signature("s3cret", old, body, u.sign("s3cret", old, body)))
        self.assertFalse(u.verify_signature("s3cret", "x", body, sig))
        self.assertFalse(u.verify_signature("s3cret", ts, body, ""))


class TestIds(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(u.call_name_for("p:a:1"), u.call_name_for("p:a:1"))
        self.assertNotEqual(u.call_name_for("p:a:1"), u.call_name_for("p:a:2"))
        self.assertTrue(u.is_uuid(u.event_name_for("p", "a", "e1")))
        self.assertFalse(u.is_uuid("nope"))


class TestEvents(unittest.TestCase):
    def t(self, s):
        return datetime(2026, 11, 24, 10, 0, s)

    def run_seq(self, events, current=None):
        cur = dict(current or {"call_status": "Dialing", "is_final": 0})
        actions = []
        for et, sec, status, dur in events:
            a, upd = u.plan_event(cur, et, self.t(sec), status, dur)
            actions.append(a)
            cur.update(upd)
        return actions, cur

    def test_answered_flow(self):
        acts, c = self.run_seq([("call.initiated", 0, None, None), ("call.ringing", 2, None, None),
                                ("call.answered", 8, None, None), ("call.ended", 38, "completed", None)])
        self.assertEqual(acts, ["apply"] * 4)
        self.assertEqual((c["call_status"], c["talk_seconds"], c["final_source"]), ("Answered", 30, "Provider"))

    def test_unanswered_zero_talk(self):
        _, c = self.run_seq([("call.ringing", 1, None, None), ("call.ended", 30, "no-answer", 0)])
        self.assertEqual((c["call_status"], c["talk_seconds"]), ("Unanswered", 0))

    def test_busy_preserved(self):
        _, c = self.run_seq([("call.ended", 5, "busy", None)])
        self.assertEqual((c["call_status"], c["provider_status"]), ("Busy", "Busy"))

    def test_late_after_end_cannot_reverse(self):
        acts, c = self.run_seq([("call.ended", 30, "no-answer", None), ("call.answered", 40, None, None),
                                ("call.ended", 50, "completed", 20)])
        self.assertEqual(acts, ["apply", "late", "late"])
        self.assertEqual(c["call_status"], "Unanswered")

    def test_out_of_order(self):
        acts, c = self.run_seq([("call.answered", 8, None, None), ("call.ringing", 2, None, None)])
        self.assertEqual(acts, ["apply", "late"])
        self.assertEqual(c["call_status"], "Answered")

    def test_human_closed_first_attach_and_flag(self):
        cur = {"call_status": "Answered", "is_final": 1, "final_source": "Human", "talk_seconds": 60}
        a, upd = u.plan_event(cur, "call.ended", self.t(30), "no-answer", 0)
        self.assertEqual(a, "attach")
        self.assertEqual(upd["reconcile_flag"], 1)
        self.assertNotIn("call_status", upd)
        cur.update(upd)
        self.assertEqual(u.plan_event(cur, "call.ended", self.t(31), "completed", 5)[0], "late")

    def test_measured_talk_replaces_reported(self):
        cur = {"call_status": "Answered", "is_final": 1, "final_source": "Human", "talk_seconds": 600}
        _, upd = u.plan_event(cur, "call.ended", self.t(30), "completed", 95)
        self.assertEqual(upd["talk_seconds"], 95)
        self.assertNotIn("reconcile_flag", upd)

    def test_parse_iso(self):
        self.assertEqual(u.parse_iso("2026-11-24T07:00:00Z"), datetime(2026, 11, 24, 10, 0))
        self.assertEqual(u.parse_iso("2026-11-24T10:00:00+03:00"), datetime(2026, 11, 24, 10, 0))
        self.assertIsNone(u.parse_iso("garbage"))


if __name__ == "__main__":
    unittest.main()
