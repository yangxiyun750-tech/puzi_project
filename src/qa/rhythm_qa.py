"""Rhythm / Meter QA.

Parses MusicXML directly with REAL <divisions> values (the ScoreIR
importer normalizes everything to divisions=1, so rhythm QA cannot
trust ScoreIR durations) and checks per voice:

- measure total vs time signature  -> overflow (AI_REVIEW) / underflow (HUMAN_REVIEW)
- gaps between consecutive events  -> missing rests (AI_REVIEW)
- tuplet spans                     -> pairing and nominal ratio report
- raw OMR XML vs ScoreIR-exported XML rhythm equality
    -> mismatches are SAFE_REPAIR (deterministic: divisions normalization,
       zeroed chord-tone durations) and are re-verified after the fix.

Chord tones (<chord/>) are excluded from voice sums per MusicXML spec
(only the first note of a chord carries duration); Audiveris writes
full durations on chord tones, which inflates naive sums.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

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


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class _MeasureRhythm:
    __slots__ = ("number", "divisions", "expected", "implicit", "voices", "gaps", "tuplets")

    def __init__(self, number: str, divisions: int, expected: Fraction, implicit: bool):
        self.number = number
        self.divisions = divisions
        self.expected = expected
        self.implicit = implicit
        self.voices: dict[str, Fraction] = {}
        self.gaps: list[tuple[str, str, str]] = []  # (voice, gap_quarters, after_note)
        self.tuplets: list[dict] = []


def parse_rhythm(xml_path: str | Path) -> dict:
    """Parse per-part rhythm facts from a MusicXML file.

    Returns: {part_id: {"measures": [ {number, divisions, expected,
        implicit, voices: {voice: total_quarters}, gaps: [...], tuplets: [...]},
        ...], "divisions_seen": [..]}}
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    parts: dict[str, dict] = {}

    for part_elem in root.findall(".//part"):
        part_id = part_elem.get("id", "P?")
        measures: list[dict] = []
        divisions_seen: list[int] = []
        cur_time = Fraction(4)  # default 4/4 before any attributes
        cur_divisions = 1

        for meas in part_elem.findall("measure"):
            number = meas.get("number", "?")
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
            divisions_seen.append(cur_divisions)

            mr = _MeasureRhythm(number, cur_divisions, cur_time, implicit)
            voice = "1"
            onset: dict[str, Fraction] = {}
            forward_count = 0
            open_tuplets: dict[str, Fraction] = {}  # number -> start onset
            tuplet_notes: dict[str, list[dict]] = {}  # number -> notes inside

            for child in meas:
                tag = _local(child.tag)
                if tag == "note":
                    n_voice = child.findtext("voice", voice) or voice
                    voice = n_voice
                    is_chord = child.find("chord") is not None
                    is_grace = child.find("grace") is not None
                    dur_elem = child.find("duration")
                    dur_text = dur_elem.text if dur_elem is not None else None
                    dur = int(dur_text) if dur_text else 0
                    q = Fraction(0)
                    if not is_chord and not is_grace:
                        q = Fraction(dur, cur_divisions)

                    start = onset.get(voice, Fraction(0))
                    if not is_chord and not is_grace:
                        # chord tones carry no time per MusicXML spec
                        mr.voices[voice] = mr.voices.get(voice, Fraction(0)) + q
                    if not is_grace:
                        onset[voice] = start + q

                    # tuplets
                    notations = child.find("notations")
                    if notations is not None:
                        for tup in notations.findall("tuplet"):
                            t_type = tup.get("type", "")
                            t_num = tup.get("number", "1")
                            if t_type == "start":
                                open_tuplets[t_num] = start
                                tuplet_notes[t_num] = []
                            elif t_type == "stop":
                                stop_onset = start + q
                                span = stop_onset - open_tuplets.get(t_num, start)
                                notes = tuplet_notes.get(t_num, [])
                                types = {n["type"] for n in notes}
                                mr.tuplets.append({
                                    "number": t_num,
                                    "span_quarters": str(span),
                                    "note_count": len(notes),
                                    "note_types": sorted(types),
                                    "consistent_types": len(types) <= 1,
                                })
                                open_tuplets.pop(t_num, None)
                                tuplet_notes.pop(t_num, None)
                    # collect tuplet member notes (non-chord, non-grace)
                    if not is_chord and not is_grace and open_tuplets:
                        n_type = child.findtext("type", "")
                        for t_num in open_tuplets:
                            tuplet_notes.setdefault(t_num, []).append(
                                {"type": n_type, "id": child.get("id", "")}
                            )
                elif tag == "backup":
                    voice = str(int(voice) + 1) if voice.isdigit() else voice
                elif tag == "forward":
                    # explicit time-forward: silence written without a rest —
                    # suspicious, usually a missing rest in the source data
                    forward_count += 1
                    f_dur = int(child.findtext("duration", "0") or 0)
                    onset[voice] = onset.get(voice, Fraction(0)) + Fraction(f_dur, cur_divisions)

            if forward_count:
                mr.gaps.append((voice, str(forward_count), "explicit time-forward"))

            measures.append({
                "number": mr.number,
                "divisions": mr.divisions,
                "expected": str(mr.expected),
                "implicit": mr.implicit,
                "voices": {v: str(q) for v, q in mr.voices.items()},
                "gaps": mr.gaps,
                "tuplets": mr.tuplets,
            })

        parts[part_id] = {"measures": measures, "divisions_seen": divisions_seen}

    return parts


