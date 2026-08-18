"""Rhythm detector for raw OMR MusicXML.

Parses MusicXML using real <divisions> values and checks per-voice
measure totals against the current time signature. Detects overflow,
underflow, and explicit <forward> elements (which represent missing
rests in the source OMR).

No MusicXML-specific filenames, part IDs, or measure numbers are
hard-coded. All decisions come from MusicXML structure and music-theory
invariants.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from lxml import etree

from omr_normalization.detectors.base import OMRDetector, _local
from omr_normalization.issue_model import OMRCategory, OMREditSafety, OMRIssue, OMRStatus

EPSILON = Fraction(1, 128)

TYPE_QUARTERS = {
    "breve": Fraction(8),
    "whole": Fraction(4),
    "half": Fraction(2),
    "quarter": Fraction(1),
    "eighth": Fraction(1, 2),
    "16th": Fraction(1, 4),
    "32nd": Fraction(1, 8),
    "64th": Fraction(1, 16),
    "128th": Fraction(1, 32),
}


class RhythmDetector(OMRDetector):
    """Detect rhythmic defects in raw OMR MusicXML."""

    name = "rhythm"

    def detect(self, tree: etree._ElementTree, input_path: str = "") -> list[OMRIssue]:
        issues: list[OMRIssue] = []
        root = tree.getroot()

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

                voice_totals: dict[str, Fraction] = {}
                forward_count = 0
                active_voice = "1"

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
                        voice_totals[active_voice] = voice_totals.get(active_voice, Fraction(0)) + q
                    elif tag == "forward":
                        forward_count += 1
                        active_voice = child.findtext("voice", active_voice) or active_voice
                        dur = int(child.findtext("duration", "0") or 0)
                        q = Fraction(dur, cur_divisions)
                        voice_totals[active_voice] = voice_totals.get(active_voice, Fraction(0)) + q
                    elif tag == "backup":
                        # backup does not itself create content; we note it for
                        # multi-voice structure but do not add to totals.
                        pass

                if forward_count:
                    issues.append(
                        self._make_issue(
                            issue_id=f"RHY-FORWARD-{part_id}-M{mn}",
                            category=OMRCategory.RHYTHM,
                            check="forward_element",
                            status=OMRStatus.OMR_ERROR,
                            severity="medium",
                            edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                            part_id=part_id,
                            measure_number=mn,
                            description=(
                                f"Measure contains {forward_count} explicit <forward> element(s) "
                                f"representing missing rests in the OMR output"
                            ),
                            evidence={"forward_count": forward_count},
                        )
                    )

                for voice, total in voice_totals.items():
                    if implicit:
                        # Pickup measures: only flag overflow, not underflow.
                        if total > cur_time + EPSILON:
                            issues.append(
                                self._make_issue(
                                    issue_id=f"RHY-OVERFLOW-{part_id}-M{mn}-V{voice}",
                                    category=OMRCategory.RHYTHM,
                                    check="measure_overflow",
                                    status=OMRStatus.OMR_ERROR,
                                    severity="high",
                                    edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                                    part_id=part_id,
                                    measure_number=mn,
                                    voice_id=f"{part_id}-V{voice}",
                                    description=(
                                        f"Pickup measure voice {voice} overflows: "
                                        f"{total} quarters vs {cur_time} expected"
                                    ),
                                    evidence={
                                        "actual_quarters": str(total),
                                        "expected_quarters": str(cur_time),
                                        "overflow": str(total - cur_time),
                                    },
                                )
                            )
                        continue

                    if total > cur_time + EPSILON:
                        issues.append(
                            self._make_issue(
                                issue_id=f"RHY-OVERFLOW-{part_id}-M{mn}-V{voice}",
                                category=OMRCategory.RHYTHM,
                                check="measure_overflow",
                                status=OMRStatus.OMR_ERROR,
                                severity="high",
                                edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                                part_id=part_id,
                                measure_number=mn,
                                voice_id=f"{part_id}-V{voice}",
                                description=(
                                    f"Measure voice {voice} overflows: "
                                    f"{total} quarters vs {cur_time} expected"
                                ),
                                evidence={
                                    "actual_quarters": str(total),
                                    "expected_quarters": str(cur_time),
                                    "overflow": str(total - cur_time),
                                },
                            )
                        )
                    elif total < cur_time - EPSILON:
                        issues.append(
                            self._make_issue(
                                issue_id=f"RHY-UNDERFLOW-{part_id}-M{mn}-V{voice}",
                                category=OMRCategory.RHYTHM,
                                check="measure_underflow",
                                status=OMRStatus.OMR_ERROR,
                                severity="high",
                                edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                                part_id=part_id,
                                measure_number=mn,
                                voice_id=f"{part_id}-V{voice}",
                                description=(
                                    f"Measure voice {voice} underflows: "
                                    f"{total} quarters vs {cur_time} expected "
                                    f"(OMR lost content)"
                                ),
                                evidence={
                                    "actual_quarters": str(total),
                                    "expected_quarters": str(cur_time),
                                    "missing": str(cur_time - total),
                                },
                            )
                        )

        return issues
