"""TransposeRequest schema — the interface from the NL/command layer to the engine.

V1 supports two families of operations:
1. Relative interval transposition (transpose selected parts/measures by a
   named interval up or down).
2. Written/sounding conversion for transposing instruments.

Future versions may add absolute target-key transposition; the schema leaves
room for that by keeping ``interval`` and ``target_key`` separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from score_engine.transposition.interval import Interval


class TranspositionOperation(Enum):
    """Kind of transposition requested."""

    INTERVAL = "interval"
    WRITTEN_TO_SOUNDING = "written_to_sounding"
    SOUNDING_TO_WRITTEN = "sounding_to_written"


@dataclass(frozen=True, slots=True)
class TransposeRequest:
    """Request to transpose one or more parts of a score.

    Attributes:
        operation: What kind of transposition to perform.
        interval: Named interval for ``INTERVAL`` operations.
        part_ids: Parts to affect; ``None`` means all parts.
        measure_start: 1-based start measure (inclusive).
        measure_end: 1-based end measure (inclusive); ``None`` means to the end.
        preserve_original: If True, the engine deep-copies the score before
            modifying it (default True).
    """

    operation: TranspositionOperation = TranspositionOperation.INTERVAL
    interval: Interval | None = None
    part_ids: list[str] | None = None
    measure_start: int = 1
    measure_end: int | None = None
    preserve_original: bool = True

    def __post_init__(self) -> None:
        if self.operation == TranspositionOperation.INTERVAL and self.interval is None:
            raise ValueError("INTERVAL operation requires an interval")
        if self.measure_start < 1:
            raise ValueError("measure_start must be >= 1")
        if self.measure_end is not None and self.measure_end < self.measure_start:
            raise ValueError("measure_end must be >= measure_start")
