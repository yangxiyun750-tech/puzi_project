"""OMR Structure QA — part/staff counts and measure completeness.

Measures flagged here are NEVER auto-filled: a missing measure is a
HUMAN_REVIEW item because inventing content (even rests) is a musical
decision, not a structural one.
"""

from __future__ import annotations

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Chord, Measure, Note, Rest, Score


def _measure_number_int(measure: Measure) -> int | None:
    try:
        return int(measure.number.split("X")[0])
    except (ValueError, AttributeError):
        return None


def _part_staff_count(score, part) -> int:
    staffs: set[int] = set()
    for measure in part.measures:
        for voice in measure.voices:
            for event in voice.events:
                if hasattr(event, "staff"):
                    staffs.add(event.staff)
                if isinstance(event, Chord):
                    for note in event.notes:
                        staffs.add(note.staff)
        for staff_num in measure.clefs:
            staffs.add(staff_num)
    return max(staffs) if staffs else 1


def _iter_events(measure: Measure):
    for voice in measure.voices:
        for event in voice.events:
            yield voice, event


class StructureQA:
    """Validate OMR structure: parts, staves, measure completeness."""

    def run(self, score: Score, identities: list | None = None) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.OMR_STRUCTURE)
        id_by_part = {i.part_id: i for i in (identities or [])}

        # --- 1. Part count ---------------------------------------------------
        stage.checks_run += 1
        if not score.parts:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="STRUCT-NO-PARTS",
                    category=QACategory.OMR_STRUCTURE,
                    check="part_count",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description="OMR produced no parts at all",
                )
            )
            return stage

        # --- 2. Per-part staff count vs identity expectation -----------------
        expected_staffs = {"Piano": 2, "Harp": 2, "Organ": 3}
        for part in score.parts:
            stage.checks_run += 1
            staff_count = _part_staff_count(score, part)
            identity = id_by_part.get(part.id)
            canonical = (identity.canonical_instrument if identity else "") or part.name
            expected = expected_staffs.get(canonical, 1)
            if staff_count != expected:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"STRUCT-STAFFS-{part.id}",
                        category=QACategory.OMR_STRUCTURE,
                        check="staff_count",
                        status=QAStatus.AI_REVIEW,
                        severity="high" if expected >= 2 else "medium",
                        part_id=part.id,
                        description=(
                            f"{part.id} ('{canonical}') has {staff_count} staff(s), "
                            f"expected {expected}"
                        ),
                        evidence={"staff_count": staff_count, "expected": expected, "canonical": canonical},
                        confidence="high" if identity and identity.confidence == "high" else "medium",
                    )
                )

        # --- 3/4. Measure number gaps and duplicates -------------------------
        for part in score.parts:
            nums = [_measure_number_int(m) for m in part.measures]
            nums = [n for n in nums if n is not None]
            stage.checks_run += 1
            if not nums:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"STRUCT-NO-MEASURES-{part.id}",
                        category=QACategory.OMR_STRUCTURE,
                        check="measure_presence",
                        status=QAStatus.HUMAN_REVIEW,
                        severity="high",
                        part_id=part.id,
                        description=f"{part.id} has no measures",
                    )
                )
                continue

            prev = nums[0]
            for n in nums[1:]:
                if n == prev:  # duplicate number
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"STRUCT-DUP-M-{part.id}-{n}",
                            category=QACategory.OMR_STRUCTURE,
                            check="duplicate_measure",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            part_id=part.id,
                            measure_number=str(n),
                            description=(
                                f"Duplicate measure number {n} in {part.id} — "
                                f"possible merged measure or spurious barline"
                            ),
                        )
                    )
                elif n > prev + 1:
                    for gap in range(prev + 1, n):
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"STRUCT-GAP-M-{part.id}-{gap}",
                                category=QACategory.OMR_STRUCTURE,
                                check="missing_measure",
                                status=QAStatus.HUMAN_REVIEW,
                                severity="high",
                                part_id=part.id,
                                measure_number=str(gap),
                                description=(
                                    f"Measure {gap} missing from {part.id} — "
                                    f"never auto-filled; needs visual recovery"
                                ),
                            )
                        )
                prev = n

        # --- 5. Cross-part measure count consistency -------------------------
        if len(score.parts) > 1:
            stage.checks_run += 1
            counts = {p.id: len(p.measures) for p in score.parts}
            lo = min(counts.values())
            hi = max(counts.values())
            if lo != hi:
                stage.issues.append(
                    QAIssue(
                        issue_id="STRUCT-MEASURE-COUNT-MISMATCH",
                        category=QACategory.OMR_STRUCTURE,
                        check="measure_count_consistency",
                        status=QAStatus.HUMAN_REVIEW,
                        severity="high",
                        description=(
                            f"Parts have different measure counts: {counts} — "
                            f"one or more parts lost measures in OMR"
                        ),
                        evidence=counts,
                    )
                )

        # --- 6. Empty measures / empty voices / invalid durations ------------
        for part in score.parts:
            for measure in part.measures:
                events = list(_iter_events(measure))
                stage.checks_run += 1
                if not events:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"STRUCT-EMPTY-M-{part.id}-{measure.number}",
                            category=QACategory.OMR_STRUCTURE,
                            check="empty_measure",
                            status=QAStatus.HUMAN_REVIEW,
                            severity="high",
                            part_id=part.id,
                            measure_number=measure.number,
                            description=(
                                f"Measure {measure.number} in {part.id} has no events — "
                                f"content lost by OMR, needs visual recovery"
                            ),
                        )
                    )
                    continue

                for voice, event in events:
                    dur = getattr(event, "duration", None)
                    if dur is not None and dur.value <= 0:
                        stage.issues.append(
                            QAIssue(
                                issue_id=f"STRUCT-BAD-DUR-{part.id}-{measure.number}-{voice.id}",
                                category=QACategory.OMR_STRUCTURE,
                                check="invalid_duration",
                                status=QAStatus.AI_REVIEW,
                                severity="medium",
                                part_id=part.id,
                                measure_number=measure.number,
                                voice_id=voice.id,
                                note_id=getattr(event, "id", ""),
                                description=(
                                    f"Non-positive duration ({dur.value}) on "
                                    f"{getattr(event, 'id', 'event')}"
                                ),
                                evidence={"duration": dur.value},
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
