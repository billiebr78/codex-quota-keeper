import json
import tempfile
import unittest
from pathlib import Path

from codex_quota_keeper import usage


class ComparisonTests(unittest.TestCase):
    def test_comparison_reduces_reported_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder) / "baseline.jsonl"
            optimized = Path(folder) / "optimized.jsonl"
            baseline.write_text(json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 1000, "cached_input_tokens": 100, "output_tokens": 300}}))
            optimized.write_text(json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 600, "cached_input_tokens": 100, "output_tokens": 200}}))
            diff = usage.compare([baseline], [optimized])
            self.assertEqual(diff["baseline"]["total_tokens"], 1300)
            self.assertEqual(diff["optimized"]["total_tokens"], 800)
            self.assertEqual(diff["changes"]["total_tokens"]["absolute"], -500)
            self.assertIn("Not subscription quota", usage.format_comparison(diff))
