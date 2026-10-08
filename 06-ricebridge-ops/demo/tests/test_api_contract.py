"""Regression checks for request parsing, approval identity and translation isolation."""
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import server
import translate


class ApiContract(unittest.TestCase):
    def test_invalid_length_and_json(self):
        for raw, length in [(b"{}", "bad"), (b"{}", "-1"), (b"{", "1"), (b"[]", "2")]:
            handler = object.__new__(server.Handler)
            handler.headers = {"Content-Length": length}
            handler.rfile = io.BytesIO(raw)
            with self.subTest(raw=raw, length=length), self.assertRaises(server.DemoError):
                handler.read_json()

    def test_publication_does_not_translate_source_evidence(self):
        source = {"message": {"en": "Example"}}
        rt = object.__new__(server.Runtime)
        rt.demo = SimpleNamespace(snapshot=lambda: source)
        rt.store = SimpleNamespace(get=lambda key: {"vi": "Vi du", "ja": "Example"}, failed=set())
        rt.version = 0
        rt.publish()
        self.assertEqual(source, {"message": {"en": "Example"}})
        self.assertEqual(json.loads(rt.published)["message"]["vi"], "Vi du")

    def test_old_plan_or_previous_reset_cannot_be_approved(self):
        for body in [{"plan_id": "P1", "epoch": 2}, {"plan_id": "P2", "epoch": 1}]:
            handler = object.__new__(server.Handler)
            handler.path = "/api/decision"
            handler.read_json = lambda: {"decision": "approve", **body}
            handler.runtime = SimpleNamespace(
                demo=SimpleNamespace(plan={"id": "P2"}, epoch=2),
                start_job=lambda kind, label, fn: fn(),
            )
            with self.subTest(body=body), self.assertRaises(server.DemoError):
                handler.route_post()

    def test_stage_reason_has_offline_translations(self):
        store = translate.Store()
        self.assertTrue(store.get("28e070fc61bb84dd7775")["vi"])
        self.assertTrue(store.get("28e070fc61bb84dd7775")["ja"])


if __name__ == "__main__":
    unittest.main()
