import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from codex_quota_keeper import hooks, state


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {"CODEX_HOME": self.temp.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_counts_and_warns_once(self):
        with patch.object(hooks, "PROMPT_THRESHOLDS", (2,)):
            payload = {"hook_event_name": "UserPromptSubmit", "session_id": "private-id",
                       "prompt": "confidential text"}
            self.assertIsNone(hooks.process(payload))
            warning = hooks.process(payload)
            self.assertEqual(warning["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn("2 prompts", warning["hookSpecificOutput"]["additionalContext"])
            self.assertIsNone(hooks.process(payload))
        path = hooks.state_path("private-id")
        saved = path.read_text(encoding="utf-8")
        self.assertEqual(json.loads(saved)["prompts"], 3)
        self.assertNotIn("private-id", str(path))
        self.assertNotIn("confidential", saved)

    def test_model_request_metrics_no_private_content(self):
        payload = {
            "hook_event_name": "PostModelRequest", "session_id": "session-1",
            "status": "completed", "prompt": "secret prompt",
            "error": "secret error",
            "token_usage": {
                "input_tokens": 120, "cached_input_tokens": 50,
                "output_tokens": 40, "reasoning_output_tokens": 7,
                "unknown": "private content",
            },
        }
        self.assertIsNone(hooks.process(payload))
        self.assertIsNone(hooks.process({
            "hook_event_name": "PostModelRequest", "session_id": "session-1",
            "status": "failed", "token_usage": {"input_tokens": -2, "output_tokens": True},
        }))
        result = json.loads(hooks.state_path("session-1").read_text())
        self.assertEqual(result["model_requests"], 2)
        self.assertEqual(result["model_status"]["completed"], 1)
        self.assertEqual(result["model_status"]["failed"], 1)
        self.assertEqual(result["model_tokens"]["input_tokens"], 120)
        self.assertEqual(result["model_tokens"]["cached_input_tokens"], 50)
        self.assertEqual(result["token_usage_reports"], 1)
        raw = hooks.state_path("session-1").read_bytes()
        self.assertNotIn(b"secret", raw)
        self.assertNotIn(b"private content", raw)
        self.assertNotIn(b"session-1", raw)

    def test_existing_json_is_incremented_without_migration(self):
        path = hooks.state_path("old")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "prompts": 2, "tools": 4, "announced": ["prompts-40"],
            "model_requests": 6,
            "model_tokens": {"input_tokens": 123739, "cached_input_tokens": 104448,
                             "output_tokens": 622, "reasoning_output_tokens": 153},
        }), encoding="utf-8")
        hooks.process({"hook_event_name": "UserPromptSubmit", "session_id": "old"})
        hooks.process({"hook_event_name": "PostToolUse", "session_id": "old"})
        stored = json.loads(path.read_text())
        self.assertEqual(stored["prompts"], 3)
        self.assertEqual(stored["tools"], 5)
        self.assertEqual(stored["model_requests"], 6)
        self.assertEqual(stored["model_tokens"]["input_tokens"], 123739)
        report = state.summary()
        self.assertEqual(report["totals"]["prompts"], 3)
        self.assertEqual(report["totals"]["model_tokens"]["input_tokens"], 123739)

    def test_concurrent_updates_keep_all_counts(self):
        event = {"hook_event_name": "PostToolUse", "session_id": "parallel"}
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(hooks.process, [event] * 32))
        self.assertEqual(state.summary()["totals"]["tools"], 32)

    def test_summary_limit_only_changes_recent_list(self):
        for i in range(3):
            hooks.process({"hook_event_name": "UserPromptSubmit", "session_id": f"session-{i}"})
        report = state.summary(limit=1)
        self.assertEqual(report["sessions_total"], 3)
        self.assertEqual(report["totals"]["prompts"], 3)
        self.assertEqual(len(report["sessions"]), 1)
        self.assertIn("Input tokens", state.format_summary(report))
        with self.assertRaises(ValueError):
            state.summary(limit=0)

    def test_malformed_is_ignored(self):
        self.assertIsNone(hooks.process({}))
        self.assertIsNone(hooks.process({"hook_event_name": "Stop", "session_id": "x"}))
        self.assertIsNone(hooks.process({"hook_event_name": "PostToolUse", "session_id": ""}))
        self.assertFalse((Path(self.temp.name) / "quota-keeper").exists())


if __name__ == "__main__":
    unittest.main()
