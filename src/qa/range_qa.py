"""Transposition / Range QA.

- written pitch range vs PRACTICAL range of the canonical instrument
  (a fixed domain table of instrument capabilities — not per-piece data)
- instrument transposition (<transpose>) consistency:
  chromatic mod 12 must equal diatonic mod 7, else the transposition is
  internally inconsistent
- written vs concert pitch reporting (sounding() via ScoreIR Pitch)
- clef consistency: dominant clef vs canonical-instrument clef

Out-of-range notes are AI_REVIEW, never silently corrected.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Note, Score

# Practical WRITTEN ranges (midi). Tolerance: +-2 semitones.
PRACTICAL_RANGE_WRITTEN: dict[str, tuple[int, int]] = {
    "Piccolo": (74, 108),
    "Flute": (60, 96),
    "Oboe": (58, 93),
    "Clarinet": (52, 91),          # Bb clarinet, written
    "Bass Clarinet": (39, 78),     # written
    "Bassoon": (34, 75),
    "Contrabassoon": (22, 64),     # written (sounding one octave lower)
    "Horn": (42, 84),              # written
    "Trumpet": (54, 86),           # written
    "Trombone": (40, 70),
    "Bass Trombone": (23, 70),
    "Tuba": (26, 65),
    "Violin": (55, 105),
    "Viola": (48, 88),
    "Cello": (36, 81),
    "Double Bass": (28, 67),
    "Harp": (24, 103),
    "Timpani": (38, 58),
    "Piano": (21, 108),
    "Soprano": (60, 84),
    "Alto": (53, 77),
    "Tenor": (48, 71),
    "Bass": (40, 64),
    "Choir": (40, 84),
}

RANGE_TOLERANCE = 2

# Canonical-instrument -> expected clef signs
EXPECTED_CLEFS: dict[str, set[str]] = {
    "Piano": {"G", "F"},
    "Harp": {"G", "F"},
    "Bass Trombone": {"F"},
    "Trombone": {"F", "C"},
    "Tuba": {"F"},
    "Cello": {"F", "C"},
    "Bassoon": {"F", "C"},
    "Contrabassoon": {"F"},
    "Double Bass": {"F"},
    "Viola": {"C"},
    "Violin": {"G"},
    "Flute": {"G"},
    "Oboe": {"G"},
    "Piccolo": {"G"},
    "Clarinet": {"G"},
    "Bass Clarinet": {"G"},
    "Trumpet": {"G"},
    "Horn": {"G", "F"},
    "Timpani": {"F"},
    "Soprano": {"G"},
    "Alto": {"G"},
    "Tenor": {"G"},   # treble-8vb
    "Bass": {"F"},
}


def _parse_transpose(part_elem) -> dict | None:
    for attrs in part_elem.iter("attributes"):
        t = attrs.find("transpose")
        if t is not None:
            return {
                "diatonic": int(t.findtext("diatonic", "0") or 0),
                "chromatic": int(t.findtext("chromatic", "0") or 0),
                "octave_change": int(t.findtext("octave-change", "0") or 0),
            }
    return None


class TranspositionRangeQA:
    """Written/concert pitch, practical range and clef consistency QA."""

    def run(
        self,
        score: Score,
        raw_xml: str | Path,
        identities: list | None = None,
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.TRANSPOSITION_RANGE)
        tree = etree.parse(str(raw_xml))
        root = tree.getroot()

        id_by_part = {i.part_id: i for i in (identities or [])}
        transposes: dict[str, dict] = {}
        for part_elem in root.findall(".//part"):
            t = _parse_transpose(part_elem)
            if t is not None:
                transposes[part_elem.get("id", "?")] = t

        for part in score.parts:
            identity = id_by_part.get(part.id)
            canonical = (identity.canonical_instrument if identity else "") or part.name

            # collect written pitches
            pitches: list = []
            clefs: dict[int, set[str]] = {}
            for measure in part.measures:
                for staff_num, clef in measure.clefs.items():
                    clefs.setdefault(staff_num, set()).add(f"{clef.sign}{clef.line}")
                for voice in measure.voices:
                    for event in voice.events:
                        for note in (
                            [event]
                            if isinstance(event, Note)
                            else getattr(event, "notes", [])
                        ):
                            if isinstance(note, Note) and note.pitch is not None and not note.is_grace:
                                pitches.append(note)

            if not pitches:
                continue

            # --- 1. Transposition internal consistency -----------------------
            t = transposes.get(part.id)
            stage.checks_run += 1
            if t:
                chrom = t["chromatic"]
                diat = t["diatonic"]
                if chrom % 12 != diat % 7:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-TRANS-INCONSISTENT-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="transposition_consistency",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part.id,
                            description=(
                                f"{part.id} transposition is internally inconsistent: "
                                f"chromatic={chrom}, diatonic={diat} "
                                f"(chromatic mod 12 = {chrom % 12} != "
                                f"diatonic mod 7 = {diat % 7})"
                            ),
                            evidence=t,
                            confidence="high",
                        )
                    )
                else:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-TRANS-OK-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="transposition_consistency",
                            status=QAStatus.PASS,
                            severity="info",
                            part_id=part.id,
                            description=(
                                f"{part.id} transposes: chromatic={chrom}, "
                                f"diatonic={diat}, octave_change={t['octave_change']}"
                            ),
                            evidence=t,
                        )
                    )

            # --- 2. Written range vs practical range -------------------------
            stage.checks_run += 1
            written_midis = [n.pitch.midi for n in pitches]
            lo, hi = min(written_midis), max(written_midis)
            pr = PRACTICAL_RANGE_WRITTEN.get(canonical)
            if pr:
                pr_lo, pr_hi = pr[0] - RANGE_TOLERANCE, pr[1] + RANGE_TOLERANCE
                outliers = [n for n in pitches if not (pr_lo <= n.pitch.midi <= pr_hi)]
                if outliers:
                    by_measure: dict[str, list[str]] = {}
                    for n in outliers:
                        m = n.id.split("-M", 1)[1].split("-")[0]
                        by_measure.setdefault(m, []).append(
                            f"{n.pitch.step}{n.pitch.alter:+d}{n.pitch.octave}"
                        )
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-OUT-OF-RANGE-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="practical_range",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part.id,
                            description=(
                                f"{len(outliers)} note(s) in {part.id} outside the "
                                f"practical written range of {canonical} "
                                f"(midi {pr_lo}–{pr_hi}): {dict(list(by_measure.items())[:5])}"
                            ),
                            evidence={
                                "canonical": canonical,
                                "practical_range": list(pr),
                                "written_range": [lo, hi],
                                "outlier_measures": by_measure,
                            },
                            confidence="medium",
                        )
                    )
                else:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-OK-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="practical_range",
                            status=QAStatus.PASS,
                            severity="info",
                            part_id=part.id,
                            description=(
                                f"{part.id} written range midi {lo}–{hi} within "
                                f"practical range of {canonical} ({pr_lo}–{pr_hi})"
                            ),
                            evidence={"written_range": [lo, hi], "practical_range": list(pr)},
                        )
                    )

            # --- 3. Concert range report (transposing instruments) -----------
            if t:
                stage.checks_run += 1
                chrom = t["chromatic"]
                oct_change = t["octave_change"]
                concert = [n.pitch.sounding(chrom, oct_change).midi for n in pitches]
                stage.issues.append(
                    QAIssue(
                        issue_id=f"RANGE-CONCERT-{part.id}",
                        category=QACategory.TRANSPOSITION_RANGE,
                        check="concert_range",
                        status=QAStatus.PASS,
                        severity="info",
                        part_id=part.id,
                        description=(
                            f"{part.id} concert range midi {min(concert)}–{max(concert)} "
                            f"(written {lo}–{hi})"
                        ),
                        evidence={"concert_range": [min(concert), max(concert)], "written_range": [lo, hi]},
                    )
                )

            # --- 4. Clef consistency -----------------------------------------
            stage.checks_run += 1
            expected_signs = EXPECTED_CLEFS.get(canonical)
            if expected_signs and clefs:
                used_signs = set()
                for staff_num, clef_set in clefs.items():
                    used_signs |= {c[0] for c in clef_set}
                if not (used_signs & expected_signs):
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-CLEF-MISMATCH-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="clef_consistency",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part.id,
                            description=(
                                f"{part.id} uses clef(s) {sorted(used_signs)} but "
                                f"{canonical} expects {sorted(expected_signs)}"
                            ),
                            evidence={"used_clefs": sorted(used_signs), "expected": sorted(expected_signs)},
                            confidence="medium",
                        )
                    )
                else:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"RANGE-CLEF-OK-{part.id}",
                            category=QACategory.TRANSPOSITION_RANGE,
                            check="clef_consistency",
                            status=QAStatus.PASS,
                            severity="info",
                            part_id=part.id,
                            description=(
                                f"{part.id} clefs {sorted(used_signs)} consistent with "
                                f"{canonical}"
                            ),
                            evidence={"used_clefs": sorted(used_signs)},
                        )
                    )

        # Stage status
        if any(i.status in (QAStatus.AI_REVIEW,) for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage
