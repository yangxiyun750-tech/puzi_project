"""QA core model — status machine and issue structures.

Status machine (the only four outcomes allowed for any check):

    PASS          check passed, no action needed
    SAFE_REPAIR   deterministic, purely structural fix exists;
                  the fixer applies it, the check is re-run, and the
                  issue is either resolved (PASS) or escalated to AI_REVIEW
    AI_REVIEW     the AI must look at the LOCAL region of the original
                  score (evidence package prepared by the visual QA stage)
    HUMAN_REVIEW  neither a deterministic fix nor a reliable AI judgment
                  exists; a human must decide

Delivery gate: a project may be delivered only when NO open AI_REVIEW /
HUMAN_REVIEW issues remain. SAFE_REPAIR issues must carry
fix_applied=True and verified_after_fix="PASS". Silent delivery of
AI_REVIEW / HUMAN_REVIEW issues is forbidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class QAStatus:
    PASS = "PASS"
    SAFE_REPAIR = "SAFE_REPAIR"
    AI_REVIEW = "AI_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    SKIP = "SKIP"  # stage not applicable (e.g. lyrics QA on instrumental score)

    # Terminal resolutions
    FIXED = "FIXED"        # SAFE_REPAIR applied and re-verified -> PASS
    ESCALATED = "ESCALATED"  # SAFE_REPAIR did not resolve -> AI_REVIEW/HUMAN_REVIEW

    OPEN = {SAFE_REPAIR, AI_REVIEW, HUMAN_REVIEW}
    BLOCKING = {AI_REVIEW, HUMAN_REVIEW}


class QACategory:
    INPUT_PDF = "input_pdf"
    OMR_STRUCTURE = "omr_structure"
    INSTRUMENT_IDENTITY = "instrument_identity"
    RHYTHM_METER = "rhythm_meter"
    NOTATION_OBJECT = "notation_object"
    LYRICS = "lyrics"
    TRANSPOSITION_RANGE = "transposition_range"
    MUSESCORE_RENDER = "musescore_render"
    VISUAL_EVIDENCE = "visual_evidence"

    ALL = [
        INPUT_PDF,
        OMR_STRUCTURE,
        INSTRUMENT_IDENTITY,
        RHYTHM_METER,
        NOTATION_OBJECT,
        LYRICS,
        TRANSPOSITION_RANGE,
        MUSESCORE_RENDER,
        VISUAL_EVIDENCE,
    ]


@dataclass
class QAIssue:
    """One issue found by a QA stage, organized by Part -> Measure."""

    issue_id: str
    category: str
    check: str
    status: str  # PASS | SAFE_REPAIR | AI_REVIEW | HUMAN_REVIEW | SKIP
    severity: str  # high | medium | low | info
    part_id: str = ""
    measure_number: str = ""
    voice_id: str = ""
    note_id: str = ""
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: str = "high"  # high | medium | low
    # SAFE_REPAIR lifecycle
    fix: dict[str, Any] | None = None
    fix_applied: bool = False
    verified_after_fix: str | None = None  # PASS | FAIL -> escalates

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "check": self.check,
            "status": self.status,
            "severity": self.severity,
            "part_id": self.part_id,
            "measure_number": self.measure_number,
            "voice_id": self.voice_id,
            "note_id": self.note_id,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "fix": self.fix,
            "fix_applied": self.fix_applied,
            "verified_after_fix": self.verified_after_fix,
        }


@dataclass
class QAStageResult:
    """Result of one QA stage (input_pdf, rhythm_meter, ...)."""

    stage: str
    status: str = QAStatus.PASS  # PASS | WARN | FAIL | SKIP
    checks_run: int = 0
    issues: list[QAIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "checks_run": self.checks_run,
            "pass": len([i for i in self.issues if i.status == QAStatus.PASS]),
            "safe_repair": len([i for i in self.issues if i.status == QAStatus.SAFE_REPAIR]),
            "ai_review": len([i for i in self.issues if i.status == QAStatus.AI_REVIEW]),
            "human_review": len([i for i in self.issues if i.status == QAStatus.HUMAN_REVIEW]),
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class DeliveryVerdict:
    """Whether the current outputs may be delivered."""

    allowed: bool = True
    blocking_issue_ids: list[str] = field(default_factory=list)
    open_ai_review: int = 0
    open_human_review: int = 0
    unverified_safe_repair: int = 0
    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocking_issue_ids": self.blocking_issue_ids,
            "open_ai_review": self.open_ai_review,
            "open_human_review": self.open_human_review,
            "unverified_safe_repair": self.unverified_safe_repair,
            "conditions": self.conditions,
        }


@dataclass
class QAReport:
    """Aggregated report of the whole QA pipeline."""

    project: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    inputs: dict[str, str] = field(default_factory=dict)
    stages: list[QAStageResult] = field(default_factory=list)
    fixes_applied: list[dict[str, Any]] = field(default_factory=list)
    delivery_verdict: DeliveryVerdict = field(default_factory=DeliveryVerdict)

    def add_stage(self, stage: QAStageResult) -> None:
        self.stages.append(stage)

    def all_issues(self) -> list[QAIssue]:
        return [i for s in self.stages for i in s.issues]

    def open_issues(self) -> list[QAIssue]:
        """Issues still blocking delivery (AI_REVIEW / HUMAN_REVIEW, or
        SAFE_REPAIR without successful re-verification)."""
        out = []
        for i in self.all_issues():
            if i.status in QAStatus.BLOCKING:
                out.append(i)
            elif i.status == QAStatus.SAFE_REPAIR and (
                not i.fix_applied or i.verified_after_fix != QAStatus.PASS
            ):
                out.append(i)
        return out

    def compute_verdict(self) -> DeliveryVerdict:
        open_issues = self.open_issues()
        verdict = DeliveryVerdict()
        verdict.open_ai_review = len(
            [i for i in self.all_issues() if i.status == QAStatus.AI_REVIEW]
        )
        verdict.open_human_review = len(
            [i for i in self.all_issues() if i.status == QAStatus.HUMAN_REVIEW]
        )
        verdict.unverified_safe_repair = len(
            [
                i
                for i in self.all_issues()
                if i.status == QAStatus.SAFE_REPAIR
                and (not i.fix_applied or i.verified_after_fix != QAStatus.PASS)
            ]
        )
        verdict.blocking_issue_ids = [i.issue_id for i in open_issues]
        verdict.allowed = not open_issues
        if verdict.allowed:
            verdict.conditions.append(
                "All checks PASS or SAFE_REPAIR re-verified — delivery allowed."
            )
        else:
            verdict.conditions.append(
                "AI_REVIEW / HUMAN_REVIEW issues must be resolved and re-verified "
                "before delivery. Silent delivery of open review issues is forbidden."
            )
        self.delivery_verdict = verdict
        return verdict

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "created_at": self.created_at,
            "inputs": self.inputs,
            "stages": [s.to_dict() for s in self.stages],
            "fixes_applied": self.fixes_applied,
            "delivery_verdict": self.delivery_verdict.to_dict(),
        }
