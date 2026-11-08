import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from codex_quota_keeper import hooks, settings, storage


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env_patch = patch.dict(os.environ, {"CODEX_HOME": self.tmp.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_counts_only_and_warns_once(self):
        with patch.object(hooks, "PROMPT_THRESHOLDS", (2,)):
            event = {"hook_event_name": "UserPromptSubmit", "session_id": "private-id",
                     "prompt": "confidential text"}
            self.assertIsNone(hooks.process(event))
            warning = hooks.process(event)
            self.assertEqual(warning["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn("2 prompts", warning["hookSpecificOutput"]["additionalContext"])
            self.assertIsNone(hooks.process(event))
        report = storage.history()
        self.assertEqual(report["sessions_total"], 1)
        self.assertEqual(report["totals"]["prompts"], 3)
        self.assertFalse(hooks.state_path("private-id").exists())
        raw_db = storage.db_path().read_bytes()
        self.assertNotIn(b"confidential", raw_db)
        self.assertNotIn(b"private-id", raw_db)

    def test_model_request_metrics_are_diagnostic_only(self):
        event = {
            "hook_event_name": "PostModelRequest", "session_id": "session-1",
            "status": "completed", "error": "should not save",
            "token_usage": {
                "input_tokens": 120, "cached_input_tokens": 50,
                "output_tokens": 40, "reasoning_output_tokens": 7,
                "unknown_text": "should not save",
            }, "prompt": "should not save",
        }
        self.assertIsNone(hooks.process(event))
        self.assertIsNone(hooks.process({
            "hook_event_name": "PostModelRequest", "session_id": "session-1",
            "status": "failed", "token_usage": None,
        }))
        report = storage.history()
        result = report["sessions"][0]
        self.assertEqual(result["model_requests"], 2)
        self.assertEqual(result["model_status"]["completed"], 1)
        self.assertEqual(result["model_status"]["failed"], 1)
        self.assertEqual(result["model_tokens"]["input_tokens"], 120)
        self.assertEqual(result["model_tokens"]["cached_input_tokens"], 50)
        self.assertEqual(result["token_usage_reports"], 1)
        raw = storage.db_path().read_bytes()
        self.assertNotIn(b"should not save", raw)
        self.assertNotIn(b"session-1", raw)

    def test_legacy_import_once_and_history_no_duplication(self):
        legacy = hooks.state_path("old-private")
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({
            "prompts": 4, "tools": 3, "announced": ["prompts-2"],
            "model_requests": 1, "model_tokens": {"input_tokens": 100},
            "prompt": "PRIVATE",
        }), encoding="utf-8")
        self.assertEqual(storage.history()["totals"]["prompts"], 4)
        hooks.process({"session_id": "old-private", "hook_event_name": "UserPromptSubmit"})
        report = storage.history()
        self.assertEqual(report["sessions_total"], 1)
        self.assertEqual(report["totals"]["prompts"], 5)
        self.assertEqual(report["totals"]["model_tokens"]["input_tokens"], 100)
        self.assertEqual(report["sessions"][0]["source"], "sqlite")
        self.assertEqual(json.loads(legacy.read_text())["prompts"], 4)

    def test_simultaneous_updates_do_not_lose_counts(self):
        event = {"hook_event_name": "PostToolUse", "session_id": "parallel-private"}
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(hooks.process, [event] * 40))
        self.assertEqual(storage.history()["totals"]["tools"], 40)

    def test_configurable_alerts_and_validation(self):
        path, created = settings.init()
        self.assertTrue(created)
        self.assertFalse(settings.init()[1])
        path.write_text(json.dumps({
            "alerts": {"prompts": [1], "tools": []}, "warnings_enabled": True
        }))
        result = hooks.process({"hook_event_name": "UserPromptSubmit", "session_id": "new"})
        self.assertIn("1 prompts", result["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(hooks.process({"hook_event_name": "UserPromptSubmit", "session_id": "new"}))
        with self.assertRaises(ValueError):
            settings.validate({"alerts": {"prompts": [2, 1]}})
        with self.assertRaises(ValueError):
            settings.validate({"alerts": {"tools": [True]}})
        with self.assertRaises(ValueError):
            settings.validate({"warnings_enabled": "false"})

    def test_malformed_event_is_ignored(self):
        self.assertIsNone(hooks.process({}))
        self.assertIsNone(hooks.process({"hook_event_name": "Stop", "session_id": "x"}))
        self.assertIsNone(hooks.process({"hook_event_name": "PostToolUse", "session_id": ""}))
        self.assertFalse((Path(self.tmp.name) / "quota-keeper").exists())


if __name__ == "__main__":
    unittest.main()
