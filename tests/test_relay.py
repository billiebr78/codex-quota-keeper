import tempfile
import unittest
from pathlib import Path

from codex_quota_keeper import relay


class RelayTests(unittest.TestCase):
    def test_state_and_next_step(self):
        self.assertTrue(relay._done("STAGE DONE\n# Details"))
        self.assertFalse(relay._done("# HANDOFF\nSTAGE DONE"))
        text = "# HANDOFF\n\n## Next exact step\nRun tests\n\n## Then\nPublish\n"
        self.assertEqual(relay._next_step(text), "Run tests")

    def test_cannot_run_without_filled_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "HANDOFF.md").write_text("# HANDOFF\n## Next exact step\n<ONE action>\n")
            with self.assertRaises(ValueError):
                relay.run(project=root, rounds=1)


if __name__ == "__main__":
    unittest.main()
