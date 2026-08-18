"""Unified QA Pipeline V1.

Stages: input_pdf -> omr_structure -> instrument_identity ->
rhythm_meter -> notation_object -> lyrics -> transposition_range ->
SAFE_REPAIR fix/re-verify -> musescore_render -> visual_evidence.

All issues carry one of: PASS | SAFE_REPAIR | AI_REVIEW | HUMAN_REVIEW.
Delivery is allowed only when no open AI_REVIEW / HUMAN_REVIEW issues
remain and every SAFE_REPAIR issue was applied and re-verified.
"""

from qa.qa_model import (
    QACategory,
    QAIssue,
    QAReport,
    QAStageResult,
    QAStatus,
    DeliveryVerdict,
)
from qa.pdf_qa import PDFInputQA, PDFQAConfig, PageMetrics
from qa.structure_qa import StructureQA
from qa.instrument_qa import InstrumentQA
from qa.rhythm_qa import RhythmQA, parse_rhythm
from qa.notation_qa import NotationQA
from qa.lyrics_qa import LyricsQA
from qa.range_qa import TranspositionRangeQA
from qa.render_qa import RenderQA
from qa.visual_qa import VisualQA
from qa.fixer import SafeFixer
from qa.reporter import QAReporter
from qa.qa_pipeline import QAPipeline, main

__all__ = [
    "QACategory",
    "QAIssue",
    "QAReport",
    "QAStageResult",
    "QAStatus",
    "DeliveryVerdict",
    "PDFInputQA",
    "PDFQAConfig",
    "PageMetrics",
    "StructureQA",
    "InstrumentQA",
    "RhythmQA",
    "parse_rhythm",
    "NotationQA",
    "LyricsQA",
    "TranspositionRangeQA",
    "RenderQA",
    "VisualQA",
    "SafeFixer",
    "QAReporter",
    "QAPipeline",
    "main",
]
