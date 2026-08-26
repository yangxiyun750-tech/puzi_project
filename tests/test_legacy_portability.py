from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from score_rebuild.doctor import resolve_manifest_binary
from score_rebuild.private_fixture import (
    PRIVATE_FIXTURE_ENV,
    PRIVATE_OUTPUT_ENV,
    private_fixture_output_dir,
    private_fixture_status,
)


class PrivateFixtureIsolationTests(unittest.TestCase):
    def test_absent_private_fixture_is_a_clear_optional_skip(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status = private_fixture_status()
        self.assertFalse(status.available)
        self.assertIsNone(status.path)
        self.assertIn("Not configured", status.detail)
        self.assertIn(PRIVATE_FIXTURE_ENV, status.detail)

    def test_missing_configured_fixture_is_not_available(self) -> None:
        with patch.dict(os.environ, {PRIVATE_FIXTURE_ENV: "missing-private.musicxml"}, clear=True):
            status = private_fixture_status()
        self.assertFalse(status.available)
        self.assertIsNotNone(status.path)
        self.assertIn("does not exist", status.detail)

    def test_configured_fixture_and_output_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "private.musicxml"
            fixture.write_text("<score-partwise version='4.0'/>", encoding="utf-8")
            output = root / "output"
            with patch.dict(
                os.environ,
                {PRIVATE_FIXTURE_ENV: str(fixture), PRIVATE_OUTPUT_ENV: str(output)},
                clear=True,
            ):
                status = private_fixture_status()
                resolved_output = private_fixture_output_dir()
        self.assertTrue(status.available)
        self.assertEqual(status.path, fixture.resolve())
        self.assertEqual(resolved_output, output.resolve())

    def test_manifest_binary_resolution_honors_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "pdftoppm.exe"
            executable.write_bytes(b"test executable placeholder")
            with patch.dict(os.environ, {"PDFTOPPM_EXE": str(executable)}, clear=True):
                resolved = resolve_manifest_binary("pdftoppm")
        self.assertEqual(resolved, executable.resolve())


if __name__ == "__main__":
    unittest.main()
