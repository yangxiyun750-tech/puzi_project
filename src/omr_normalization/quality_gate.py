"""OMR Quality Gate — decide whether a normalized score is safe to edit.

The gate sits between the OMR Normalization Layer and downstream
score-engine consumers (MusicXMLImporter / ScoreIR). It classifies every
remaining issue by edit safety and returns a verdict:

- STRICT: unresolved blocking_for_edit issues block deterministic editing.
- PERMISSIVE: all issues become warnings; editing is allowed in degraded mode.

The gate never mutates musical content. It only inspects an
OMRNormalizationReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omr_normalization.issue_model import (
    OMREditSafety,
    OMRNormalizationReport,
    OMRIssue,
    OMRStatus,
)


class OMRGateMode:
    """Supported gate modes."""

    STRICT = "STRICT"
    PERMISSIVE = "PERMISSIVE"


@dataclass
class OMRGateResult:
    """Result of running the OMR Quality Gate on a normalization report."""

    mode: str
    status: str  # "clean" | "degraded" | "blocked"
    allowed: bool
    allows_deterministic_edit: bool
    blocking_issues: list[OMRIssue] = field(default_factory=list)
    warnings: list[OMRIssue] = field(default_factory=list)
    info: list[OMRIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
            "allowed": self.allowed,
            "allows_deterministic_edit": self.allows_deterministic_edit,
            "blocking_issues": [i.to_dict() for i in self.blocking_issues],
            "warnings": [i.to_dict() for i in self.warnings],
            "info": [i.to_dict() for i in self.info],
            "summary": self.summary,
        }


class OMRQualityGate:
    """Quality gate for OMR normalization reports.

    Usage:
        gate = OMRQualityGate()
        result = gate.check(report, OMRGateMode.STRICT)
        if result.allows_deterministic_edit:
            score = MusicXMLImporter().import_file(normalized_path)
        else:
            # route to human / AI review
    """

    def check(
        self,
        report: OMRNormalizationReport,
        mode: str = OMRGateMode.STRICT,
    ) -> OMRGateResult:
        """Classify issues and return a gate verdict."""
        if mode not in (OMRGateMode.STRICT, OMRGateMode.PERMISSIVE):
            raise ValueError(f"Unknown gate mode: {mode}")

        unresolved = [
            i for i in report.issues
            if i.status in (OMRStatus.OMR_ERROR, OMRStatus.NEEDS_REVIEW)
        ]
        resolved = [i for i in report.issues if i.status == OMRStatus.SAFE_FIX_APPLIED]
        info = [i for i in report.issues if i.status == OMRStatus.INFO]

        blocking = [i for i in unresolved if i.edit_safety == OMREditSafety.BLOCKING_FOR_EDIT]
        warnings = [
            i for i in unresolved
            if i.edit_safety in (OMREditSafety.NON_BLOCKING, "")
        ]

        if mode == OMRGateMode.STRICT:
            if not unresolved:
                # Only info / resolved issues present.
                return OMRGateResult(
                    mode=mode,
                    status="clean" if not resolved else "clean",
                    allowed=True,
                    allows_deterministic_edit=True,
                    info=info,
                    summary=self._summary(report, blocking=[], warnings=[], info=info),
                )
            if blocking:
                return OMRGateResult(
                    mode=mode,
                    status="blocked",
                    allowed=False,
                    allows_deterministic_edit=False,
                    blocking_issues=blocking,
                    warnings=warnings,
                    info=info,
                    summary=self._summary(
                        report, blocking=blocking, warnings=warnings, info=info
                    ),
                )
            # Unresolved warnings only.
            return OMRGateResult(
                mode=mode,
                status="degraded",
                allowed=True,
                allows_deterministic_edit=True,
                warnings=warnings,
                info=info,
                summary=self._summary(
                    report, blocking=[], warnings=warnings, info=info
                ),
            )

        # PERMISSIVE mode: everything is a warning, editing allowed.
        all_warnings = list(blocking + warnings)
        return OMRGateResult(
            mode=mode,
            status="clean" if not all_warnings else "degraded",
            allowed=True,
            allows_deterministic_edit=True,
            warnings=all_warnings,
            info=info,
            summary=self._summary(
                report, blocking=[], warnings=all_warnings, info=info
            ),
        )

    def _summary(
        self,
        report: OMRNormalizationReport,
        blocking: list[OMRIssue],
        warnings: list[OMRIssue],
        info: list[OMRIssue],
    ) -> dict[str, Any]:
        return {
            "input_path": report.input_path,
            "output_path": report.output_path,
            "total_issues": len(report.issues),
            "fixes_applied": len(report.fixes_applied),
            "blocking_for_edit": len(blocking),
            "warnings": len(warnings),
            "informational": len(info),
        }
