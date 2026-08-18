"""Natural-language intent schemas for transpose requests.

These dataclasses form the contract between:
- the AI intent provider (LLM / mock)
- the deterministic intent resolver
- the validator
- the caller

No ScoreIR objects are modified here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from score_engine.transposition.request import TransposeRequest


@dataclass(frozen=True, slots=True)
class IntentContext:
    """Minimal context sent to the AI provider for a transpose request.

    Contains no full MusicXML, no full ScoreIR, and no project code — only
    enough information for the model to choose parts and measure ranges.
    """

    available_parts: list[dict[str, Any]] = field(default_factory=list)
    min_measure: int = 1
    max_measure: int = 1
    supported_intervals: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TransposeIntent:
    """Raw structured intent returned by an AI provider.

    This is a *candidate* only. It must pass through deterministic resolution
    and validation before a ``TransposeRequest`` is produced.
    """

    status: str = "needs_clarification"  # ready | needs_clarification | unsupported | invalid | provider_error
    operation: str | None = None         # transpose | written_to_sounding | sounding_to_written
    direction: str | None = None         # up | down
    interval_description: str | None = None
    part_description: str | None = None
    measure_start_description: str | None = None
    measure_end_description: str | None = None
    is_all_parts: bool = False
    basis: str | None = None             # written | sounding | concert
    clarification_question: str = ""
    confidence: float = 0.0
    source_text: str = ""
    error_reason: str = ""
    diagnostics: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of deterministic validation."""

    valid: bool
    reason: str = ""


@dataclass
class TransposeIntentResult:
    """Final output of the NL → TransposeRequest layer."""

    status: str  # ready | needs_clarification | unsupported | invalid | provider_error
    request: TransposeRequest | None = None
    confidence: float = 0.0
    ambiguities: list[str] = field(default_factory=list)
    clarification_question: str = ""
    source_text: str = ""
    error_reason: str = ""
    diagnostics: tuple[Any, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "ready" and self.request is not None
