"""Reconstruction pipeline for Score Reconstruction V2.

Orchestrates the complete workflow:
    PDF → rendered PNG → Audiveris OMR → raw MusicXML → ScoreIR
    → validation → repaired MusicXML → MuseScore → final outputs

Key V2 improvements:
- Explicit SAFE_REPAIR vs MUSICAL_REPAIR separation
- ScoreIR as the canonical intermediate representation
- RepairLog tracks every decision
- Original files are never overwritten
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Handle both package and standalone execution
try:
    from ..musicxml.musicxml_to_score_ir import MusicXMLImporter
    from ..musicxml.score_ir_to_musicxml import MusicXMLExporter
    from ..score_ir.score_ir import RepairIssue, RepairLog, RepairType
    from ..validation.roundtrip_validator import RoundtripValidator, ValidationReport
    from ..validation.instrument_identity import InstrumentIdentityResolver
except ImportError:
    from score_engine.musicxml.musicxml_to_score_ir import MusicXMLImporter
    from score_engine.musicxml.score_ir_to_musicxml import MusicXMLExporter
    from score_engine.score_ir.score_ir import RepairIssue, RepairLog, RepairType
    from score_engine.validation.roundtrip_validator import RoundtripValidator, ValidationReport
    from score_engine.validation.instrument_identity import InstrumentIdentityResolver


class ReconstructionPipeline:
    """End-to-end score reconstruction pipeline."""

    def __init__(
        self,
        source_pdf: Path,
        workdir: Path,
        project_name: str,
        audiveris_exe: Path,
        musescore_exe: Path,
        poppler_exe: Path,
        python_exe: Path | None = None,
    ) -> None:
        self.source_pdf = Path(source_pdf).resolve()
        self.workdir = Path(workdir).resolve()
        self.project_name = project_name
        self.audiveris_exe = Path(audiveris_exe).resolve()
        self.musescore_exe = Path(musescore_exe).resolve()
        self.poppler_exe = Path(poppler_exe).resolve()
        self.python_exe = python_exe or Path(sys.executable)

        # Standard directory layout
        self.dirs = {
            "source": self.workdir / "source",
            "rendered": self.workdir / "rendered",
            "omr": self.workdir / "omr",
            "score_ir": self.workdir / "score_ir",
            "repairs": self.workdir / "repairs",
            "output": self.workdir / "output",
            "qa": self.workdir / "qa",
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        # Repair tracking
        self.repair_log = RepairLog()

    # ------------------------------------------------------------------
    # Step 1: Preserve source
    # ------------------------------------------------------------------

    def preserve_source(self) -> Path:
        """Copy source PDF into workdir/source/ and return the preserved path."""
        preserved = self.dirs["source"] / self.source_pdf.name
        if not preserved.exists():
            shutil.copy2(self.source_pdf, preserved)
        return preserved

    # ------------------------------------------------------------------
    # Step 2: Render PDF to PNG
    # ------------------------------------------------------------------

    def render_pdf(self, dpi: int = 400) -> list[Path]:
        """Render source PDF to PNG pages using Poppler."""
        source = self.dirs["source"] / self.source_pdf.name
        prefix = self.dirs["rendered"] / "page"
        subprocess.run(
            [str(self.poppler_exe), "-png", "-r", str(dpi), str(source), str(prefix)],
            check=True,
            capture_output=True,
        )
        pages = sorted(self.dirs["rendered"].glob("page-*.png"))
        return pages

    # ------------------------------------------------------------------
    # Step 3: Audiveris OMR
    # ------------------------------------------------------------------

    def run_omr(self, pages: list[Path]) -> Path:
        """Run Audiveris batch OMR and return path to raw .mxl."""
        playlist_xml = self.dirs["omr"] / f"{self.project_name}-playlist.xml"
        self._make_playlist(pages, playlist_xml)

        # Build compound book
        subprocess.run(
            [str(self.audiveris_exe), "-batch", "-playlist", str(playlist_xml)],
            check=True,
            capture_output=True,
        )

        omr_file = self.dirs["omr"] / f"{self.project_name}-playlist.omr"

        # Transcribe, export, save
        output_dir = self.dirs["omr"] / "output"
        output_dir.mkdir(exist_ok=True)
        subprocess.run(
            [
                str(self.audiveris_exe),
                "-batch", "-transcribe", "-export", "-save",
                "-output", str(output_dir),
                "--", str(omr_file),
            ],
            check=True,
            capture_output=True,
        )

        mxl_files = list(output_dir.glob("*.mxl"))
        if not mxl_files:
            # Try same directory as .omr
            mxl_files = list(self.dirs["omr"].glob("*.mxl"))
        if not mxl_files:
            raise RuntimeError("Audiveris did not produce .mxl output")
        
        # Extract .mxl to .musicxml for easier processing
        mxl_path = mxl_files[0]
        musicxml_path = self.dirs["omr"] / f"{self.project_name}_raw.musicxml"
        import zipfile
        with zipfile.ZipFile(mxl_path) as z:
            names = [n for n in z.namelist() if n.endswith((".xml", ".musicxml")) and "META-INF" not in n]
            if not names:
                raise RuntimeError(f"No XML found in {mxl_path}")
            musicxml_path.write_bytes(z.read(names[0]))
        return musicxml_path

    def _make_playlist(self, pages: list[Path], output: Path) -> None:
        """Create Audiveris playlist XML."""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<play-list>"]
        for page in pages:
            lines.append(f"  <excerpt>")
            lines.append(f"    <path>{page}</path>")
            lines.append(f"    <sheets-selection>1</sheets-selection>")
            lines.append(f"  </excerpt>")
        lines.append("</play-list>")
        output.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Step 4: Import MusicXML → ScoreIR
    # ------------------------------------------------------------------

    def import_to_score_ir(self, musicxml_path: Path) -> "Score":
        """Import raw MusicXML into ScoreIR."""
        importer = MusicXMLImporter()
        score = importer.import_file(musicxml_path)
        self.repair_log.issues.extend(importer.repair_log.issues)
        return score

    # ------------------------------------------------------------------
    # Step 5: Export ScoreIR → MusicXML
    # ------------------------------------------------------------------

    def export_from_score_ir(self, score: "Score") -> Path:
        """Export ScoreIR back to MusicXML."""
        exporter = MusicXMLExporter()
        output_path = self.dirs["output"] / f"{self.project_name}_score_ir.musicxml"
        exporter.export_file(score, output_path)
        return output_path

    # ------------------------------------------------------------------
    # Step 6: Round-trip validation
    # ------------------------------------------------------------------

    def validate_roundtrip(self, original_score: "Score", roundtrip_path: Path) -> ValidationReport:
        """Validate that ScoreIR → MusicXML → ScoreIR preserves semantics."""
        importer = MusicXMLImporter()
        roundtrip_score = importer.import_file(roundtrip_path)

        validator = RoundtripValidator()
        report = validator.validate(original_score, roundtrip_score)

        json_path = self.dirs["qa"] / "ROUNDTRIP_SCORE_IR.json"
        md_path = self.dirs["qa"] / "ROUNDTRIP_SCORE_IR.md"
        report.save_json(json_path)
        report.save_markdown(md_path)

        return report

    # ------------------------------------------------------------------
    # Step 7: SAFE_REPAIR — structural fixes only
    # ------------------------------------------------------------------

    def apply_safe_repairs(self, score: "Score") -> None:
        """Apply only structural repairs (SAFE_REPAIR).

        Musical content is NEVER modified here. Missing measures are
        flagged as NEEDS_VISUAL_RECOVERY instead of being filled with rests.
        """
        # Detect missing measures and flag them
        for part in score.parts:
            nums = {int(m.number) for m in part.measures}
            max_num = max(nums) if nums else 0
            missing = [n for n in range(1, max_num + 1) if n not in nums]
            for miss_num in missing:
                instrument_name = part.name or part.id
                self.repair_log.add(RepairIssue(
                    issue_id=f"VISUAL-{part.id}-M{miss_num}",
                    repair_type=RepairType.VISUAL,
                    severity="high",
                    part_id=part.id,
                    measure_number=str(miss_num),
                    description=(
                        f"Missing measure {miss_num} in part {part.id} "
                        f"(instrument='{instrument_name}') — "
                        f"content not recoverable from OMR. "
                        f"Verify against source PDF."
                    ),
                    applied_fix={},
                    needs_human_review=True,
                ))

        # Structural repairs (key signature inheritance, etc.)
        for part in score.parts:
            for measure in part.measures:
                # Check for missing key/time signature that can be inferred
                if measure.key_signature is None and measure.number != "1":
                    prev_num = int(measure.number) - 1
                    if prev_num >= 1:
                        prev_measure = next(
                            (m for m in part.measures if m.number == str(prev_num)), None
                        )
                        if prev_measure and prev_measure.key_signature:
                            measure.key_signature = prev_measure.key_signature
                            self.repair_log.add(RepairIssue(
                                issue_id=f"SAFE-{part.id}-M{measure.number}-key",
                                repair_type=RepairType.SAFE,
                                severity="low",
                                part_id=part.id,
                                measure_number=measure.number,
                                description="Inherited key signature from previous measure",
                                applied_fix={"fifths": prev_measure.key_signature.fifths},
                            ))

    # ------------------------------------------------------------------
    # Step 8: MuseScore import/export
    # ------------------------------------------------------------------

    def musescore_import(self, musicxml_path: Path, output_name: str) -> Path | None:
        """Import MusicXML into MuseScore and save as .mscz."""
        output = self.dirs["output"] / output_name
        try:
            subprocess.run(
                [str(self.musescore_exe), "-o", str(output), str(musicxml_path)],
                check=True,
                capture_output=True,
            )
            return output
        except subprocess.CalledProcessError as e:
            self.repair_log.add(RepairIssue(
                issue_id=f"MUSESCORE-IMPORT-{self.project_name}",
                repair_type=RepairType.VISUAL,
                severity="high",
                part_id="",
                measure_number="",
                description=f"MuseScore import failed: exit={e.returncode}",
                applied_fix={},
                needs_human_review=True,
            ))
            return None

    def musescore_export_musicxml(self, mscz_path: Path, output_name: str) -> Path:
        """Export MusicXML from MuseScore .mscz."""
        output = self.dirs["output"] / output_name
        subprocess.run(
            [str(self.musescore_exe), "-o", str(output), str(mscz_path)],
            check=True,
            capture_output=True,
        )
        return output

    def musescore_export_pdf(self, mscz_path: Path, output_name: str) -> Path:
        """Export PDF from MuseScore .mscz."""
        output = self.dirs["output"] / output_name
        subprocess.run(
            [str(self.musescore_exe), "-o", str(output), str(mscz_path)],
            check=True,
            capture_output=True,
        )
        return output

    # ------------------------------------------------------------------
    # Instrument Identity Resolution
    # ------------------------------------------------------------------

    def _extract_pdf_text(self) -> str:
        """Extract text from source PDF for instrumentation clues."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(self.source_pdf)
            text_parts = []
            for page in reader.pages[:3]:  # First 3 pages usually contain title
                text = page.extract_text() or ""
                text_parts.append(text)
            return "\n".join(text_parts)
        except Exception:
            return ""

    def resolve_instrument_identities(self, score: "Score", pdf_text: str) -> list:
        """Resolve canonical instrument identities for all parts."""
        resolver = InstrumentIdentityResolver(pdf_text=pdf_text)
        identities = resolver.resolve(score)
        resolver.save_json(self.dirs["qa"] / "INSTRUMENT_IDENTITIES.json")
        return identities

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute the complete reconstruction pipeline."""
        results = {}

        # 1. Preserve source
        preserved = self.preserve_source()
        results["source_pdf"] = str(preserved)

        # 2. Render
        pages = self.render_pdf()
        results["rendered_pages"] = len(pages)

        # 3. OMR
        mxl_path = self.run_omr(pages)
        results["raw_omr_mxl"] = str(mxl_path)

        # 4. Import to ScoreIR
        score = self.import_to_score_ir(mxl_path)
        results["score_ir_parts"] = len(score.parts)
        results["score_ir_measures"] = sum(len(p.measures) for p in score.parts)

        # 4.5. Resolve instrument identities
        pdf_text = self._extract_pdf_text()
        identities = self.resolve_instrument_identities(score, pdf_text)
        results["instrument_identities"] = [i.to_dict() for i in identities]

        # 5. Apply safe repairs
        self.apply_safe_repairs(score)
        results["safe_repairs"] = len(self.repair_log.by_type(RepairType.SAFE))
        results["musical_repairs"] = len(self.repair_log.by_type(RepairType.MUSICAL))
        results["needs_visual"] = len(self.repair_log.by_type(RepairType.VISUAL))

        # 6. Export from ScoreIR
        score_ir_xml = self.export_from_score_ir(score)
        results["score_ir_musicxml"] = str(score_ir_xml)

        # 7. Round-trip validation
        report = self.validate_roundtrip(score, score_ir_xml)
        results["roundtrip_status"] = report.status
        results["roundtrip_errors"] = len(report.errors())
        results["roundtrip_warnings"] = len(report.warnings())

        # 8. MuseScore import (may fail if raw OMR has unrecoverable structure issues)
        mscz_path = self.musescore_import(score_ir_xml, f"{self.project_name}.mscz")
        if mscz_path is not None:
            results["musescore_mscz"] = str(mscz_path)

            # 9. MuseScore exports
            native_xml = self.musescore_export_musicxml(mscz_path, f"{self.project_name}_native.musicxml")
            results["musescore_musicxml"] = str(native_xml)

            pdf_path = self.musescore_export_pdf(mscz_path, f"{self.project_name}.pdf")
            results["musescore_pdf"] = str(pdf_path)
        else:
            results["musescore_mscz"] = "FAILED"
            results["musescore_musicxml"] = "FAILED"
            results["musescore_pdf"] = "FAILED"

        # 10. Save repair log
        self._save_repair_log()
        results["repair_log"] = str(self.dirs["qa"] / "REPAIR_LOG.json")

        return results

    def _save_repair_log(self) -> None:
        import json
        data = {
            "project": self.project_name,
            "total_issues": len(self.repair_log.issues),
            "safe_repairs": [
                {
                    "issue_id": i.issue_id,
                    "severity": i.severity,
                    "part_id": i.part_id,
                    "measure_number": i.measure_number,
                    "description": i.description,
                    "applied_fix": i.applied_fix,
                }
                for i in self.repair_log.by_type(RepairType.SAFE)
            ],
            "musical_repairs": [
                {
                    "issue_id": i.issue_id,
                    "severity": i.severity,
                    "part_id": i.part_id,
                    "measure_number": i.measure_number,
                    "description": i.description,
                    "needs_human_review": i.needs_human_review,
                }
                for i in self.repair_log.by_type(RepairType.MUSICAL)
            ],
            "needs_visual_recovery": [
                {
                    "issue_id": i.issue_id,
                    "severity": i.severity,
                    "part_id": i.part_id,
                    "measure_number": i.measure_number,
                    "description": i.description,
                    "needs_human_review": i.needs_human_review,
                }
                for i in self.repair_log.by_type(RepairType.VISUAL)
            ],
        }
        (self.dirs["qa"] / "REPAIR_LOG.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: reconstruction_pipeline.py SOURCE_PDF WORKDIR")
        return 2

    source = Path(sys.argv[1])
    workdir = Path(sys.argv[2])

    try:
        from score_rebuild.doctor import resolve_manifest_binary

        audiveris_exe = resolve_manifest_binary("audiveris")
        musescore_exe = resolve_manifest_binary("musescore")
        poppler_exe = resolve_manifest_binary("pdftoppm")
    except (ImportError, KeyError) as exc:
        print(f"environment discovery unavailable: {exc}")
        return 1

    missing = [
        name
        for name, executable in (("Audiveris", audiveris_exe), ("MuseScore", musescore_exe), ("pdftoppm", poppler_exe))
        if executable is None
    ]
    if missing:
        print(f"missing required executable(s): {', '.join(missing)}; run: python -m score_rebuild doctor")
        return 1

    pipeline = ReconstructionPipeline(
        source_pdf=source,
        workdir=workdir,
        project_name=source.stem.replace(" ", "_"),
        audiveris_exe=audiveris_exe,
        musescore_exe=musescore_exe,
        poppler_exe=poppler_exe,
    )

    results = pipeline.run()
    for key, value in results.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
