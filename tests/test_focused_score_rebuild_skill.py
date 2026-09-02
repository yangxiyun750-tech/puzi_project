"""Synthetic tests for the focused-score-rebuild Skill helpers."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".agents" / "skills" / "focused-score-rebuild"
SCRIPTS = SKILL / "scripts"


def run_python(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise AssertionError(f"{script} failed: {result.stdout}\n{result.stderr}")
    return result


class SkillContractTests(unittest.TestCase):
    def test_name_and_manifest_resources(self) -> None:
        first_lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()[:5]
        self.assertIn("name: focused-score-rebuild", first_lines)
        self.assertIn("license: AGPL-3.0-only", first_lines)
        manifest = json.loads((ROOT / "score-rebuild-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["project"]["license"], "AGPL-3.0-only")
        entry = manifest["required_internal_skills"][0]
        self.assertEqual(entry["name"], "focused-score-rebuild")
        self.assertTrue((ROOT / entry["path"]).is_file())
        for resource in entry["resources"]:
            self.assertTrue((ROOT / resource).is_file(), resource)

    def test_packages_are_licensed_and_exclude_private_scores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_agent_packages.py"),
                 "--output-dir", directory],
                check=True, capture_output=True, text=True, encoding="utf-8",
            )
            archives = sorted(Path(directory).glob("*.zip"))
            self.assertEqual(len(archives), 2)
            for archive_path in archives:
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()
                    self.assertTrue(any(name.endswith("LICENSE") for name in names))
                    self.assertFalse(any(name.endswith("PACKAGE_NOTICE.txt") for name in names))
                    self.assertFalse(any(name.lower().endswith((".pdf", ".mscz", ".musicxml", ".mxl", ".omr"))
                                         for name in names))
                    plugin_names = [name for name in names if name.endswith(".zcode-plugin/plugin.json")]
                    if plugin_names:
                        plugin = json.loads(archive.read(plugin_names[0]))
                        self.assertEqual(plugin["license"], "AGPL-3.0-only")


class MetadataAndCatalogTests(unittest.TestCase):
    def test_multilingual_metadata_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "metadata.json"
            run_python("metadata_record.py", "init", "--record", record, "--source-pdf", "synthetic.pdf")
            run_python(
                "metadata_record.py", "add-title", "--record", record, "--kind", "original",
                "--value", "月光", "--method", "human", "--location", "synthetic page 1",
                "--language", "zh", "--script", "Hans", "--confidence", "1", "--status", "confirmed",
            )
            result = run_python("metadata_record.py", "validate", "--record", record)
            self.assertIn("METADATA_STATUS = PASS", result.stdout)
            payload = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(payload["titles"][0]["value"], "月光")

    def test_clarity_answer_blocks_or_classifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            run_python("library_catalog.py", "init", "--catalog", catalog)
            run_python(
                "library_catalog.py", "start", "--catalog", catalog, "--work-id", "synthetic",
                "--title", "Synthetic", "--source-pdf", "synthetic.pdf",
            )
            run_python(
                "library_catalog.py", "answer", "--catalog", catalog, "--work-id", "synthetic",
                "--field", "source_quality", "--value", "needs_rescan",
            )
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            self.assertEqual(payload["entries"]["synthetic"]["status"], "SOURCE_BLOCKED")


class ReviewAndBootstrapTests(unittest.TestCase):
    def test_metadata_question_blocks_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "queue.json"
            run_python(
                "review_queue.py", "init", "--queue", queue, "--title", "Synthetic",
                "--source-pdf", "synthetic.pdf",
            )
            result = run_python(
                "review_queue.py", "add", "--queue", queue, "--page", "1", "--measure", "header",
                "--instrument", "score", "--category", "metadata", "--severity", "important",
                "--source-observation", "two plausible readings", "--reconstructed-value", "A",
                "--proposed-action", "B", "--confidence", "0.5",
            )
            self.assertIn("QA_STATUS = BLOCKED", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "PowerShell helper is Windows-only")
    def test_download_requires_explicit_approval(self) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        self.assertIsNotNone(shell)
        result = subprocess.run(
            [shell, "-NoProfile", "-File", str(SCRIPTS / "bootstrap_tools.ps1"),
             "-Action", "Download", "-Tool", "python"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("APPROVAL_REQUIRED", result.stdout)


if __name__ == "__main__":
    unittest.main()
