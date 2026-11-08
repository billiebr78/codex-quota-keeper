import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_quota_keeper import installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()

    def test_dry_run_then_apply_and_idempotence(self):
        self.assertFalse((self.root / "AGENTS.md").exists())
        plan = installer.configure(project=self.root, apply=False)
        self.assertTrue(any("preview" in line for line in plan))
        self.assertFalse((self.root / "AGENTS.md").exists())

        installer.configure(project=self.root, apply=True)
        policy = (self.root / "AGENTS.md").read_text()
        self.assertIn(installer.START, policy)
        self.assertTrue((self.root / "HANDOFF.md").is_file())
        hooks = json.loads((self.root / ".codex" / "hooks.json").read_text())
        self.assertIn("UserPromptSubmit", hooks["hooks"])
        self.assertIn("PostToolUse", hooks["hooks"])
        handler = hooks["hooks"]["PostToolUse"][0]["hooks"][0]
        self.assertIn("commandWindows", handler)
        self.assertNotIn("command_windows", handler)
        self.assertEqual(handler["additionalContextLimit"], 350)

        again = installer.configure(project=self.root, apply=True)
        self.assertTrue(all(line.startswith("unchanged:") for line in again))
        self.assertEqual(policy, (self.root / "AGENTS.md").read_text())

    def test_preserve_existing_config_and_remove_managed_only(self):
        policy = self.root / "AGENTS.md"
        policy.write_text("# Existing project rules\n", encoding="utf-8")
        hookfile = self.root / ".codex" / "hooks.json"
        hookfile.parent.mkdir()
        existing = {
            "unknown": {"keep": True},
            "hooks": {
                "PostToolUse": [{"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "echo keep"}
                ]}]
            }
        }
        hookfile.write_text(json.dumps(existing), encoding="utf-8")
        installer.configure(project=self.root, apply=True)
        self.assertIn("# Existing project rules", policy.read_text())
        self.assertTrue(any(self.root.glob("AGENTS.md.cqk-backup-*")))
        installer.configure(project=self.root, apply=True, remove=True)
        self.assertEqual(policy.read_text().strip(), "# Existing project rules")
        result = json.loads(hookfile.read_text())
        self.assertEqual(result["unknown"], {"keep": True})
        self.assertEqual(result["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "echo keep")
        self.assertNotIn("UserPromptSubmit", result["hooks"])
        self.assertTrue((self.root / "HANDOFF.md").exists())

    def test_invalid_hook_json_fails_without_policy_write(self):
        (self.root / ".codex").mkdir()
        (self.root / ".codex" / "hooks.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(ValueError):
            installer.configure(project=self.root, apply=True)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_uninstall_without_install_has_no_side_effects(self):
        installer.configure(project=self.root, apply=True, remove=True)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / ".codex" / "hooks.json").exists())

    def test_user_scope_does_not_create_global_handoff(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root)}):
            installer.configure(project=self.root, scope="user", apply=True)
        self.assertTrue((self.root / "AGENTS.md").exists())
        self.assertTrue((self.root / "hooks.json").exists())
        self.assertFalse((self.root / "HANDOFF.md").exists())


if __name__ == "__main__":
    unittest.main()
