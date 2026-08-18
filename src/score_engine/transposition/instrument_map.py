"""Instrument transposition mapping and resolution.

Provides a lookup table from common instrument names to
``InstrumentTransposition`` and a resolver that chooses the best available
source of transposition metadata for a Part.

Provenance chain (most reliable first):
1. Explicit MusicXML ``<transpose>`` metadata stored on ``Part.instrument.transposition``.
2. Instrument identity fallback based on the resolved/labelled instrument name.
3. Unknown — default C instrument.
"""

from __future__ import annotations

from dataclasses import dataclass

from score_engine.score_ir.score_ir import InstrumentTransposition, Part
from score_engine.transposition.interval import Interval


@dataclass(frozen=True, slots=True)
class ResolvedTransposition:
    """Resolved transposition metadata for a part."""

    transposition: InstrumentTransposition
    provenance: str  # "musicxml" | "identity" | "unknown"
    supported: bool  # False when MusicXML has unsupported variable/staff/double transpose
    reason: str = ""


# Common transposing instruments. Values follow MusicXML semantics:
#   sounding_pitch = written_pitch + transposition
_INSTRUMENT_TRANSPOSITIONS: dict[tuple[str, ...], InstrumentTransposition] = {
    # Bb instruments (written C sounds Bb)
    ("trumpet", "cornet", "flugelhorn", "clarinet", "soprano saxophone",
     "soprano sax", "tenor saxophone", "tenor sax", "bass clarinet",
     "bass trumpet", "contrabass clarinet"): InstrumentTransposition(-1, -2, 0),
    # Eb alto saxophone (written C sounds Eb)
    ("alto saxophone", "alto sax"): InstrumentTransposition(-5, -9, 0),
    # Eb baritone saxophone (written C sounds Eb, one octave lower)
    ("baritone saxophone", "baritone sax"): InstrumentTransposition(-5, -9, -1),
    # F horns / English horn (written C sounds F)
    ("horn", "french horn", "english horn", "cor anglais"): InstrumentTransposition(-4, -7, 0),
    # A clarinet (written C sounds A, a minor third lower)
    ("clarinet in a", "a clarinet"): InstrumentTransposition(-2, -3, 0),
    # Piccolo (written C sounds C, one octave higher)
    ("piccolo", "piccolo flute"): InstrumentTransposition(0, 0, 1),
    # Double bass / contrabass (written C sounds C, one octave lower)
    ("double bass", "contrabass", "string bass", "bass guitar"): InstrumentTransposition(0, 0, -1),
    # Guitar (written C sounds C, one octave lower)
    ("guitar", "acoustic guitar", "electric guitar"): InstrumentTransposition(0, 0, -1),
}


def _normalize(name: str) -> str:
    return name.lower().strip().replace("  ", " ")


# Base semitones for the seven diatonic interval classes (0 = unison, 1 = second, ...).
_INTERVAL_BASE_SEMITONES = {
    0: 0,
    1: 2,
    2: 4,
    3: 5,
    4: 7,
    5: 9,
    6: 11,
}
_INTERVAL_PERFECT_CLASSES = {0, 3, 4}


def transposition_to_interval(transposition: InstrumentTransposition) -> Interval:
    """Convert an ``InstrumentTransposition`` to a named ``Interval``.

    This captures the diatonic/chromatic portion. Any ``octave_change`` must be
    applied separately by the engine because ``Interval`` itself models
    compound intervals but not pure octave displacement.

    Raises:
        ValueError: if the transposition cannot be represented with V1 qualities.
    """
    d = transposition.diatonic
    c = transposition.chromatic

    if d == 0 and c == 0:
        return Interval(1, "P", 1)

    direction = 1 if d > 0 or (d == 0 and c > 0) else -1
    abs_d = abs(d)
    number = abs_d + 1
    interval_class = abs_d % 7
    octaves = abs_d // 7
    base = _INTERVAL_BASE_SEMITONES[interval_class]
    target_semitones = abs(c) - octaves * 12

    if interval_class in _INTERVAL_PERFECT_CLASSES:
        if target_semitones == base:
            quality = "P"
        else:
            raise ValueError(
                f"Cannot map perfect-class transposition {transposition} to V1 interval"
            )
    else:
        if target_semitones == base:
            quality = "M"
        elif target_semitones == base - 1:
            quality = "m"
        else:
            raise ValueError(
                f"Cannot map major/minor-class transposition {transposition} to V1 interval"
            )

    return Interval(number, quality, direction)


def lookup_instrument_transposition(name: str) -> InstrumentTransposition | None:
    """Look up a known transposition by instrument name/label."""
    normalized = _normalize(name)
    for aliases, transposition in _INSTRUMENT_TRANSPOSITIONS.items():
        if any(alias in normalized for alias in aliases):
            return transposition
    return None


def resolve_part_transposition(
    part: Part,
    canonical_name: str = "",
) -> ResolvedTransposition:
    """Return the best available transposition metadata for ``part``.

    The resolver checks, in order:
      1. ScoreIR / MusicXML transposition metadata stored on the part.
      2. Instrument identity fallback (``canonical_name`` or ``part.name``).
      3. Unknown C instrument.

    If the MusicXML metadata is present but flagged as unsupported
    (staff-specific, ``<double>``, or mid-part change), ``supported`` is False
    and the returned transposition is the default C instrument. The event list
    is preserved on the part for reporting.
    """
    # 1. Explicit ScoreIR / MusicXML metadata.
    if part.has_variable_transposition:
        return ResolvedTransposition(
            transposition=InstrumentTransposition(),
            provenance="musicxml",
            supported=False,
            reason="MusicXML contains unsupported variable transposition",
        )

    if part.instrument.transposition:
        return ResolvedTransposition(
            transposition=part.instrument.transposition,
            provenance="musicxml",
            supported=True,
            reason="ScoreIR/MusicXML transposition metadata",
        )

    if part.transposition_events:
        # Events existed but none set the instrument transposition (e.g. all
        # were staff-specific/double). Treat as unsupported.
        return ResolvedTransposition(
            transposition=InstrumentTransposition(),
            provenance="musicxml",
            supported=False,
            reason="MusicXML transposition metadata is staff-specific or double",
        )

    # 2. Instrument identity fallback.
    name = canonical_name or part.name or part.instrument.name
    if name:
        transposition = lookup_instrument_transposition(name)
        if transposition is not None:
            return ResolvedTransposition(
                transposition=transposition,
                provenance="identity",
                supported=True,
                reason=f"Instrument identity fallback: {name}",
            )

    # 3. Unknown.
    return ResolvedTransposition(
        transposition=InstrumentTransposition(),
        provenance="unknown",
        supported=True,
        reason="No transposition metadata or known instrument identity",
    )
