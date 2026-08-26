"""Non-score unit tests for the Phase 0.5 reproducibility tooling."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from score_rebuild.capabilities import (  # noqa: E402
    AVAILABLE,
    NOT_CONFIGURED,
    capability_exit_code,
    run_capability_doctor,
)
from score_rebuild.manifest import load_manifest  # noqa: E402
from score_rebuild.schema import verify_schema  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_manifest_has_one_runtime_skill_and_no_skill_creator(self) -> None:
        manifest = load_manifest()
        names = [entry["name"] for entry in manifest["required_internal_skills"]]
        self.assertEqual(names, ["orchestral-score-rebuild"])
        self.assertNotIn("skill-creator", json.dumps(manifest["required_internal_skills"]))

    def test_confirmed_dependency_classification(self) -> None:
        manifest = load_manifest()
        required = {entry["distribution"] for entry in manifest["required_python_packages"]}
        optional = {entry["distribution"] for entry in manifest["optional_python_packages"]}
        self.assertIn("pypdfium2", required)
        self.assertIn("PyMuPDF", required)
        self.assertNotIn("pdfplumber", required)
        self.assertIn("pdfplumber", optional)


class CapabilityDoctorTests(unittest.TestCase):
    def test_visual_is_not_assumed_and_manual_fallback_is_allowed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            results = run_capability_doctor(
                code_provider="test-agent",
                code_verified=True,
                human_reviewer="qualified-human",
            )
        statuses = {result.capability: result.status for result in results}
        self.assertEqual(statuses["CODE_REASONING"], AVAILABLE)
        self.assertEqual(statuses["VISUAL_REVIEW"], NOT_CONFIGURED)
        self.assertEqual(statuses["HUMAN_REVIEW_FALLBACK"], AVAILABLE)
        self.assertEqual(capability_exit_code(results), 0)

    def test_unverified_code_provider_blocks_readiness(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            results = run_capability_doctor(
                code_provider="named-but-unverified",
                code_verified=False,
                human_reviewer="qualified-human",
            )
        self.assertEqual(capability_exit_code(results), 1)


class SchemaAndFixtureTests(unittest.TestCase):
    def test_missing_schema_fails_with_file_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            valid, errors = verify_schema(Path(temp_dir))
        self.assertFalse(valid)
        self.assertTrue(any("musicxml.xsd" in error for error in errors))

    def test_runtime_validator_missing_schema_message_has_repair_command(self) -> None:
        src_path = PROJECT_ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        from validation.musicxml_xsd_validator import MusicXML4Validator

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(FileNotFoundError, "score_rebuild schema-install"):
                MusicXML4Validator(schema_dir=Path(temp_dir))

    def test_smoke_fixture_is_synthetic_musicxml_4(self) -> None:
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "smoke" / "minimal_score.musicxml"
        root = ET.parse(fixture).getroot()
        self.assertEqual(root.tag, "score-partwise")
        self.assertEqual(root.get("version"), "4.0")
        text = fixture.read_text(encoding="utf-8")
        self.assertIn("Repository-authored synthetic fixture", text)
        self.assertNotIn("天使的脸", text)


if __name__ == "__main__":
    unittest.main()
