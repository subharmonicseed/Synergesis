"""Software-only transport doubles for the recorded prompt trial."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("recorded_trial", Path(__file__).with_name("syn_four_arm_recorded_v1.py"))
recorded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorded)


class Response(io.BytesIO):
    status = 200


class Transport:
    def __init__(self, result):
        self.raw = json.dumps(result).encode()
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.raw)


class RecordedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pinning = patch.object(recorded, "identity", return_value={"name": "fake-unit-test", "digest": "a"*64, "details": {}})
        self.identity = self.pinning.start()
        self.addCleanup(self.pinning.stop)
        self.old = recorded.legacy_module()
        self.manifest = {"model_id": "fake-unit-test", "token_budget_per_arm": 100000}
        self.questions = [{"task_id": "toy", "arm": "baseline", "prompt": "Return the answer"}]
        self.backend = recorded.RecordedBackend(self.old, self.manifest, self.questions, self.root)
        self.transport = Transport({"done": True, "message": {"content": '{"answer":"42"}'},
                                    "prompt_eval_count": 20, "eval_count": 5})
        self.backend.transport = self.transport

    def test_real_payload_and_raw_receipts_are_preserved(self):
        self.assertEqual(self.backend("Return the answer"), ("42", 25))
        folder = self.root / "transport" / "000"
        sent = self.transport.requests[0].data
        self.assertEqual(json.loads(sent)["options"]["num_ctx"], 4096)
        self.assertEqual((folder / "response.json").read_bytes(), self.transport.raw)
        receipt = json.loads((folder / "receipt.json").read_text())
        self.assertEqual(receipt["request_sha256"], hashlib.sha256(sent).hexdigest())
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(self.transport.raw).hexdigest())
        self.assertEqual(self.backend.tokens["baseline"], 25)

    def test_budget_is_checked_before_model_transport(self):
        self.manifest["token_budget_per_arm"] = 4223
        with self.assertRaises(RuntimeError):
            self.backend("Return the answer")
        self.assertFalse(self.transport.requests)

    def test_foreign_prompt_and_extra_call_are_denied(self):
        with self.assertRaises(self.old.TrialError):
            self.backend("unregistered")
        self.assertFalse(self.transport.requests)
        self.backend("Return the answer")
        with self.assertRaises(self.old.TrialError):
            self.backend("Return the answer")
        self.assertEqual(len(self.transport.requests), 1)

    def test_format_failure_keeps_actual_response_and_usage(self):
        self.transport.raw = json.dumps({"done": True, "message": {"content": '{"answer":42}'},
                                         "prompt_eval_count": 20, "eval_count": 5}).encode()
        with self.assertRaises(RuntimeError):
            self.backend("Return the answer")
        self.assertTrue((self.root / "transport" / "000" / "response.json").exists())
        self.assertEqual(self.backend.tokens["baseline"], 25)
        self.assertEqual(self.backend.index, 0)

    def test_missing_usage_is_not_fabricated(self):
        self.transport.raw = json.dumps({"done": True, "message": {"content": '{"answer":"42"}'}}).encode()
        with self.assertRaises(RuntimeError):
            self.backend("Return the answer")
        self.assertTrue((self.root / "transport" / "000" / "response.json").exists())
        self.assertFalse((self.root / "transport" / "000" / "receipt.json").exists())
        self.assertEqual(self.backend.tokens["baseline"], 0)

    def test_model_change_stops_before_inference(self):
        self.identity.return_value = {"name": "fake-unit-test", "digest": "b"*64, "details": {}}
        with self.assertRaises(RuntimeError):
            self.backend("Return the answer")
        self.assertFalse(self.transport.requests)


if __name__ == "__main__":
    unittest.main()
