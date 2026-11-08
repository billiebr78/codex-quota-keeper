import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_quota_keeper import hooks


class HookTests(unittest.TestCase):
    def test_counts_only_and_warns_once(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CODEX_HOME": folder}):
                with patch.object(hooks, "PROMPT_THRESHOLDS", (2,)):
                    event = {"hook_event_name": "UserPromptSubmit", "session_id": "private-id",
                             "prompt": "confidential text"}
                    self.assertIsNone(hooks.process(event))
                    warning = hooks.process(event)
                    self.assertEqual(warning["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
                    self.assertIn("2 prompts", warning["hookSpecificOutput"]["additionalContext"])
                    self.assertIsNone(hooks.process(event))
                    path = hooks.state_path("private-id")
                    self.assertTrue(path.exists())
                    saved = path.read_text()
                    self.assertNotIn("confidential", saved)
                    self.assertNotIn("private-id", str(path))
                    self.assertEqual(json.loads(saved)["prompts"], 3)

    def test_model_request_metrics_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CODEX_HOME": folder}):
                event = {
                    "hook_event_name": "PostModelRequest", "session_id": "session-1",
                    "status": "completed", "error": "should not save",
                    "token_usage": {
                        "input_tokens": 120, "cached_input_tokens": 50,
                        "output_tokens": 40, "reasoning_output_tokens": 7,
                        "unknown_text": "should not save"
                    },
                    "prompt": "should not save"
                }
                self.assertIsNone(hooks.process(event))
                self.assertIsNone(hooks.process({
                    "hook_event_name": "PostModelRequest", "session_id": "session-1",
                    "status": "failed", "token_usage": None,
                }))
                state_text = hooks.state_path("session-1").read_text(encoding="utf-8")
                result = json.loads(state_text)
                self.assertEqual(result["model_requests"], 2)
                self.assertEqual(result["model_status"], {"completed": 1, "failed": 1})
                self.assertEqual(result["model_tokens"]["input_tokens"], 120)
                self.assertEqual(result["model_tokens"]["cached_input_tokens"], 50)
                self.assertEqual(result["model_tokens"]["output_tokens"], 40)
                self.assertEqual(result["token_usage_reports"], 1)
                self.assertNotIn("should not save", state_text)
                self.assertNotIn("session-1", state_text)

    def test_malformed_event_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CODEX_HOME": folder}):
                self.assertIsNone(hooks.process({}))
                self.assertIsNone(hooks.process({"hook_event_name": "Stop", "session_id": "x"}))
                self.assertIsNone(hooks.process({"hook_event_name": "PostToolUse", "session_id": ""}))
                self.assertFalse((Path(folder) / "quota-keeper").exists())


if __name__ == "__main__":
    unittest.main()
