"""Instrument Identity QA.

Wraps InstrumentIdentityResolver and turns its output into QA issues.

The Audiveris label is treated ONLY as candidate evidence (per V2 rule);
identity problems escalate to AI_REVIEW / HUMAN_REVIEW, never to a
silent override.
"""

from __future__ import annotations

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

from score_engine.score_ir.score_ir import Score
from score_engine.validation.instrument_identity import InstrumentIdentity, InstrumentIdentityResolver


class InstrumentQA:
    """QA checks over resolved instrument identities."""

    def run(self, score: Score, pdf_text: str = "") -> QAStageResult:
        stage = QAStageResult(stage=QACategory.INSTRUMENT_IDENTITY)

        resolver = InstrumentIdentityResolver(pdf_text=pdf_text)
        identities = resolver.resolve(score)
        stage.checks_run += len(identities) if identities else 1

        for identity in identities:
            stage.checks_run += 1

            # 1. Unresolvable identity
            if (
                not identity.canonical_instrument
                or identity.canonical_instrument.startswith("Unknown")
            ):
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-UNKNOWN-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="canonical_instrument",
                        status=QAStatus.HUMAN_REVIEW,
                        severity="high",
                        part_id=identity.part_id,
                        description=(
                            f"Cannot determine canonical instrument for {identity.part_id} "
                            f"(source label: '{identity.source_label}')"
                        ),
                        evidence={
                            "source_label": identity.source_label,
                            "evidence": identity.evidence,
                        },
                        confidence="low",
                    )
                )
                continue

            # 2. Low / medium confidence — needs local visual confirmation
            if identity.confidence in ("low", "medium"):
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-CONFIDENCE-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="confidence",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        part_id=identity.part_id,
                        measure_number="1",
                        description=(
                            f"{identity.part_id} resolved as "
                            f"'{identity.canonical_instrument}' with {identity.confidence} "
                            f"confidence — verify against source score"
                        ),
                        evidence={
                            "canonical": identity.canonical_instrument,
                            "confidence": identity.confidence,
                            "evidence": identity.evidence,
                        },
                        confidence="medium",
                    )
                )

            # 3. Resolver explicitly asked for verification
            if identity.needs_verification:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-VERIFY-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="needs_verification",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        part_id=identity.part_id,
                        measure_number="1",
                        description=(
                            f"{identity.part_id} ('{identity.canonical_instrument}') "
                            f"needs verification: {identity.verification_reason}"
                        ),
                        evidence={"reason": identity.verification_reason},
                        confidence="medium",
                    )
                )

            # 4. Vocal / lyric consistency
            lyrics_present = self._part_has_lyrics(score, identity.part_id)
            if identity.is_vocal and not lyrics_present:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-VOCAL-NO-LYRICS-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="vocal_lyric_consistency",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        part_id=identity.part_id,
                        description=(
                            f"{identity.part_id} is a Vocal Part but contains no lyrics — "
                            f"verify against source"
                        ),
                        evidence={"is_vocal": True, "has_lyrics": False},
                        confidence="medium",
                    )
                )
            if lyrics_present and not identity.is_vocal:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-LYRICS-NO-VOCAL-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="vocal_lyric_consistency",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        part_id=identity.part_id,
                        description=(
                            f"{identity.part_id} ('{identity.canonical_instrument}') "
                            f"contains lyrics but is not a Vocal Part — verify against source"
                        ),
                        evidence={"is_vocal": False, "has_lyrics": True},
                        confidence="medium",
                    )
                )

            # 5. Audiveris label conflict — recorded as INFO evidence only.
            #    The label is candidate evidence; a conflict alone is not an issue.
            if identity.source_label.lower() != identity.canonical_instrument.lower():
                stage.issues.append(
                    QAIssue(
                        issue_id=f"IDENT-LABEL-CONFLICT-{identity.part_id}",
                        category=QACategory.INSTRUMENT_IDENTITY,
                        check="audiveris_label_conflict",
                        status=QAStatus.PASS,
                        severity="info",
                        part_id=identity.part_id,
                        description=(
                            f"Audiveris label '{identity.source_label}' overridden by "
                            f"'{identity.canonical_instrument}' (label is candidate "
                            f"evidence only)"
                        ),
                        evidence={
                            "source_label": identity.source_label,
                            "canonical": identity.canonical_instrument,
                            "evidence": identity.evidence,
                        },
                    )
                )

            # 6. Record the resolved identity itself as a PASS entry
            stage.issues.append(
                QAIssue(
                    issue_id=f"IDENT-RESOLVED-{identity.part_id}",
                    category=QACategory.INSTRUMENT_IDENTITY,
                    check="identity_summary",
                    status=QAStatus.PASS,
                    severity="info",
                    part_id=identity.part_id,
                    description=(
                        f"{identity.part_id} = {identity.canonical_instrument} "
                        f"(confidence {identity.confidence}, staffs {identity.staff_count}, "
                        f"clef {identity.clef}, range {identity.pitch_range_low}–"
                        f"{identity.pitch_range_high}, vocal={identity.is_vocal})"
                    ),
                    evidence={
                        "canonical": identity.canonical_instrument,
                        "confidence": identity.confidence,
                        "staff_count": identity.staff_count,
                        "clef": identity.clef,
                        "pitch_range": [identity.pitch_range_low, identity.pitch_range_high],
                        "is_vocal": identity.is_vocal,
                    },
                )
            )

        # Stage status
        if any(i.status == QAStatus.HUMAN_REVIEW for i in stage.issues):
            stage.status = "FAIL"
        elif any(i.status == QAStatus.AI_REVIEW for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage

    @staticmethod
    def _part_has_lyrics(score: Score, part_id: str) -> bool:
        part = score.get_part(part_id)
        if part is None:
            return False
        for measure in part.measures:
            for voice in measure.voices:
                for event in voice.events:
                    if hasattr(event, "lyrics") and event.lyrics:
                        return True
        return False
