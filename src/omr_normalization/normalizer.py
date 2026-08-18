"""OMR Normalizer — optional preprocessing layer between raw OMR and Score Engine.

The normalizer reads raw MusicXML, runs a set of generic detectors, applies
only deterministic safe fixes, and writes a normalized MusicXML alongside
an issue report. The raw input file is never modified.
"""

from __future__ import annotations

import shutil
from fractions import Fraction
from pathlib import Path
from typing import Any

from lxml import etree

from omr_normalization.detectors import (
    DivisionsDetector,
    NotationDetector,
    RhythmDetector,
    StructureDetector,
)
from omr_normalization.issue_model import (
    OMRCategory,
    OMRNormalizationReport,
    OMRIssue,
    OMRStatus,
)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class OMRNormalizer:
    """Optional preprocessing wrapper for raw OMR MusicXML.

    Usage:
        normalizer = OMRNormalizer()
        report = normalizer.normalize("raw.musicxml", "normalized.musicxml")

    The existing direct import path remains valid:
        score = MusicXMLImporter().import_file("raw.musicxml")
    """

    def __init__(self) -> None:
        self.detectors = [
            RhythmDetector(),
            StructureDetector(),
            DivisionsDetector(),
            NotationDetector(),
        ]

    def normalize(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        *,
        apply_safe_fixes: bool = True,
    ) -> OMRNormalizationReport:
        """Run detectors and produce a normalized MusicXML + report."""
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path.with_suffix(".normalized.musicxml")
        else:
            output_path = Path(output_path)

        tree = etree.parse(str(input_path))

        # Detection phase
        issues: list[OMRIssue] = []
        for detector in self.detectors:
            issues.extend(detector.detect(tree, str(input_path)))

        # Safe-fix phase
        fixes_applied: list[dict[str, Any]] = []
        if apply_safe_fixes:
            tree, fixes = self._apply_safe_fixes(tree)
            fixes_applied.extend(fixes)

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tree.write(str(output_path), encoding="utf-8", xml_declaration=True)

        # Update issue statuses to reflect safe fixes that were applied.
        updated_issues = self._mark_applied_fixes(issues, fixes_applied)

        return OMRNormalizationReport(
            input_path=str(input_path),
            output_path=str(output_path) if output_path else None,
            issues=updated_issues,
            fixes_applied=fixes_applied,
        )

    def detect_only(self, input_path: str | Path) -> OMRNormalizationReport:
        """Run detectors without writing a normalized file."""
        input_path = Path(input_path)
        tree = etree.parse(str(input_path))
        issues: list[OMRIssue] = []
        for detector in self.detectors:
            issues.extend(detector.detect(tree, str(input_path)))
        return OMRNormalizationReport(
            input_path=str(input_path),
            output_path=None,
            issues=issues,
            fixes_applied=[],
        )

    # ------------------------------------------------------------------
    # Issue status updates
    # ------------------------------------------------------------------

    def _mark_applied_fixes(
        self,
        issues: list[OMRIssue],
        fixes_applied: list[dict[str, Any]],
    ) -> list[OMRIssue]:
        """Rewrite issue statuses for issues that were fully resolved by safe fixes.

        A forward_element issue is marked SAFE_FIX_APPLIED only when every
        <forward> in that measure was converted. Partial conversions remain
        OMR_ERROR so the gate still sees unresolved missing content.
        """
        updated: list[OMRIssue] = []
        forward_fixes = {
            (f["part_id"], f["measure_number"]): f
            for f in fixes_applied
            if f.get("fix_type") == "forward_to_rest"
        }
        for issue in issues:
            if issue.check != "forward_element":
                updated.append(issue)
                continue
            key = (issue.part_id, issue.measure_number)
            fix = forward_fixes.get(key)
            forward_count = issue.evidence.get("forward_count", 0)
            if fix is not None and fix.get("count", 0) >= forward_count:
                issue.status = OMRStatus.SAFE_FIX_APPLIED
                issue.fix = fix
            elif fix is not None:
                # Partial conversion: keep error but record progress.
                issue.evidence["converted_forwards"] = fix.get("count", 0)
            updated.append(issue)
        return updated

    # ------------------------------------------------------------------
    # Safe fixes
    # ------------------------------------------------------------------

    def _apply_safe_fixes(
        self, tree: etree._ElementTree
    ) -> tuple[etree._ElementTree, list[dict[str, Any]]]:
        """Apply only provably-correct fixes to a copy of the tree.

        Currently supported:
        - Convert <forward> elements to explicit <rest> elements when the
          conversion does not itself create measure overflow.
        """
        # Work on a deep copy so the original tree is not mutated.
        new_tree = etree.ElementTree(etree.fromstring(etree.tostring(tree.getroot())))
        root = new_tree.getroot()
        fixes: list[dict[str, Any]] = []

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")
            cur_divisions = 1
            cur_time = Fraction(4)

            for meas in part_elem.findall("measure"):
                mn = meas.get("number", "?")
                implicit = meas.get("implicit", "no") == "yes"

                attrs = meas.find("attributes")
                if attrs is not None:
                    div_elem = attrs.find("divisions")
                    if div_elem is not None and div_elem.text:
                        cur_divisions = int(div_elem.text)
                    time_elem = attrs.find("time")
                    if time_elem is not None:
                        beats = int(time_elem.findtext("beats", "4") or 4)
                        beat_type = int(time_elem.findtext("beat-type", "4") or 4)
                        cur_time = Fraction(beats * 4, beat_type)

                if implicit:
                    # Do not auto-fix pickup measures.
                    continue

                expected = cur_time
                # Per-voice totals from real note events only (excluding forwards).
                note_totals: dict[str, Fraction] = {}
                active_voice = "1"
                forward_elems: list[tuple[etree._Element, str, Fraction]] = []

                # First pass: compute note totals and collect forwards in order.
                for child in meas:
                    tag = _local(child.tag)
                    if tag == "note":
                        active_voice = child.findtext("voice", active_voice) or active_voice
                        is_chord = child.find("chord") is not None
                        is_grace = child.find("grace") is not None
                        if is_chord or is_grace:
                            continue
                        dur = int(child.findtext("duration", "0") or 0)
                        q = Fraction(dur, cur_divisions)
                        note_totals[active_voice] = note_totals.get(active_voice, Fraction(0)) + q
                    elif tag == "forward":
                        active_voice = child.findtext("voice", active_voice) or active_voice
                        dur = int(child.findtext("duration", "0") or 0)
                        q = Fraction(dur, cur_divisions)
                        forward_elems.append((child, active_voice, q))
                    elif tag == "backup":
                        pass

                # Second pass: convert forwards to rests only when provably safe.
                # We maintain a running total per voice of notes + already-converted rests.
                converted = 0
                running_totals = dict(note_totals)
                for fwd_elem, voice, q in forward_elems:
                    current_total = running_totals.get(voice, Fraction(0))
                    if current_total + q <= expected + EPSILON:
                        rest_note = self._forward_to_rest(fwd_elem, cur_divisions)
                        if rest_note is not None:
                            meas.replace(fwd_elem, rest_note)
                            converted += 1
                            running_totals[voice] = current_total + q

                if converted:
                    fixes.append({
                        "part_id": part_id,
                        "measure_number": mn,
                        "fix_type": "forward_to_rest",
                        "count": converted,
                    })

        return new_tree, fixes

    def _forward_to_rest(
        self, fwd_elem: etree._Element, divisions: int
    ) -> etree._Element | None:
        """Create a <note><rest/> ... </note> element from a <forward> element.

        Preserves voice and duration. The rest type is inferred from duration
        when possible; otherwise it defaults to the MusicXML type matching the
        raw duration value.
        """
        voice = fwd_elem.findtext("voice", "1")
        dur_text = fwd_elem.findtext("duration", "0")
        try:
            dur = int(dur_text)
        except (TypeError, ValueError):
            return None

        note = etree.Element("note")
        rest = etree.SubElement(note, "rest")
        _ = rest  # explicitly create child
        dur_el = etree.SubElement(note, "duration")
        dur_el.text = str(dur)
        voice_el = etree.SubElement(note, "voice")
        voice_el.text = voice

        # Best-effort type inference. Exact rendering is left to the importer.
        q = Fraction(dur, divisions)
        type_name = self._quarters_to_type(q)
        if type_name:
            type_el = etree.SubElement(note, "type")
            type_el.text = type_name

        return note

    @staticmethod
    def _quarters_to_type(q: Fraction) -> str:
        """Map a quarter-note fraction to a MusicXML note type name."""
        mapping = [
            (Fraction(8), "breve"),
            (Fraction(4), "whole"),
            (Fraction(2), "half"),
            (Fraction(1), "quarter"),
            (Fraction(1, 2), "eighth"),
            (Fraction(1, 4), "16th"),
            (Fraction(1, 8), "32nd"),
            (Fraction(1, 16), "64th"),
        ]
        for value, name in mapping:
            if q == value:
                return name
        return ""


# Small epsilon used for floating-point-like fraction comparisons.
EPSILON = Fraction(1, 128)
