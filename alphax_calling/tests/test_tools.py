import hashlib
import hmac
import importlib.util
import pathlib
import unittest

from alphax_calling import utils

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTools(unittest.TestCase):
    def test_send_event_signature_matches_app(self):
        m = load("alphax_send_event")
        self.assertEqual(m.sign("k", "170", b'{"a":1}'), utils.sign("k", "170", b'{"a":1}'))

    def test_fetch_config_signature_is_over_empty_body(self):
        expected = hmac.new(b"k", b"170.", hashlib.sha256).hexdigest()
        self.assertEqual(utils.sign("k", "170", b""), expected)
        self.assertTrue(utils.verify_signature("k", "170", b"", expected, now=171))


if __name__ == "__main__":
    unittest.main()