class RhythmQA:
    """Rhythm and meter QA for one MusicXML (raw OMR or ScoreIR-exported)."""

    def run(self, raw_xml: str | Path, exported_xml: str | Path) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.RHYTHM_METER)
        raw = parse_rhythm(raw_xml)
        exported = parse_rhythm(exported_xml) if Path(exported_xml).exists() else {}

        for part_id, data in raw.items():
            # --- divisions consistency ------------------------------------
            stage.checks_run += 1
            uniq = sorted(set(data["divisions_seen"]))
            if len(uniq) > 1:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"RHYTHM-DIVISIONS-VARY-{part_id}",
                        category=QACategory.RHYTHM_METER,
                        check="divisions_consistency",
                        status=QAStatus.PASS,
                        severity="info",
                        part_id=part_id,
                        description=f"{part_id} changes divisions mid-part: {uniq}",
                        evidence={"divisions": uniq},
                    )
                )

            # --- per measure: overflow / underflow / gaps / tuplets --------
            for m in data["measures"]:
                expected = Fraction(m["expected"])
                for voice, total_s in m["voices"].items():
                    total = Fraction(total_s)
                    stage.checks_run += 1
                    if m["implicit"]:
                        # pickup measure: shorter than full is normal
                        if total > expected:
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"RHYTHM-OVERFLOW-{part_id}-M{m['number']}-V{voice}",
                                    category=QACategory.RHYTHM_METER,
                                    check="measure_total_overflow",
                                    status=QAStatus.AI_REVIEW,
                                    severity="high",
                                    part_id=part_id,
                                    measure_number=m["number"],
                                    voice_id=f"{part_id}-V{voice}",
                                    description=(
                                        f"Pickup measure M{m['number']} voice {voice} has "
                                        f"{total} quarters > {expected} expected"
                                    ),
                                    evidence={"actual_quarters": str(total), "expected": str(expected)},
                                )
                            )
                        continue
                    if total > expected + EPSILON:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"RHYTHM-OVERFLOW-{part_id}-M{m['number']}-V{voice}",
                                category=QACategory.RHYTHM_METER,
                                check="measure_total_overflow",
                                status=QAStatus.AI_REVIEW,
                                severity="high",
                                part_id=part_id,
                                measure_number=m["number"],
                                voice_id=f"{part_id}-V{voice}",
                                description=(
                                    f"Measure M{m['number']} voice {voice} overflows: "
                                    f"{total} quarters vs {expected} expected "
                                    f"(OMR added rhythmic content)"
                                ),
                                evidence={
                                    "actual_quarters": str(total),
                                    "expected": str(expected),
                                    "overflow": str(total - expected),
                                },
                            )
                        )
                    elif total < expected - EPSILON:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"RHYTHM-UNDERFLOW-{part_id}-M{m['number']}-V{voice}",
                                category=QACategory.RHYTHM_METER,
                                check="measure_total_underflow",
                                status=QAStatus.HUMAN_REVIEW,
                                severity="high",
                                part_id=part_id,
                                measure_number=m["number"],
                                voice_id=f"{part_id}-V{voice}",
                                description=(
                                    f"Measure M{m['number']} voice {voice} underflows: "
                                    f"{total} quarters vs {expected} expected "
                                    f"(content lost by OMR — never auto-filled)"
                                ),
                                evidence={
                                    "actual_quarters": str(total),
                                    "expected": str(expected),
                                    "missing": str(expected - total),
                                },
                            )
                        )

                for voice, gap_q, after in m["gaps"]:
                    stage.checks_run += 1
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RHYTHM-GAP-{part_id}-M{m['number']}-V{voice}",
                            category=QACategory.RHYTHM_METER,
                            check="missing_rest",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part_id,
                            measure_number=m["number"],
                            voice_id=f"{part_id}-V{voice}",
                            description=(
                                f"Measure M{m['number']} uses {gap_q} explicit "
                                f"time-forward element(s) instead of rests — "
                                f"possible missing rest"
                            ),
                            evidence={"forward_count": gap_q},
                            confidence="medium",
                        )
                    )

                for tup in m["tuplets"]:
                    stage.checks_run += 1
                    if not tup["consistent_types"]:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"RHYTHM-TUPLET-MIXED-{part_id}-M{m['number']}",
                                category=QACategory.RHYTHM_METER,
                                check="tuplet_consistency",
                                status=QAStatus.AI_REVIEW,
                                severity="medium",
                                part_id=part_id,
                                measure_number=m["number"],
                                description=(
                                    f"Tuplet #{tup['number']} in M{m['number']} mixes "
                                    f"note types {tup['note_types']} — verify rhythm"
                                ),
                                evidence=tup,
                                confidence="medium",
                            )
                        )
                    else:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"RHYTHM-TUPLET-OK-{part_id}-M{m['number']}",
                                category=QACategory.RHYTHM_METER,
                                check="tuplet_consistency",
                                status=QAStatus.PASS,
                                severity="info",
                                part_id=part_id,
                                measure_number=m["number"],
                                description=(
                                    f"Tuplet #{tup['number']} in M{m['number']}: "
                                    f"{tup['note_count']} notes, span {tup['span_quarters']} "
                                    f"quarters, types {tup['note_types']}"
                                ),
                                evidence=tup,
                            )
                        )

        # --- raw vs ScoreIR-exported rhythm equality ------------------------
        if exported:
            stage.checks_run += 1
            mismatches: list[dict] = []
            for part_id, raw_data in raw.items():
                exp_data = exported.get(part_id)
                if exp_data is None:
                    mismatches.append({"part": part_id, "issue": "part missing in export"})
                    continue
                raw_meas = {m["number"]: m for m in raw_data["measures"]}
                exp_meas = {m["number"]: m for m in exp_data["measures"]}
                for mn in sorted(set(raw_meas) | set(exp_meas)):
                    r, e = raw_meas.get(mn), exp_meas.get(mn)
                    if r is None or e is None:
                        mismatches.append({"part": part_id, "measure": mn, "issue": "measure missing in one side"})
                        continue
                    if Fraction(r["expected"]) != Fraction(e["expected"]):
                        mismatches.append({"part": part_id, "measure": mn, "issue": "time signature differs"})
                    for v in sorted(set(r["voices"]) | set(e["voices"])):
                        rq = Fraction(r["voices"].get(v, "0"))
                        eq = Fraction(e["voices"].get(v, "0"))
                        if rq != eq:
                            mismatches.append({
                                "part": part_id,
                                "measure": mn,
                                "voice": v,
                                "raw_quarters": str(rq),
                                "exported_quarters": str(eq),
                            })
            if mismatches:
                stage.issues.append(
                    QAIssue(
                        issue_id="RHYTHM-EXPORT-MISMATCH",
                        category=QACategory.RHYTHM_METER,
                        check="export_rhythm_equality",
                        status=QAStatus.SAFE_REPAIR,
                        severity="high",
                        description=(
                            f"ScoreIR-exported MusicXML rhythm differs from raw OMR in "
                            f"{len(mismatches)} place(s) — deterministic fix: normalize "
                            f"divisions and zero chord-tone durations, then re-verify"
                        ),
                        evidence={"mismatch_count": len(mismatches), "examples": mismatches[:10]},
                        fix={"action": "normalize_rhythm"},
                    )
                )
            else:
                stage.issues.append(
                    QAIssue(
                        issue_id="RHYTHM-EXPORT-MATCH",
                        category=QACategory.RHYTHM_METER,
                        check="export_rhythm_equality",
                        status=QAStatus.PASS,
                        severity="info",
                        description="ScoreIR-exported rhythm matches raw OMR exactly",
                    )
                )

        # Stage status
        if any(i.status == QAStatus.HUMAN_REVIEW and i.severity == "high" for i in stage.issues):
            stage.status = "FAIL"
        elif any(i.status in (QAStatus.AI_REVIEW, QAStatus.HUMAN_REVIEW) for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage
