"""SafeTranspositionService — guarded entry point for transposition.

Wraps ``TranspositionEngine`` with the OMR Quality Gate. In ``STRICT`` mode,
any blocking OMR issue prevents deterministic editing. In ``PERMISSIVE`` mode,
issues are downgraded to warnings and the operation proceeds.

The service also handles the case where no OMR report is available: the engine
runs normally and the caller is responsible for gate checks beforehand.
"""

from __future__ import annotations

import copy

from score_engine.score_ir.score_ir import Score
from score_engine.transposition.engine import TranspositionEngine, TranspositionResult
from score_engine.transposition.report import TransposeReport
from score_engine.transposition.request import TransposeRequest


try:
    from omr_normalization.issue_model import OMRNormalizationReport
    from omr_normalization.quality_gate import OMRGateMode, OMRQualityGate
    _HAS_GATE = True
except Exception:  # pragma: no cover - defensive import
    OMRNormalizationReport = None  # type: ignore
    OMRQualityGate = None  # type: ignore
    OMRGateMode = None  # type: ignore
    _HAS_GATE = False


class SafeTranspositionService:
    """Run transposition through the OMR Quality Gate."""

    def __init__(
        self,
        engine: TranspositionEngine | None = None,
        gate=None,
    ) -> None:
        self.engine = engine or TranspositionEngine()
        self.gate = gate or (OMRQualityGate() if _HAS_GATE else None)

    def transpose(
        self,
        score: Score,
        request: TransposeRequest,
        omr_report=None,
        mode: str | None = None,
    ) -> TranspositionResult:
        """Execute ``request`` if the OMR gate allows it.

        Args:
            score: Input ScoreIR score (unchanged).
            request: TransposeRequest describing the desired operation.
            omr_report: Optional OMRNormalizationReport to gate against.
            mode: OMR gate mode (``STRICT`` or ``PERMISSIVE``). Defaults to
                ``STRICT`` when a report is supplied.

        Returns:
            A TranspositionResult. If the gate blocks the operation in STRICT
            mode, the returned score is a deep copy of the input and the report
            status is ``blocked``.
        """
        if omr_report is not None and self.gate is not None:
            mode = mode or OMRGateMode.STRICT
            gate_result = self.gate.check(omr_report, mode)

            if mode == OMRGateMode.STRICT and not gate_result.allows_deterministic_edit:
                return TranspositionResult(
                    score=copy.deepcopy(score) if request.preserve_original else score,
                    report=TransposeReport(
                        status="blocked",
                        operation=request.operation.value,
                        message="OMR Quality Gate blocked deterministic editing in STRICT mode",
                    ),
                )

            result = self.engine.transpose(score, request)
            if gate_result.status in ("degraded", "blocked"):
                result.report.warnings.append(
                    f"OMR Quality Gate status: {gate_result.status}"
                )
            return result

        return self.engine.transpose(score, request)
