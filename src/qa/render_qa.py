"""MuseScore Render QA.

Confirms the deliverable can actually be opened and rendered:
- MusicXML parses (re-import)
- MuseScore imports it to .mscz (exit code 0)
- MuseScore exports a non-empty PDF
- per-part MusicXML files import (linked-part viability)

A failure here is HUMAN_REVIEW: nothing may be delivered that does not
render. The fix path is the SAFE_REPAIR rhythm normalization — the
pipeline re-runs this stage after the fixer.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.musicxml.musicxml_to_score_ir import MusicXMLImporter
from score_engine.musicxml.score_ir_to_musicxml import MusicXMLExporter
from score_engine.score_ir.score_ir import Score


def find_musescore() -> str | None:
    candidates = [
        "C:/Program Files/MuseScore 4/bin/MuseScore4.exe",
        "D:/Program Files/MuseScore 4/bin/MuseScore4.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


class RenderQA:
    """MuseScore import / PDF render / linked parts verification."""

    def __init__(self, musescore_exe: str | None = None) -> None:
        self.musescore_exe = musescore_exe or find_musescore()

    def run(
        self,
        musicxml_path: str | Path,
        score: Score,
        work_dir: str | Path,
        project_name: str = "project",
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.MUSESCORE_RENDER)
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        musicxml_path = Path(musicxml_path)

        # --- 1. MusicXML parses ----------------------------------------------
        stage.checks_run += 1
        try:
            importer = MusicXMLImporter()
            importer.import_file(musicxml_path)
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-XML-PARSE",
                    category=QACategory.MUSESCORE_RENDER,
                    check="musicxml_parse",
                    status=QAStatus.PASS,
                    severity="info",
                    description=f"MusicXML parses: {musicxml_path.name}",
                )
            )
        except Exception as e:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-XML-PARSE-FAIL",
                    category=QACategory.MUSESCORE_RENDER,
                    check="musicxml_parse",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description=f"MusicXML does not parse: {e}",
                )
            )
            return stage

        if self.musescore_exe is None:
            stage.status = "SKIP"
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-NO-MUSESCORE",
                    category=QACategory.MUSESCORE_RENDER,
                    check="musescore_available",
                    status=QAStatus.SKIP,
                    severity="info",
                    description="MuseScore 4 executable not found — render checks skipped",
                )
            )
            return stage

        # --- 2. MuseScore import -> .mscz ------------------------------------
        stage.checks_run += 1
        mscz = work_dir / f"{project_name}.mscz"
        import_ok = self._run_ms(
            [self.musescore_exe, "-o", str(mscz), str(musicxml_path)]
        )
        if import_ok and mscz.exists():
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-MSCZ-IMPORT",
                    category=QACategory.MUSESCORE_RENDER,
                    check="musescore_import",
                    status=QAStatus.PASS,
                    severity="info",
                    description=f"MuseScore imported to {mscz.name}",
                    evidence={"mscz": str(mscz)},
                )
            )
        else:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-MSCZ-IMPORT-FAIL",
                    category=QACategory.MUSESCORE_RENDER,
                    check="musescore_import",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description=(
                        "MuseScore could not import the MusicXML — the file is not "
                        "deliverable. Typical causes: rhythmic overflow from "
                        "un-normalized divisions or missing measures."
                    ),
                    evidence={"musicxml": str(musicxml_path)},
                )
            )
            return stage

        # --- 3. PDF export ----------------------------------------------------
        stage.checks_run += 1
        pdf = work_dir / f"{project_name}.pdf"
        pdf_ok = self._run_ms([self.musescore_exe, "-o", str(pdf), str(mscz)])
        if pdf_ok and pdf.exists() and pdf.stat().st_size > 0:
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-PDF",
                    category=QACategory.MUSESCORE_RENDER,
                    check="pdf_render",
                    status=QAStatus.PASS,
                    severity="info",
                    description=f"PDF rendered: {pdf.name} ({pdf.stat().st_size} bytes)",
                    evidence={"pdf": str(pdf)},
                )
            )
        else:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="RENDER-PDF-FAIL",
                    category=QACategory.MUSESCORE_RENDER,
                    check="pdf_render",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description="MuseScore imported the score but could not export a PDF",
                )
            )

        # --- 4. Linked parts viability ----------------------------------------
        if len(score.parts) > 1:
            stage.checks_run += 1
            failed_parts = []
            for part in score.parts:
                part_score = Score(title=score.title, parts=[part])
                part_xml = work_dir / f"{project_name}_part_{part.id}.musicxml"
                try:
                    MusicXMLExporter().export_file(part_score, part_xml)
                except Exception as e:
                    failed_parts.append(f"{part.id} (export error: {e})")
                    continue
                part_mscz = work_dir / f"{project_name}_part_{part.id}.mscz"
                if not self._run_ms(
                    [self.musescore_exe, "-o", str(part_mscz), str(part_xml)]
                ):
                    failed_parts.append(part.id)
            if failed_parts:
                stage.issues.append(
                    QAIssue(
                        issue_id="RENDER-PARTS-FAIL",
                        category=QACategory.MUSESCORE_RENDER,
                        check="linked_parts",
                        status=QAStatus.HUMAN_REVIEW,
                        severity="medium",
                        description=(
                            f"Linked part(s) failed to build: {failed_parts}"
                        ),
                        evidence={"failed_parts": failed_parts},
                    )
                )
            else:
                stage.issues.append(
                    QAIssue(
                        issue_id="RENDER-PARTS-OK",
                        category=QACategory.MUSESCORE_RENDER,
                        check="linked_parts",
                        status=QAStatus.PASS,
                        severity="info",
                        description=(
                            f"All {len(score.parts)} linked parts import independently"
                        ),
                    )
                )

        if stage.status == "FAIL":
            pass
        else:
            stage.status = "PASS"
        return stage

    def _run_ms(self, cmd: list[str]) -> bool:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return proc.returncode == 0
        except Exception:
            return False
