"""Regression checks for invalid requests and stale approval clicks."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ApiContract(unittest.TestCase):
    def body(self, raw, length=None):
        handler = object.__new__(server.ApiHandler)
        handler.headers = {"Content-Length": str(len(raw) if length is None else length)}
        handler.rfile = io.BytesIO(raw)
        return handler._body()

    def test_invalid_bodies_are_rejected(self):
        for raw, length in [(b"{", None), (b"[]", None), (b"", -1), (b"", server.MAX_BODY + 1), (b"", "bad")]:
            with self.subTest(raw=raw, length=length), self.assertRaises(ValueError):
                self.body(raw, length)
        self.assertEqual(self.body(b'{"approved":false}'), {"approved": False})

    def test_old_and_duplicate_decisions_cannot_change_approval(self):
        runner = server.LiveRunner(0)
        runner.run_id = "new-run"
        runner.pending = {"seq": 20}
        self.assertFalse(runner.decide(True, "old-run", 20))
        self.assertFalse(runner.decide(True, "new-run", 19))
        self.assertTrue(runner.decide(False, "new-run", 20))
        self.assertFalse(runner.decide(True, "new-run", 20))
        self.assertFalse(runner.decision[0])

    def test_stopped_run_cannot_be_approved(self):
        runner = server.LiveRunner(0)
        runner.pending = {"seq": 1}
        runner.stop()
        self.assertFalse(runner.decide(True, seq=1))


if __name__ == "__main__":
    unittest.main()
