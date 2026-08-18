"""OMR detectors package."""

from omr_normalization.detectors.base import OMRDetector, _local
from omr_normalization.detectors.rhythm import RhythmDetector
from omr_normalization.detectors.structure import StructureDetector
from omr_normalization.detectors.divisions import DivisionsDetector
from omr_normalization.detectors.notation import NotationDetector

__all__ = [
    "OMRDetector",
    "_local",
    "RhythmDetector",
    "StructureDetector",
    "DivisionsDetector",
    "NotationDetector",
]
