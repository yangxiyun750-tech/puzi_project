"""Deterministic Transposition Engine V1.

Public API for score transposition and instrument written/sounding conversion.
"""

from score_engine.transposition.engine import TranspositionEngine, TranspositionResult
from score_engine.transposition.interval import Interval, SpellingError
from score_engine.transposition.request import (
    TranspositionOperation,
    TransposeRequest,
)
from score_engine.transposition.report import (
    NoteChange,
    PartReport,
    TransposeReport,
)
from score_engine.transposition.service import SafeTranspositionService

__all__ = [
    "Interval",
    "SpellingError",
    "TranspositionOperation",
    "TransposeRequest",
    "NoteChange",
    "PartReport",
    "TransposeReport",
    "TranspositionEngine",
    "TranspositionResult",
    "SafeTranspositionService",
]
