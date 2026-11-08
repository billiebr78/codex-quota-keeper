"""VS Code extension detection works without a separate Codex CLI."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from codex_quota_keeper.cli import _vscode_codex_extension


class DoctorTests(unittest.TestCase):
    def test_detects_extension_using_code_cli(self):
        proc = SimpleNamespace(
            returncode=0,
            stdout="ms-python.python@2026.1.0\nopenai.chatgpt@26.1021.22027\n",
        )
        with patch("codex_quota_keeper.cli.shutil.which", side_effect=lambda name: "code.cmd" if name == "code" else None):
            with patch("codex_quota_keeper.cli.subprocess.run", return_value=proc) as run:
                found = _vscode_codex_extension()
        self.assertEqual(found, "openai.chatgpt@26.1021.22027 (VS Code extension list)")
        self.assertEqual(run.call_args.args[0], ["code.cmd", "--list-extensions", "--show-versions"])

    def test_detects_extension_using_directory_when_cli_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "openai.chatgpt-26.1021.22027").mkdir()
            with patch("codex_quota_keeper.cli.shutil.which", return_value=None):
                with patch.dict("os.environ", {"VSCODE_EXTENSIONS": str(root)}):
                    self.assertEqual(
                        _vscode_codex_extension(),
                        "openai.chatgpt@26.1021.22027 (installed extension directory)",
                    )

    def test_no_extension_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("codex_quota_keeper.cli.shutil.which", return_value=None):
                with patch("codex_quota_keeper.cli.Path.home", return_value=Path(folder)):
                    with patch.dict("os.environ", {"VSCODE_EXTENSIONS": folder}):
                        self.assertIsNone(_vscode_codex_extension())


if __name__ == "__main__":
    unittest.main()
