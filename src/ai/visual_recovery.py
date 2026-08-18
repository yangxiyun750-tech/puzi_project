"""AI visual recovery — structured visual score inspection.

This module is a STUB. It will be implemented when measure-level visual
evidence packages are available and the AI model is configured.

Planned interface:
    inspect_measure(crop_path: str, scoreir_data: dict) -> VisualRecoveryResult
    VisualRecoveryResult:
        - status: VISUAL_RECOVERED | NO_CHANGE_REQUIRED | HUMAN_REVIEW
        - confidence: 0.0-1.0
        - detected_content: {notes, rests, rhythm, tuplets, ties, slurs, ...}
        - proposed_action: str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VisualRecoveryResult:
    """Result of AI visual inspection of a measure region."""
    status: str = "HUMAN_REVIEW"
    confidence: float = 0.0
    detected_content: dict[str, Any] = field(default_factory=dict)
    proposed_action: str = ""


def inspect_measure(crop_path: str, scoreir_data: dict) -> VisualRecoveryResult:
    """Inspect a measure crop and return recovery recommendation.

    STUB: returns HUMAN_REVIEW. To be implemented.
    """
    return VisualRecoveryResult(
        status="HUMAN_REVIEW",
        confidence=0.0,
    )
