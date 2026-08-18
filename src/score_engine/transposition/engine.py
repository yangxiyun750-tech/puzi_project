"""Deterministic Transposition Engine V1.

Transforms a ScoreIR score according to a ``TransposeRequest`` while keeping
the original score unchanged. V1 guarantees:

- Deep-copy immutability: the input ``Score`` is never modified.
- Named interval spelling: the diatonic target step is immutable.
- Measure-range key restoration: the original active key is reinstated at the
  measure immediately after a transposed range (unless the range reaches the
  part end).
- Provenance-aware written/sounding conversion for transposing instruments.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from score_engine.score_ir.score_ir import (
    Chord,
    KeySignature,
    Measure,
    Note,
    Part,
    Pitch,
    Score,
)
from score_engine.transposition.interval import Interval, SpellingError
from score_engine.transposition.instrument_map import (
    resolve_part_transposition,
    transposition_to_interval,
)
from score_engine.transposition.key_signature import (
    KeyTimeline,
    prepare_range_key_restoration,
    transpose_key_signature,
)
from score_engine.transposition.pitch_spelling import spell_transposed_pitch
from score_engine.transposition.report import NoteChange, PartReport, TransposeReport
from score_engine.transposition.request import TranspositionOperation, TransposeRequest


_DEFAULT_KEY = KeySignature(0, "major")


@dataclass(frozen=True, slots=True)
class TranspositionResult:
    """Result of a successful transposition."""

    score: Score
    report: TransposeReport


class TranspositionEngine:
    """Apply transposition requests to ScoreIR scores."""

    def transpose(self, score: Score, request: TransposeRequest) -> TranspositionResult:
        """Execute ``request`` against ``score`` and return a new score + report.

        The input score is never modified. The engine deep-copies it before
        making any changes.
        """
        working_score = copy.deepcopy(score) if request.preserve_original else score

        report = TransposeReport(
            status="ok",
            operation=request.operation.value,
        )

        target_part_ids = self._target_part_ids(working_score, request)

        for part in working_score.parts:
            if part.id not in target_part_ids:
                continue
            part_report = self._transpose_part(part, request, report)
            report.parts.append(part_report)

        return TranspositionResult(score=working_score, report=report)

    def _target_part_ids(self, score: Score, request: TransposeRequest) -> set[str]:
        if request.part_ids:
            return set(request.part_ids)
        return {p.id for p in score.parts}

    def _transpose_part(
        self,
        part: Part,
        request: TransposeRequest,
        report: TransposeReport,
    ) -> PartReport:
        resolved = resolve_part_transposition(part)
        part_report = PartReport(
            part_id=part.id,
            operation=request.operation.value,
            transposition_provenance=resolved.provenance,
        )

        # Resolve the interval to apply and any pure-octave shift.
        interval, octave_shift, unsupported_reason = self._resolve_interval(
            request, resolved
        )

        if unsupported_reason:
            part_report.warnings.append(unsupported_reason)
            if not resolved.supported:
                part_report.sounding_audit_available = False
                return part_report

        part_report.sounding_audit_available = resolved.provenance in (
            "musicxml",
            "identity",
        )
        if resolved.provenance == "unknown":
            part_report.warnings.append(
                "Unknown instrument transposition metadata; sounding audit unavailable"
            )

        start_index, end_index = self._measure_indices(part, request)

        # Build key timeline from the original part state.
        timeline = KeyTimeline.from_part(part)

        # Apply interval to notes in the selected range.
        for m_idx in range(start_index, end_index + 1):
            measure = part.measures[m_idx]
            self._transpose_measure_notes(
                part, measure, interval, octave_shift, report
            )

        # Count actually changed notes from the report.
        part_report.notes_changed = sum(
            1 for nc in report.note_changes if nc.part_id == part.id
        )

        # Transpose key signatures in the range.
        self._transpose_range_keys(
            part, start_index, end_index, interval, timeline, part_report
        )

        return part_report

    def _resolve_interval(
        self,
        request: TransposeRequest,
        resolved,
    ) -> tuple[Interval, int, str]:
        """Return (interval, octave_shift, unsupported_reason)."""
        if request.operation == TranspositionOperation.INTERVAL:
            assert request.interval is not None
            return request.interval, 0, ""

        if request.operation == TranspositionOperation.WRITTEN_TO_SOUNDING:
            return self._instrument_conversion_interval(resolved, invert=False)

        if request.operation == TranspositionOperation.SOUNDING_TO_WRITTEN:
            return self._instrument_conversion_interval(resolved, invert=True)

        raise ValueError(f"Unsupported operation: {request.operation}")

    def _instrument_conversion_interval(
        self,
        resolved,
        invert: bool,
    ) -> tuple[Interval, int, str]:
        if not resolved.supported:
            return (
                Interval(1, "P"),
                0,
                f"Unsupported transposition metadata: {resolved.reason}",
            )

        if resolved.provenance == "unknown":
            return (
                Interval(1, "P"),
                0,
                "Cannot convert: unknown instrument transposition",
            )

        interval = transposition_to_interval(resolved.transposition)
        octave_shift = resolved.transposition.octave_change
        if invert:
            interval = interval.inverted()
            octave_shift = -octave_shift
        return interval, octave_shift, ""

    def _measure_indices(self, part: Part, request: TransposeRequest) -> tuple[int, int]:
        start = max(0, request.measure_start - 1)
        end = len(part.measures) - 1
        if request.measure_end is not None:
            end = min(end, request.measure_end - 1)
        return start, end

    def _transpose_measure_notes(
        self,
        part: Part,
        measure: Measure,
        interval: Interval,
        octave_shift: int,
        report: TransposeReport,
    ) -> None:
        for voice in measure.voices:
            for event in voice.events:
                if isinstance(event, Note):
                    self._transpose_note(
                        part, measure, voice, event, interval,
                        octave_shift, report
                    )
                elif isinstance(event, Chord):
                    for note in event.notes:
                        self._transpose_note(
                            part, measure, voice, note, interval,
                            octave_shift, report
                        )

    def _transpose_note(
        self,
        part: Part,
        measure: Measure,
        voice,
        note: Note,
        interval: Interval,
        octave_shift: int,
        report: TransposeReport,
    ) -> None:
        if note.pitch is None:
            return
        before = note.pitch
        try:
            after = spell_transposed_pitch(before, interval)
            if octave_shift:
                after = self._shift_octave(after, octave_shift)
            note.pitch = after
        except SpellingError as exc:
            report.warnings.append(f"{note.id}: {exc}")
            return

        report.note_changes.append(
            NoteChange(
                part_id=part.id,
                measure_number=measure.number,
                voice_id=getattr(voice, "id", ""),
                note_id=note.id,
                before=before,
                after=after,
            )
        )

    def _shift_octave(self, pitch: Pitch, octave_shift: int) -> Pitch:
        """Shift a pitch by an integer number of octaves.

        The step and accidental are preserved exactly; only the octave number
        changes. This avoids enharmonic re-interpretation of edge cases such as
        B#3 -> B#4.
        """
        return Pitch(pitch.step, pitch.alter, pitch.octave + octave_shift)

    def _transpose_range_keys(
        self,
        part: Part,
        start_index: int,
        end_index: int,
        interval: Interval,
        timeline: KeyTimeline,
        part_report: PartReport,
    ) -> None:
        """Transpose active keys inside the range and restore at end+1."""
        for m_idx in range(start_index, end_index + 1):
            original_active = timeline.active_key_at(m_idx) or _DEFAULT_KEY
            try:
                new_key = transpose_key_signature(original_active, interval)
            except (SpellingError, ValueError) as exc:
                part_report.warnings.append(
                    f"Measure {m_idx + 1}: key transposition unsupported: {exc}"
                )
                continue
            part.measures[m_idx].key_signature = new_key
            if original_active.fifths != new_key.fifths:
                part_report.key_changes.append({
                    "measure": m_idx + 1,
                    "before_fifths": original_active.fifths,
                    "after_fifths": new_key.fifths,
                })

        restore_key = prepare_range_key_restoration(
            part, start_index, end_index, timeline
        )
        if restore_key is not None:
            restore_index = end_index + 1
            current = part.measures[restore_index].key_signature
            if current is None or current.fifths != restore_key.fifths:
                part.measures[restore_index].key_signature = restore_key
                part_report.key_changes.append({
                    "measure": restore_index + 1,
                    "before_fifths": restore_key.fifths,
                    "after_fifths": restore_key.fifths,
                    "restoration": True,
                })
