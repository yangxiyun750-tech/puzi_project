"""Lyrics QA — runs ONLY when a genuine Vocal Part or real <lyric>
elements exist. On purely instrumental scores the stage is SKIP.

Checks: lyric coverage, empty lyric text, syllabic chains
(begin/middle/end), extend chains, lyric on rests.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Score


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class LyricsQA:
    """Lyrics validation, enabled only for vocal parts with real lyrics."""

    def run(self, raw_xml: str | Path, score: Score, vocal_part_ids: set[str]) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.LYRICS)
        tree = etree.parse(str(raw_xml))
        root = tree.getroot()

        # Gate: any lyric elements anywhere?
        lyric_elems = root.findall(".//lyric")
        stage.checks_run += 1
        if not lyric_elems and not vocal_part_ids:
            stage.status = "SKIP"
            stage.issues.append(
                QAIssue(
                    issue_id="LYRICS-SKIP",
                    category=QACategory.LYRICS,
                    check="lyrics_gate",
                    status=QAStatus.SKIP,
                    severity="info",
                    description=(
                        "No Vocal Parts and no <lyric> elements — lyrics QA disabled"
                    ),
                )
            )
            return stage

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")
            is_vocal = part_id in vocal_part_ids

            notes_with_lyrics = 0
            notes_total = 0
            prev_syllabic: dict[str, str] = {}  # number -> last syllabic
            extend_open: set[str] = set()

            for meas in part_elem.findall("measure"):
                mn = meas.get("number", "?")
                for note in meas.findall("note"):
                    notes_total += 1
                    is_rest = note.find("rest") is not None or (
                        note.find("pitch") is None
                    )
                    for lyric in note.findall("lyric"):
                        num = lyric.get("number", "1")
                        text = lyric.findtext("text", "")
                        syllabic = lyric.findtext("syllabic", "single") or "single"
                        stage.checks_run += 1

                        if lyric.get("number") != "1":
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"LYRICS-MULTI-VERSE-{part_id}-M{mn}",
                                    category=QACategory.LYRICS,
                                    check="multi_verse",
                                    status=QAStatus.PASS,
                                    severity="info",
                                    part_id=part_id,
                                    measure_number=mn,
                                    description=(
                                        f"Multiple lyric verses detected in M{mn} — "
                                        f"each verse validated independently"
                                    ),
                                )
                            )

                        notes_with_lyrics += 1

                        if is_rest:
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"LYRICS-ON-REST-{part_id}-M{mn}",
                                    category=QACategory.LYRICS,
                                    check="lyric_on_rest",
                                    status=QAStatus.AI_REVIEW,
                                    severity="medium",
                                    part_id=part_id,
                                    measure_number=mn,
                                    description=f"Lyric '{text}' attached to a rest in M{mn}",
                                    evidence={"text": text},
                                    confidence="medium",
                                )
                            )

                        if text is None or not text.strip():
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"LYRICS-EMPTY-{part_id}-M{mn}",
                                    category=QACategory.LYRICS,
                                    check="empty_text",
                                    status=QAStatus.AI_REVIEW,
                                    severity="medium",
                                    part_id=part_id,
                                    measure_number=mn,
                                    description=f"Empty lyric text on a note in M{mn}",
                                    confidence="medium",
                                )
                            )

                        # syllabic chain: single | begin middle* end
                        prev = prev_syllabic.get(num)
                        if syllabic in ("middle", "end") and prev in (None, "single", "end"):
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"LYRICS-SYLLABIC-{part_id}-M{mn}",
                                    category=QACategory.LYRICS,
                                    check="syllabic_chain",
                                    status=QAStatus.AI_REVIEW,
                                    severity="low",
                                    part_id=part_id,
                                    measure_number=mn,
                                    description=(
                                        f"Syllabic '{syllabic}' without a preceding "
                                        f"'begin' in M{mn} (verse {num})"
                                    ),
                                    evidence={"syllabic": syllabic, "previous": prev},
                                    confidence="low",
                                )
                            )
                        if syllabic == "begin" and prev == "begin":
                            stage.issues.append(
                                QAIssue(
                                    issue_id=f"LYRICS-SYLLABIC-BEGIN-{part_id}-M{mn}",
                                    category=QACategory.LYRICS,
                                    check="syllabic_chain",
                                    status=QAStatus.AI_REVIEW,
                                    severity="low",
                                    part_id=part_id,
                                    measure_number=mn,
                                    description=(
                                        f"Two consecutive 'begin' syllables in M{mn} "
                                        f"(verse {num}) — previous word may be incomplete"
                                    ),
                                    confidence="low",
                                )
                            )
                        prev_syllabic[num] = syllabic

                        # extend chain: start -> continue* -> stop
                        extend = lyric.find("extend")
                        if extend is not None:
                            e_type = extend.get("type", "start")
                            if e_type == "start":
                                if num in extend_open:
                                    stage.issues.append(
                                        QAIssue(
                                            issue_id=f"LYRICS-EXTEND-{part_id}-M{mn}",
                                            category=QACategory.LYRICS,
                                            check="extend_chain",
                                            status=QAStatus.SAFE_REPAIR,
                                            severity="low",
                                            part_id=part_id,
                                            measure_number=mn,
                                            description=(
                                                f"Overlapping lyric extend start in M{mn} "
                                                f"(verse {num})"
                                            ),
                                            fix={"action": "remove_dangling_extend"},
                                        )
                                    )
                                extend_open.add(num)
                            elif e_type == "stop":
                                extend_open.discard(num)

            # coverage report for vocal parts
            if is_vocal and notes_total:
                stage.checks_run += 1
                coverage = notes_with_lyrics / notes_total
                stage.issues.append(
                    QAIssue(
                        issue_id=f"LYRICS-COVERAGE-{part_id}",
                        category=QACategory.LYRICS,
                        check="lyric_coverage",
                        status=(
                            QAStatus.PASS
                            if coverage > 0.05
                            else QAStatus.AI_REVIEW
                        ),
                        severity="info" if coverage > 0.05 else "medium",
                        part_id=part_id,
                        description=(
                            f"{part_id}: {notes_with_lyrics}/{notes_total} notes "
                            f"({coverage:.1%}) carry lyrics"
                        ),
                        evidence={
                            "notes_with_lyrics": notes_with_lyrics,
                            "notes_total": notes_total,
                            "coverage": round(coverage, 3),
                        },
                    )
                )

        # Stage status
        if not lyric_elems:
            stage.status = "SKIP"
        elif any(i.status in (QAStatus.AI_REVIEW,) and i.severity != "low" for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage
