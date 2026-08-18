"""Named musical interval with immutable diatonic spelling.

V1 supports:
- simple and compound intervals
- qualities M (major), m (minor), P (perfect)
- directions up (+1) and down (-1)

V1 rejects augmented/diminished qualities because they complicate enharmonic
spelling without adding value for the current use cases.
"""

from __future__ import annotations

from dataclasses import dataclass

from score_engine.score_ir.score_ir import Pitch


_STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
_INDEX_STEP = {v: k for k, v in _STEP_INDEX.items()}

# Semitones for the seven 0-based diatonic interval classes within an octave.
# class 0 = unison, 1 = second, ..., 6 = seventh.
_BASE_SEMITONES = {
    0: 0,
    1: 2,
    2: 4,
    3: 5,
    4: 7,
    5: 9,
    6: 11,
}

# Diatonic classes that are perfect (0, 3, 4) vs major (1, 2, 5, 6).
_PERFECT_CLASSES = {0, 3, 4}


@dataclass(frozen=True, slots=True)
class Interval:
    """A named interval (e.g. M3, m2, P8).

    Attributes:
        number: Interval number (1 = unison, 2 = second, 8 = octave,
            9 = compound second, etc.).
        quality: "M", "m", or "P" (V1 rejects "A" and "d").
        direction: +1 for ascending, -1 for descending.
    """

    number: int
    quality: str
    direction: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.number, int) or self.number < 1:
            raise ValueError(f"Interval number must be a positive integer, got {self.number!r}")
        if self.quality not in ("M", "m", "P"):
            raise ValueError(
                f"V1 only supports qualities M, m, P; got {self.quality!r}"
            )
        if self.direction not in (1, -1):
            raise ValueError(f"Interval direction must be +1 or -1, got {self.direction}")

        # Validate that quality is compatible with interval number.
        interval_class = (self.number - 1) % 7
        if interval_class in _PERFECT_CLASSES and self.quality in ("M", "m"):
            raise ValueError(
                f"Interval number {self.number} is perfect and cannot be {self.quality}"
            )
        if interval_class not in _PERFECT_CLASSES and self.quality == "P":
            raise ValueError(
                f"Interval number {self.number} is major/minor and cannot be P"
            )

    def __str__(self) -> str:
        sign = "+" if self.direction == 1 else "-"
        return f"{sign}{self.quality}{self.number}"

    @property
    def semitones(self) -> int:
        """Total chromatic distance of the interval (always non-negative)."""
        interval_class = (self.number - 1) % 7
        octaves = (self.number - 1) // 7
        base = _BASE_SEMITONES[interval_class]
        quality_adjust = 0
        if self.quality == "m":
            quality_adjust = -1
        return octaves * 12 + base + quality_adjust

    def apply(self, pitch: Pitch) -> Pitch:
        """Apply this interval to ``pitch`` while preserving the named diatonic step.

        The target staff step is determined solely by the interval number and the
        source step. The accidental is then chosen so that the chromatic distance
        matches ``self.semitones``. If the required accidental falls outside
        [-2, +2] V1 reports it by raising ``SpellingError``; the caller can decide
        whether to treat this as unsupported.
        """
        if pitch is None:
            raise TypeError("Cannot apply interval to a rest (pitch is None)")

        src_index = _STEP_INDEX[pitch.step]
        diatonic_distance = self.direction * (self.number - 1)
        target_index = (src_index + diatonic_distance) % 7
        octave_carry = (src_index + diatonic_distance) // 7
        target_step = _INDEX_STEP[target_index]
        target_octave = pitch.octave + octave_carry

        chromatic_distance = self.direction * self.semitones
        target_midi = pitch.midi + chromatic_distance

        # Determine accidental for the target step that yields target_midi.
        base_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[target_step]
        target_pc = target_midi % 12
        alter = target_pc - base_pc

        # Normalize alter into canonical range [-2, 2]. If it is outside that
        # range we keep the immutable diatonic step but raise so the engine can
        # report unsupported spelling.
        if alter < -2 or alter > 2:
            raise SpellingError(
                f"Interval {self} from {pitch} requires alter={alter} on {target_step}"
            )

        return Pitch(target_step, alter, target_octave)

    def inverted(self) -> "Interval":
        """Return the interval that undoes this one (same number, opposite direction)."""
        return Interval(self.number, self.quality, -self.direction)


class SpellingError(ValueError):
    """Raised when a named interval produces an out-of-bounds accidental."""
