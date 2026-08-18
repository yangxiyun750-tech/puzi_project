"""Deterministic validation for transpose intents and requests.

This module guards against LLM hallucinations and malformed input. It performs
all checks in plain Python against the actual ``Score``; it does not call any
AI model.
"""

from __future__ import annotations

from score_engine.score_ir.score_ir import Score
from score_engine.transposition.interval import Interval
from score_engine.transposition.request import TranspositionOperation, TransposeRequest

from .intent_schema import TransposeIntent, ValidationResult


class IntentValidator:
    """Validate a transpose intent or request deterministically."""

    ALLOWED_STATUSES = {"ready", "needs_clarification", "unsupported", "invalid", "provider_error"}
    ALLOWED_DIRECTIONS = {"up", "down"}
    ALLOWED_OPERATIONS = {
        "transpose",
        "written_to_sounding",
        "sounding_to_written",
    }
    ALLOWED_BASIS = {"written", "sounding", "concert"}

    def validate_intent(self, intent: TransposeIntent) -> ValidationResult:
        """Check the raw intent structure before resolution."""
        if intent.status not in self.ALLOWED_STATUSES:
            return ValidationResult(
                valid=False,
                reason=f"Unknown status: {intent.status}",
            )

        if intent.status in ("needs_clarification", "unsupported", "invalid"):
            # Non-ready statuses are valid as long as the status itself is known.
            return ValidationResult(valid=True)

        # status == "ready"
        if intent.operation and intent.operation not in self.ALLOWED_OPERATIONS:
            return ValidationResult(
                valid=False,
                reason=f"Unsupported operation: {intent.operation}",
            )

        if intent.direction and intent.direction not in self.ALLOWED_DIRECTIONS:
            return ValidationResult(
                valid=False,
                reason=f"Unknown direction: {intent.direction}",
            )

        if intent.basis and intent.basis not in self.ALLOWED_BASIS:
            return ValidationResult(
                valid=False,
                reason=f"Unknown basis: {intent.basis}",
            )

        return ValidationResult(valid=True)

    def validate_request(self, request: TransposeRequest, score: Score) -> ValidationResult:
        """Check a resolved ``TransposeRequest`` against the actual score."""
        if not isinstance(request.operation, TranspositionOperation):
            return ValidationResult(valid=False, reason="Invalid operation enum")

        if request.operation == TranspositionOperation.INTERVAL:
            if request.interval is None:
                return ValidationResult(
                    valid=False,
                    reason="INTERVAL operation requires an interval",
                )
            try:
                _ = request.interval.semitones
            except ValueError as exc:
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid interval: {exc}",
                )

        if request.measure_start < 1:
            return ValidationResult(
                valid=False,
                reason=f"measure_start must be >= 1, got {request.measure_start}",
            )

        if request.measure_end is not None:
            if request.measure_end < request.measure_start:
                return ValidationResult(
                    valid=False,
                    reason="measure_end must be >= measure_start",
                )

        if not request.part_ids:
            return ValidationResult(valid=False, reason="part_ids must not be empty")

        score_part_ids = {p.id for p in score.parts}
        for pid in request.part_ids:
            if pid not in score_part_ids:
                return ValidationResult(
                    valid=False,
                    reason=f"Unknown part_id: {pid}",
                )
            part = score.get_part(pid)
            if part is None:
                return ValidationResult(
                    valid=False,
                    reason=f"Part not found: {pid}",
                )
            max_measure_idx = len(part.measures)
            if max_measure_idx == 0:
                return ValidationResult(
                    valid=False,
                    reason=f"Part {pid} has no measures",
                )
            if request.measure_start > max_measure_idx:
                return ValidationResult(
                    valid=False,
                    reason=(
                        f"Part {pid} has only {max_measure_idx} measures, "
                        f"measure_start {request.measure_start} is out of range"
                    ),
                )
            if request.measure_end is not None and request.measure_end > max_measure_idx:
                return ValidationResult(
                    valid=False,
                    reason=(
                        f"Part {pid} has only {max_measure_idx} measures, "
                        f"measure_end {request.measure_end} is out of range"
                    ),
                )

        return ValidationResult(valid=True)
