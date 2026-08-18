"""OMR Normalization issue model.

Every finding from an OMR detector is represented as an OMRIssue.
The schema is intentionally separate from qa.qa_model so that the
OMR layer can be developed, tested, and reasoned about independently
of the downstream QA pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class OMRCategory:
    RHYTHM = "rhythm"
    STRUCTURE = "structure"
    DIVISIONS = "divisions"
    NOTATION = "notation"
    VOICE = "voice"


class OMRStatus:
    """Resolution status of an OMR issue."""

    # Defect present in raw OMR; no safe automatic fix exists.
    OMR_ERROR = "omr_error"

    # A deterministic, provably-correct fix was applied.
    SAFE_FIX_APPLIED = "safe_fix_applied"

    # Needs AI or human review.
    NEEDS_REVIEW = "needs_review"

    # Informational only.
    INFO = "info"


class OMREditSafety:
    """Edit-safety classification for downstream deterministic editing.

    OMR issues are classified independently of their resolution status:
    - blocking_for_edit: unresolved issues that make deterministic editing
      (transposition, part extraction, orchestration) unsafe.
    - non_blocking: issues that affect visual or performance semantics but
      do not endanger deterministic note/rhythm edits.
    - informational: observations that do not represent defects.
    """

    BLOCKING_FOR_EDIT = "blocking_for_edit"
    NON_BLOCKING = "non_blocking"
    INFORMATIONAL = "informational"


@dataclass
class OMRIssue:
    """One finding from the OMR normalization layer.

    Fields are deliberately flat and serializable so the report is easy
    to inspect and diff across runs.
    """

    issue_id: str
    category: str
    check: str
    status: str
    severity: str
    edit_safety: str = ""
    part_id: str = ""
    measure_number: str = ""
    voice_id: str = ""
    note_id: str = ""
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    fix: dict[str, Any] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "check": self.check,
            "status": self.status,
            "severity": self.severity,
            "edit_safety": self.edit_safety,
            "part_id": self.part_id,
            "measure_number": self.measure_number,
            "voice_id": self.voice_id,
            "note_id": self.note_id,
            "description": self.description,
            "evidence": self.evidence,
            "fix": self.fix,
            "provenance": self.provenance,
        }


@dataclass
class OMRNormalizationReport:
    """Aggregated result of normalizing one raw MusicXML file."""

    input_path: str
    output_path: str | None
    issues: list[OMRIssue] = field(default_factory=list)
    fixes_applied: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "issue_count": len(self.issues),
            "fix_count": len(self.fixes_applied),
            "issues": [i.to_dict() for i in self.issues],
            "fixes_applied": self.fixes_applied,
        }

    def by_category(self, category: str) -> list[OMRIssue]:
        return [i for i in self.issues if i.category == category]

    def by_status(self, status: str) -> list[OMRIssue]:
        return [i for i in self.issues if i.status == status]

    def by_severity(self, severity: str) -> list[OMRIssue]:
        return [i for i in self.issues if i.severity == severity]
