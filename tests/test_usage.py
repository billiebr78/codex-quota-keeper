import json
import tempfile
import unittest
from pathlib import Path

from codex_quota_keeper import usage


class UsageTests(unittest.TestCase):
    def test_jsonl_reports_no_double_counted_cached_tokens(self):
        lines = [
            {"type": "thread.started", "thread_id": "a"},
            {"type": "turn.completed", "usage": {
                "input_tokens": 1000, "cached_input_tokens": 600,
                "output_tokens": 80, "reasoning_output_tokens": 30}},
            {"type": "turn.completed", "usage": {
                "input_tokens": 300, "cached_input_tokens": 100,
                "output_tokens": 20}},
            {"type": "turn.failed"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "one.jsonl"
            file.write_text("\n".join(json.dumps(line) for line in lines) + "\nnot json\n")
            result = usage.summarize([file])
        self.assertEqual(result["completed_turns"], 2)
        self.assertEqual(result["failed_turns"], 1)
        self.assertEqual(result["input_tokens"], 1300)
        self.assertEqual(result["cached_input_tokens"], 700)
        self.assertEqual(result["uncached_input_tokens"], 600)
        self.assertEqual(result["output_tokens"], 100)
        self.assertEqual(result["reasoning_output_tokens"], 30)
        self.assertEqual(result["total_tokens"], 1400)
        self.assertEqual(result["invalid_lines"], 1)
        self.assertIn("Not a subscription quota", usage.format_report(result))


if __name__ == "__main__":
    unittest.main()
