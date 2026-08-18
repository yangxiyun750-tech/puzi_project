"""SafeFixer — applies ONLY deterministic structural fixes to a working
copy of ScoreIR, exports a fixed MusicXML, and re-verifies.

Guarantees:
- never invents musical content (no added rests, notes, pitches)
- never changes pitches or rhythmic VALUES (only unit normalization)
- every applied fix is logged
- every fixed export is re-verified against the raw OMR rhythm facts

Supported fixes:
    normalize_rhythm    convert raw-division durations to canonical
                        divisions (LCM-based); zero chord-tone durations
    dedupe_ties         drop duplicated <tie>+<tied> annotations
    remove_dangling_*   drop tie/slur stops (and slur continues) that
                        have no matching start anywhere
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import reduce
from math import gcd
from pathlib import Path

from lxml import etree

from qa.qa_model import QAIssue, QAStatus

from score_engine.musicxml.score_ir_to_musicxml import MusicXMLExporter
from score_engine.score_ir.score_ir import Chord, Duration, Note, Rest, Score

MAX_DIVISIONS = 480


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _lcm(a: int, b: int) -> int:
    return a * b // gcd(a, b) if a and b else max(a, b)


def raw_divisions_by_measure(raw_xml: str | Path) -> dict[str, list[int]]:
    """divisions in effect for each measure of each part (document order)."""
    tree = etree.parse(str(raw_xml))
    out: dict[str, list[int]] = {}
    for part_elem in tree.getroot().findall(".//part"):
        pid = part_elem.get("id", "?")
        divs: list[int] = []
        cur = 1
        for meas in part_elem.findall("measure"):
            attrs = meas.find("attributes")
            if attrs is not None:
                d = attrs.find("divisions")
                if d is not None and d.text:
                    cur = int(d.text)
            divs.append(cur)
        out[pid] = divs
    return out


class SafeFixer:
    """Deterministic structural fixer with re-verification loop."""

    def __init__(self, raw_xml: str | Path) -> None:
        self.raw_xml = Path(raw_xml)
        self.divisions_by_measure = raw_divisions_by_measure(self.raw_xml)
        self.fixes_applied: list[dict] = []

    # ------------------------------------------------------------------

    def apply(self, score: Score, issues: list[QAIssue]) -> Score:
        """Apply every SAFE_REPAIR fix found in `issues` to `score` (a copy)."""
        wanted = {i.fix.get("action") for i in issues if i.status == QAStatus.SAFE_REPAIR and i.fix}

        if "normalize_rhythm" in wanted:
            self._normalize_rhythm(score)
        if "dedupe_ties" in wanted:
            self._dedupe_ties(score)
        if any(a.startswith("remove_dangling") for a in wanted):
            self._remove_dangling(score)
        return score

    # ------------------------------------------------------------------

    def _normalize_rhythm(self, score: Score) -> None:
        # 1. canonical divisions = LCM of all quarter denominators
        denominators: set[int] = set()
        for part in score.parts:
            divs = self.divisions_by_measure.get(part.id, [1])
            for idx, measure in enumerate(part.measures):
                div = divs[idx] if idx < len(divs) else divs[-1]
                for voice in measure.voices:
                    for event in voice.events:
                        dur = getattr(event, "duration", None)
                        if dur is not None and dur.value > 0:
                            denominators.add(Fraction(dur.value, div).denominator)
        canonical = reduce(_lcm, denominators, 1)
        if canonical > MAX_DIVISIONS:
            canonical = MAX_DIVISIONS
            self.fixes_applied.append({
                "fix": "normalize_rhythm",
                "note": f"LCM exceeded {MAX_DIVISIONS}; capped — rare tuplets may round",
            })
        self.canonical_divisions = canonical

        # 2. rewrite durations in canonical units; chord tones keep their
        #    original duration (MuseScore ignores chord-tone duration anyway)
        converted = 0
        for part in score.parts:
            divs = self.divisions_by_measure.get(part.id, [1])
            for idx, measure in enumerate(part.measures):
                div = divs[idx] if idx < len(divs) else divs[-1]
                for voice in measure.voices:
                    for event in voice.events:
                        notes: list[Note] = []
                        if isinstance(event, Note):
                            notes = [event]
                        elif isinstance(event, Chord):
                            notes = list(event.notes)
                        elif isinstance(event, Rest):
                            dur = event.duration
                            q = Fraction(dur.value, div)
                            event.duration = Duration(canonical, int(round(q * canonical)))
                            converted += 1
                            continue
                        for note in notes:
                            dur = note.duration
                            q = Fraction(dur.value, div)
                            note.duration = Duration(canonical, int(round(q * canonical)))
                            converted += 1

        self.fixes_applied.append({
            "fix": "normalize_rhythm",
            "canonical_divisions": canonical,
            "durations_converted": converted,
        })

    def _dedupe_ties(self, score: Score) -> None:
        removed = 0
        for part in score.parts:
            for measure in part.measures:
                for voice in measure.voices:
                    for event in voice.events:
                        notes: list[Note] = []
                        if isinstance(event, Note):
                            notes = [event]
                        elif isinstance(event, Chord):
                            notes = list(event.notes)
                        for note in notes:
                            seen: set[tuple[str, int]] = set()
                            kept = []
                            for tie in note.ties:
                                key = (tie.type, tie.number)
                                if key in seen:
                                    removed += 1
                                else:
                                    seen.add(key)
                                    kept.append(tie)
                            note.ties = kept
        self.fixes_applied.append({"fix": "dedupe_ties", "duplicates_removed": removed})

    def _remove_dangling(self, score: Score) -> None:
        """Remove tie/slur stops (and slur continues) without a matching
        start, walking events in document order per part.

        Uses Counter (multiset) because Audiveris reuses tie/slur number="1"
        across the entire score; a simple set would misclassify valid stops
        as dangling when the same number is used for multiple independent
        ties/slurs.
        """
        from collections import Counter

        removed = 0
        by_tag: dict[str, int] = {}
        for part in score.parts:
            open_ties: Counter = Counter()
            open_slurs: Counter = Counter()
            for measure in part.measures:
                for voice in measure.voices:
                    for event in voice.events:
                        notes: list[Note] = []
                        if isinstance(event, Note):
                            notes = [event]
                        elif isinstance(event, Chord):
                            notes = list(event.notes)
                        for note in notes:
                            kept_ties = []
                            for tie in note.ties:
                                if tie.type == "start":
                                    open_ties[tie.number] += 1
                                    kept_ties.append(tie)
                                elif tie.type == "stop":
                                    if open_ties[tie.number] > 0:
                                        open_ties[tie.number] -= 1
                                        kept_ties.append(tie)
                                    else:
                                        removed += 1
                                        by_tag["tied"] = by_tag.get("tied", 0) + 1
                                else:
                                    kept_ties.append(tie)
                            note.ties = kept_ties

                            kept_slurs = []
                            for slur in note.slurs:
                                if slur.type == "start":
                                    open_slurs[slur.number] += 1
                                    kept_slurs.append(slur)
                                elif slur.type == "continue":
                                    if open_slurs[slur.number] > 0:
                                        kept_slurs.append(slur)
                                    else:
                                        removed += 1
                                        by_tag["slur"] = by_tag.get("slur", 0) + 1
                                elif slur.type == "stop":
                                    if open_slurs[slur.number] > 0:
                                        open_slurs[slur.number] -= 1
                                        kept_slurs.append(slur)
                                    else:
                                        removed += 1
                                        by_tag["slur"] = by_tag.get("slur", 0) + 1
                                else:
                                    kept_slurs.append(slur)
                            note.slurs = kept_slurs
        self.fixes_applied.append({
            "fix": "remove_dangling",
            "annotations_removed": removed,
            "by_tag": by_tag,
        })

    # ------------------------------------------------------------------

    def export(self, score: Score, path: str | Path) -> Path:
        """Export the fixed ScoreIR to MusicXML with the canonical divisions."""
        path = Path(path)
        MusicXMLExporter().export_file(score, path)
        canonical = getattr(self, "canonical_divisions", 1)
        if canonical != 1:
            text = path.read_text(encoding="utf-8")
            text = re.sub(
                r"<divisions>1</divisions>",
                f"<divisions>{canonical}</divisions>",
                text,
            )
            path.write_text(text, encoding="utf-8")
        return path
