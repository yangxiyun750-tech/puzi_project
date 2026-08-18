"""Notation detector for raw OMR MusicXML.

Validates pairing of tied/slurred/tuplet notation objects. Uses Counter
for ties and slurs because Audiveris reuses number="1" across the entire
score; a simple set would misclassify valid stops as dangling.

No auto-fixes are performed. Unmatched starts/stops are reported as OMR
errors for human/AI review.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from lxml import etree

from omr_normalization.detectors.base import OMRDetector, _local
from omr_normalization.issue_model import OMRCategory, OMREditSafety, OMRIssue, OMRStatus


class NotationDetector(OMRDetector):
    """Detect notation-object pairing defects in raw OMR MusicXML."""

    name = "notation"

    def detect(self, tree: etree._ElementTree, input_path: str = "") -> list[OMRIssue]:
        issues: list[OMRIssue] = []
        root = tree.getroot()

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")

            # Per-part pairing state
            open_tie: Counter = Counter()
            open_slur: Counter = Counter()
            open_tuplet: dict[str, str] = {}
            open_gliss: dict[str, str] = {}
            open_octave: dict[str, str] = {}
            open_wedge: dict[str, str] = {}

            for meas in part_elem.findall("measure"):
                mn = meas.get("number", "?")
                notes = [c for c in meas if _local(c.tag) == "note"]

                for note in notes:
                    n_voice = note.findtext("voice", "1")
                    n_id = note.get("id", "")
                    loc = f"M{mn}-V{n_voice}"
                    notations = note.find("notations")
                    if notations is None:
                        continue

                    for child in notations:
                        tag = _local(child.tag)
                        n_type = child.get("type", "")
                        n_num = child.get("number", "1")

                        if tag == "tied":
                            if n_type == "start":
                                open_tie[n_num] += 1
                            elif n_type == "stop":
                                if open_tie[n_num] > 0:
                                    open_tie[n_num] -= 1
                                else:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-TIE-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="tie_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Tie stop without a matching start ({loc})"
                                            ),
                                            evidence={"tie_number": n_num},
                                        )
                                    )

                        elif tag == "slur":
                            if n_type == "start":
                                open_slur[n_num] += 1
                            elif n_type == "continue":
                                if open_slur[n_num] <= 0:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-SLUR-DANGLE-CONT-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="slur_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Slur continue without an open slur ({loc})"
                                            ),
                                            evidence={"slur_number": n_num},
                                        )
                                    )
                            elif n_type == "stop":
                                if open_slur[n_num] > 0:
                                    open_slur[n_num] -= 1
                                else:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-SLUR-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="slur_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Slur stop without a matching start ({loc})"
                                            ),
                                            evidence={"slur_number": n_num},
                                        )
                                    )

                        elif tag == "tuplet":
                            if n_type == "start":
                                open_tuplet[n_num] = loc
                            elif n_type == "stop":
                                if n_num not in open_tuplet:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-TUPLET-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="tuplet_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Tuplet stop without a matching start ({loc})"
                                            ),
                                            evidence={"tuplet_number": n_num},
                                        )
                                    )
                                else:
                                    open_tuplet.pop(n_num, None)

                        elif tag == "glissando":
                            if n_type == "start":
                                open_gliss[n_num] = loc
                            elif n_type == "stop":
                                if n_num not in open_gliss:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-GLISS-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="glissando_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Glissando stop without a matching start ({loc})"
                                            ),
                                            evidence={"glissando_number": n_num},
                                        )
                                    )
                                else:
                                    open_gliss.pop(n_num, None)

                        elif tag == "octave-shift":
                            key = f"{n_type}:{n_num}"
                            if n_type in ("up", "down"):
                                open_octave[key] = loc
                            elif n_type == "stop":
                                if key not in open_octave:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-OCTAVE-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="octave_shift_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="medium",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Ottava stop without a matching start ({loc})"
                                            ),
                                            evidence={"octave_shift_number": n_num},
                                        )
                                    )
                                else:
                                    open_octave.pop(key, None)

                        elif tag == "wedge":
                            key = f"{n_type}:{n_num}"
                            if n_type in ("crescendo", "diminuendo"):
                                open_wedge[key] = loc
                            elif n_type == "stop":
                                stop_keys = [k for k in open_wedge if k.endswith(f":{n_num}")]
                                if not stop_keys:
                                    issues.append(
                                        self._make_issue(
                                            issue_id=f"NOT-WEDGE-DANGLE-STOP-{part_id}-M{mn}-{n_num}",
                                            category=OMRCategory.NOTATION,
                                            check="wedge_pairing",
                                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                                            severity="low",
                                            part_id=part_id,
                                            measure_number=mn,
                                            voice_id=f"{part_id}-V{n_voice}",
                                            note_id=n_id,
                                            description=(
                                                f"Hairpin stop without a matching start ({loc})"
                                            ),
                                            evidence={"wedge_number": n_num},
                                        )
                                    )
                                else:
                                    for k in stop_keys:
                                        open_wedge.pop(k, None)

            # End-of-part unterminated starts
            for num, count in open_tie.items():
                if count > 0:
                    issues.append(
                        self._make_issue(
                            issue_id=f"NOT-TIE-UNTERMINATED-{part_id}-{num}",
                            category=OMRCategory.NOTATION,
                            check="tie_pairing",
                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                            severity="medium",
                            part_id=part_id,
                            description=(
                                f"Tie #{num} starts {count} time(s) but never stops"
                            ),
                            evidence={"unterminated_count": count, "tie_number": num},
                        )
                    )

            for num, count in open_slur.items():
                if count > 0:
                    issues.append(
                        self._make_issue(
                            issue_id=f"NOT-SLUR-UNTERMINATED-{part_id}-{num}",
                            category=OMRCategory.NOTATION,
                            check="slur_pairing",
                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                            severity="medium",
                            part_id=part_id,
                            description=(
                                f"Slur #{num} starts {count} time(s) but never stops"
                            ),
                            evidence={"unterminated_count": count, "slur_number": num},
                        )
                    )

            for kind, open_map, label in (
                ("tuplet", open_tuplet, "Tuplet"),
                ("glissando", open_gliss, "Glissando"),
                ("octave-shift", open_octave, "Ottava"),
                ("wedge", open_wedge, "Hairpin"),
            ):
                for key, loc in open_map.items():
                    issues.append(
                        self._make_issue(
                            issue_id=f"NOT-{kind.upper()}-UNTERMINATED-{part_id}-{key}",
                            category=OMRCategory.NOTATION,
                            check=f"{kind}_pairing",
                            status=OMRStatus.OMR_ERROR, edit_safety=OMREditSafety.NON_BLOCKING,
                            severity="medium",
                            part_id=part_id,
                            measure_number=loc.split("-")[0].replace("M", ""),
                            voice_id=loc.split("-")[1] if "-" in loc else "",
                            description=(
                                f"{label} #{key} starts at {loc} but never stops"
                            ),
                            evidence={"start_location": loc},
                        )
                    )

        return issues
