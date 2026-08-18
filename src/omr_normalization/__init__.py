"""OMR Validation / Recovery / Normalization Layer.

Optional preprocessing between raw Audiveris OMR MusicXML and the Score
Engine. Detects generic structural defects, applies only provably-correct
safe fixes, and emits an issue report without overwriting the raw input.
"""

from omr_normalization.issue_model import (
    OMRCategory,
    OMREditSafety,
    OMRNormalizationReport,
    OMRIssue,
    OMRStatus,
)
from omr_normalization.detectors import (
    DivisionsDetector,
    NotationDetector,
    OMRDetector,
    RhythmDetector,
    StructureDetector,
)
from omr_normalization.normalizer import OMRNormalizer
from omr_normalization.quality_gate import OMRGateMode, OMRGateResult, OMRQualityGate
from omr_normalization.reporter import OMRReporter

__all__ = [
    "OMRCategory",
    "OMREditSafety",
    "OMRNormalizationReport",
    "OMRIssue",
    "OMRStatus",
    "DivisionsDetector",
    "NotationDetector",
    "OMRDetector",
    "RhythmDetector",
    "StructureDetector",
    "OMRNormalizer",
    "OMRQualityGate",
    "OMRGateMode",
    "OMRGateResult",
    "OMRReporter",
]
