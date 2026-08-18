"""Key signature handling for measure-range transposition.

Provides:
- Conversion between key signature (fifths/mode) and tonic pitch.
- Transposition of a key signature by a named interval.
- A per-part key timeline that records where key changes happen, so a
  measure-range transposition can restore the original active key at the
  measure immediately following the range.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from score_engine.score_ir.score_ir import KeySignature, Part, Pitch
from score_engine.transposition.interval import Interval, SpellingError


# Standard tonic spellings for major and minor keys in the range [-7, +7].
_MAJOR_TONICS: dict[int, Pitch] = {
    -7: Pitch("C", -1, 4),  # Cb major
    -6: Pitch("G", -1, 4),  # Gb major
    -5: Pitch("D", -1, 4),  # Db major
    -4: Pitch("A", -1, 4),  # Ab major
    -3: Pitch("E", -1, 4),  # Eb major
    -2: Pitch("B", -1, 4),  # Bb major
    -1: Pitch("F", 0, 4),   # F major
    0: Pitch("C", 0, 4),    # C major
    1: Pitch("G", 0, 4),    # G major
    2: Pitch("D", 0, 4),    # D major
    3: Pitch("A", 0, 4),    # A major
    4: Pitch("E", 0, 4),    # E major
    5: Pitch("B", 0, 4),    # B major
    6: Pitch("F", 1, 4),    # F# major
    7: Pitch("C", 1, 4),    # C# major
}

_MINOR_TONICS: dict[int, Pitch] = {
    -7: Pitch("A", -1, 4),  # Ab minor
    -6: Pitch("E", -1, 4),  # Eb minor
    -5: Pitch("B", -1, 4),  # Bb minor
    -4: Pitch("F", 0, 4),   # F minor
    -3: Pitch("C", 0, 4),   # C minor
    -2: Pitch("G", 0, 4),   # G minor
    -1: Pitch("D", 0, 4),   # D minor
    0: Pitch("A", 0, 4),    # A minor
    1: Pitch("E", 0, 4),    # E minor
    2: Pitch("B", 0, 4),    # B minor
    3: Pitch("F", 1, 4),    # F# minor
    4: Pitch("C", 1, 4),    # C# minor
    5: Pitch("G", 1, 4),    # G# minor
    6: Pitch("D", 1, 4),    # D# minor
    7: Pitch("A", 1, 4),    # A# minor
}

_MODE_TONICS = {
    "major": _MAJOR_TONICS,
    "minor": _MINOR_TONICS,
}


def _build_reverse_lookups() -> dict[str, dict[tuple[str, int], int]]:
    """Build (step, alter) -> fifths reverse lookup for each mode."""
    reverse: dict[str, dict[tuple[str, int], int]] = {}
    for mode, table in _MODE_TONICS.items():
        reverse[mode] = {(p.step, p.alter): fifths for fifths, p in table.items()}
    return reverse


_REVERSE_TONICS = _build_reverse_lookups()


def tonic_for_key(fifths: int, mode: str) -> Pitch:
    """Return the tonic pitch for a key signature."""
    table = _MODE_TONICS.get(mode, _MAJOR_TONICS)
    if fifths not in table:
        raise ValueError(f"V1 key signatures support fifths in [-7, +7]; got {fifths}")
    return table[fifths]


def fifths_for_tonic(pitch: Pitch, mode: str) -> int:
    """Return the fifths count for a spelled tonic and mode."""
    table = _REVERSE_TONICS.get(mode, _REVERSE_TONICS["major"])
    key = (pitch.step, pitch.alter)
    if key not in table:
        raise ValueError(
            f"Cannot map {pitch} to a V1 key signature for mode {mode!r}"
        )
    return table[key]


def transpose_key_signature(key: KeySignature, interval: Interval) -> KeySignature:
    """Transpose a key signature by ``interval``.

    The mode is preserved. The tonic is transposed using the immutable
    diatonic spelling rules, then mapped back to a fifths count.

    Raises:
        SpellingError: if the transposed tonic requires an out-of-bounds accidental.
        ValueError: if the resulting key signature is outside the supported range.
    """
    if key is None:
        return key
    tonic = tonic_for_key(key.fifths, key.mode)
    new_tonic = interval.apply(tonic)
    new_fifths = fifths_for_tonic(new_tonic, key.mode)
    return KeySignature(new_fifths, key.mode)


@dataclass
class KeyTimeline:
    """Timeline of key-signature changes within a Part."""

    events: list[tuple[int, KeySignature]] = field(default_factory=list)

    @classmethod
    def from_part(cls, part: Part) -> "KeyTimeline":
        """Build a timeline from explicit key signatures found in measures."""
        events: list[tuple[int, KeySignature]] = []
        current: KeySignature | None = None
        for idx, measure in enumerate(part.measures):
            key = measure.key_signature
            if key is not None and key != current:
                events.append((idx, key))
                current = key
        return cls(events)

    def active_key_at(self, measure_index: int) -> KeySignature | None:
        """Return the key signature active at ``measure_index`` (inclusive)."""
        active: KeySignature | None = None
        for idx, key in self.events:
            if idx <= measure_index:
                active = key
            else:
                break
        return active

    def is_event_index(self, measure_index: int) -> bool:
        """True if the measure index is the location of an explicit key change."""
        return any(idx == measure_index for idx, _ in self.events)


def prepare_range_key_restoration(
    part: Part,
    start_index: int,
    end_index: int,
    timeline: KeyTimeline,
) -> KeySignature | None:
    """Return the key signature that must be restored at ``end_index + 1``.

    Returns ``None`` when no restoration is required (range reaches part end or
    the following measure already has an explicit key change in the original).
    """
    restore_index = end_index + 1
    if restore_index >= len(part.measures):
        return None
    if timeline.is_event_index(restore_index):
        return None
    return timeline.active_key_at(restore_index)
