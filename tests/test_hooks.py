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

    def test_malformed_event_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CODEX_HOME": folder}):
                self.assertIsNone(hooks.process({}))
                self.assertIsNone(hooks.process({"hook_event_name": "Stop", "session_id": "x"}))
                self.assertIsNone(hooks.process({"hook_event_name": "PostToolUse", "session_id": ""}))
                self.assertFalse((Path(folder) / "quota-keeper").exists())


if __name__ == "__main__":
    unittest.main()
