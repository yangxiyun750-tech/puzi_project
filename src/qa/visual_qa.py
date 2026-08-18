"""Visual QA — evidence package generation for AI_REVIEW / HUMAN_REVIEW.

The AI never re-reads the whole PDF. For every issue that needs review
this stage produces a compact evidence package:

    original_crop.png      the LOCAL region of the source PDF page
    original_page.png      downscaled full source page for context
    musescore_page.png     the same page region of the final MuseScore PDF
                           (approximate alignment, honestly labeled)
    scoreir_measure.json   the ScoreIR data for the measure(s) in question
    issue.json             the QA issue itself
    README.md              what to compare and why

Measure -> page mapping is taken from <print new-page="yes"> /
new-system="yes" events in the raw MusicXML (Audiveris mirrors the
source layout). When those events are absent the mapping falls back to
a linear estimate and is labeled as such.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Chord, Measure, Note, Rest, Score


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _event_to_dict(event) -> dict:
    if isinstance(event, Note):
        return {
            "kind": "rest" if event.is_rest else "note",
            "pitch": (
                f"{event.pitch.step}{event.pitch.alter:+d}{event.pitch.octave}"
                if event.pitch and not event.is_rest
                else None
            ),
            "type": event.type,
            "dots": event.dots,
            "ties": [{"type": t.type, "number": t.number} for t in event.ties],
            "slurs": [{"type": s.type, "number": s.number} for s in event.slurs],
            "articulations": [a.mark for a in event.articulations],
            "lyrics": [l.text for l in event.lyrics],
        }
    if isinstance(event, Chord):
        return {"kind": "chord", "notes": [_event_to_dict(n) for n in event.notes]}
    if isinstance(event, Rest):
        return {"kind": "rest", "type": event.type, "dots": event.dots}
    return {"kind": "unknown"}


def _measure_to_dict(measure: Measure) -> dict:
    return {
        "number": measure.number,
        "implicit": measure.implicit,
        "key": (
            {"fifths": measure.key_signature.fifths, "mode": measure.key_signature.mode}
            if measure.key_signature
            else None
        ),
        "time": (
            {"beats": measure.time_signature.beats, "beat_type": measure.time_signature.beat_type}
            if measure.time_signature
            else None
        ),
        "voices": [
            {"voice": v.id, "events": [_event_to_dict(e) for e in v.events]}
            for v in measure.voices
        ],
    }


@dataclass
class MeasureLocation:
    page: int = 1
    system: int = 0  # 0-based index within the page
    exact: bool = True  # False when estimated linearly


class VisualQA:
    """Generate local visual-evidence packages for issues needing review."""

    def __init__(
        self,
        rendered_dir: str | Path,
        output_dir: str | Path,
        pdftoppm: str = "pdftoppm",
        musescore_pdf: str | Path | None = None,
    ) -> None:
        self.rendered_dir = Path(rendered_dir)
        self.output_dir = Path(output_dir)
        self.pdftoppm = pdftoppm
        self.musescore_pdf = Path(musescore_pdf) if musescore_pdf else None

    # ------------------------------------------------------------------
    # measure -> page mapping
    # ------------------------------------------------------------------

    def build_measure_map(self, raw_xml: str | Path) -> dict:
        """Map (part_id, measure_number) -> MeasureLocation using
        <print new-page/new-system> events from the raw MusicXML."""
        tree = etree.parse(str(raw_xml))
        root = tree.getroot()
        mapping: dict[str, dict[str, MeasureLocation]] = {}

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")
            part_map: dict[str, MeasureLocation] = {}
            page = 1
            system = 0
            systems_on_page = {1: 1}
            measure_numbers = [m.get("number", "?") for m in part_elem.findall("measure")]
            for idx, meas in enumerate(part_elem.findall("measure")):
                mn = meas.get("number", "?")
                prints = [c for c in meas if _local(c.tag) == "print"]
                for p in prints:
                    if p.get("new-page") == "yes":
                        page += 1
                        system = 0
                        systems_on_page.setdefault(page, 1)
                    if p.get("new-system") == "yes":
                        system += 1
                        systems_on_page[page] = max(systems_on_page.get(page, 1), system + 1)
                part_map[mn] = MeasureLocation(page=page, system=system, exact=True)

            # count total systems per page from the print events of the whole
            # part (number of new-system events between page breaks + 1)
            systems_per_page: dict[int, int] = {}
            page_i = 1
            sys_count = 1
            for meas in part_elem.findall("measure"):
                for p in (c for c in meas if _local(c.tag) == "print"):
                    if p.get("new-page") == "yes":
                        systems_per_page[page_i] = sys_count
                        page_i += 1
                        sys_count = 1
                    if p.get("new-system") == "yes":
                        sys_count += 1
                systems_per_page[page_i] = sys_count

            mapping[part_id] = part_map
            mapping[f"{part_id}__systems_per_page"] = systems_per_page
            mapping[f"{part_id}__measure_count"] = len(measure_numbers)
        return mapping

    # ------------------------------------------------------------------
    # evidence package generation
    # ------------------------------------------------------------------

    def generate(
        self,
        issues: list[QAIssue],
        score: Score,
        raw_xml: str | Path,
        total_pages: int,
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.VISUAL_EVIDENCE)
        review_issues = [
            i
            for i in issues
            if i.status in (QAStatus.AI_REVIEW, QAStatus.HUMAN_REVIEW)
            and i.part_id
            and i.measure_number
        ]
        stage.checks_run = max(1, len(review_issues))

        if not review_issues:
            stage.status = "PASS"
            stage.issues.append(
                QAIssue(
                    issue_id="VISUAL-NONE-NEEDED",
                    category=QACategory.VISUAL_EVIDENCE,
                    check="evidence_gate",
                    status=QAStatus.PASS,
                    severity="info",
                    description="No AI_REVIEW / HUMAN_REVIEW issues with measure location — no evidence packages needed",
                )
            )
            return stage

        measure_map = self.build_measure_map(raw_xml)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # per-page thumbnails cache
        pages_meta: dict[int, dict] = {}

        for issue in review_issues:
            loc = measure_map.get(issue.part_id, {}).get(issue.measure_number)
            if loc is None:
                loc = self._estimate_location(measure_map, issue, total_pages)

            pkg_dir = self.output_dir / issue.issue_id
            pkg_dir.mkdir(parents=True, exist_ok=True)
            artifacts: list[str] = []

            # 1. original crop + page thumbnail
            png = self.rendered_dir / f"page-{loc.page:02d}.png"
            if png.exists():
                meta = pages_meta.get(loc.page)
                if meta is None:
                    from PIL import Image

                    with Image.open(png) as img:
                        w, h = img.size
                    meta = {"w": w, "h": h}
                    pages_meta[loc.page] = meta

                sys_per_page = self._systems_per_page(measure_map, issue.part_id, loc.page)
                band_h = meta["h"] / max(1, sys_per_page)
                top = max(0, int(loc.system * band_h - band_h * 0.15))
                bottom = min(meta["h"], int((loc.system + 1) * band_h + band_h * 0.15))

                crop_path = pkg_dir / "original_crop.png"
                self._crop(png, crop_path, 0, top, meta["w"], bottom)
                artifacts.append(crop_path.name)

                thumb_path = pkg_dir / "original_page.png"
                self._thumbnail(png, thumb_path)
                artifacts.append(thumb_path.name)

            # 2. MuseScore page for the same region (approximate alignment)
            if self.musescore_pdf and Path(self.musescore_pdf).exists():
                ms_page = pkg_dir / "musescore_page.png"
                self._render_ms_page(self.musescore_pdf, loc.page, ms_page)
                if ms_page.exists():
                    artifacts.append(ms_page.name)

            # 3. ScoreIR measure data
            ir_path = pkg_dir / "scoreir_measure.json"
            part = score.get_part(issue.part_id)
            ir_data: dict = {"part_id": issue.part_id, "measures": []}
            if part:
                try:
                    idx = int(issue.measure_number)
                    for measure in part.measures:
                        try:
                            if int(measure.number) in (idx - 1, idx, idx + 1):
                                ir_data["measures"].append(_measure_to_dict(measure))
                        except ValueError:
                            continue
                except ValueError:
                    pass
            ir_path.write_text(
                json.dumps(ir_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            artifacts.append(ir_path.name)

            # 4. issue JSON
            issue_path = pkg_dir / "issue.json"
            issue_path.write_text(
                json.dumps(issue.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            artifacts.append(issue_path.name)

            # 5. README
            readme = pkg_dir / "README.md"
            readme.write_text(
                "\n".join(
                    [
                        f"# Visual QA Evidence — {issue.issue_id}",
                        "",
                        f"- Category: {issue.category}",
                        f"- Part: {issue.part_id}  Measure: {issue.measure_number}",
                        f"- Status: {issue.status} ({issue.severity})",
                        f"- Mapping: page {loc.page}, system {loc.system + 1}"
                        + (" (from <print> events)" if loc.exact else " (LINEAR ESTIMATE)"),
                        "",
                        issue.description,
                        "",
                        "## What to compare",
                        "",
                        "1. `original_crop.png` — the LOCAL source region (do NOT review the whole PDF)",
                        "2. `scoreir_measure.json` — what the pipeline currently has",
                        "3. `musescore_page.png` — what the final render shows (alignment approximate)",
                        "",
                        "Decide: is the ScoreIR data faithful to the source in this region?",
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            artifacts.append(readme.name)

            stage.issues.append(
                QAIssue(
                    issue_id=f"VISUAL-PKG-{issue.issue_id}",
                    category=QACategory.VISUAL_EVIDENCE,
                    check="evidence_package",
                    status=QAStatus.PASS,
                    severity="info",
                    part_id=issue.part_id,
                    measure_number=issue.measure_number,
                    description=(
                        f"Evidence package for {issue.issue_id}: "
                        f"page {loc.page} system {loc.system + 1}"
                        + ("" if loc.exact else " (estimated)")
                    ),
                    evidence={"package_dir": str(pkg_dir), "artifacts": artifacts},
                )
            )

        stage.status = "PASS"
        return stage

    # ------------------------------------------------------------------

    @staticmethod
    def _systems_per_page(measure_map: dict, part_id: str, page: int) -> int:
        return measure_map.get(f"{part_id}__systems_per_page", {}).get(page, 8)

    def _estimate_location(self, measure_map: dict, issue: QAIssue, total_pages: int) -> MeasureLocation:
        total = measure_map.get(f"{issue.part_id}__measure_count", 1)
        try:
            idx = int(issue.measure_number)
        except ValueError:
            idx = 1
        page = max(1, min(total_pages, int(idx * total_pages / max(1, total)) + 1))
        return MeasureLocation(page=page, system=0, exact=False)

    def _crop(self, src: Path, dst: Path, left: int, top: int, right: int, bottom: int) -> None:
        try:
            from PIL import Image

            with Image.open(src) as img:
                img.crop((left, top, right, bottom)).save(dst)
        except Exception:
            pass

    def _thumbnail(self, src: Path, dst: Path, max_w: int = 1200) -> None:
        try:
            from PIL import Image

            with Image.open(src) as img:
                img.thumbnail((max_w, max_w * 4))
                img.save(dst)
        except Exception:
            pass

    def _render_ms_page(self, pdf: Path, page: int, dst: Path) -> None:
        tmp = dst.with_suffix(".tmpdir")
        try:
            subprocess.run(
                [
                    self.pdftoppm,
                    "-png",
                    "-r",
                    "150",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    str(pdf),
                    str(tmp),
                ],
                capture_output=True,
                timeout=120,
                check=True,
            )
            for cand in Path(tmp).parent.glob(f"{tmp.name}*.png"):
                shutil.move(str(cand), dst)
                break
        except Exception:
            pass
