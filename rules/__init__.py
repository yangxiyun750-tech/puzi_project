"""Music theory rules and instrument knowledge.

This module contains deterministic, code-level rules for:
- Transposing instruments and their transposition intervals
- Practical written ranges for each instrument
- Clef conventions
- Key signature spellings
- Rhythmic notation standards

These are domain rules, not per-piece data. They are used by the Score Engine
for validation, range checking, and transposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TransposingInstrument:
    """A transposing instrument definition."""
    name: str
    transposition_chromatic: int  # semitones: written -> sounding
    transposition_diatonic: int   # scale steps: written -> sounding
    transposition_octave: int = 0


@dataclass
class InstrumentRange:
    """Practical written range for an instrument."""
    name: str
    min_midi: int
    max_midi: int
    clef: str = "G"  # default clef sign


# Transposing instruments (written -> sounding)
TRANSPOSING_INSTRUMENTS: dict[str, TransposingInstrument] = {
    "Clarinet in Bb": TransposingInstrument("Clarinet in Bb", -2, -1, 0),
    "Clarinet in A": TransposingInstrument("Clarinet in A", -3, -2, 0),
    "Trumpet in Bb": TransposingInstrument("Trumpet in Bb", -2, -1, 0),
    "Trumpet in C": TransposingInstrument("Trumpet in C", 0, 0, 0),
    "Horn in F": TransposingInstrument("Horn in F", -7, -4, 0),
    "Alto Saxophone": TransposingInstrument("Alto Saxophone", -9, -5, 0),
    "Tenor Saxophone": TransposingInstrument("Tenor Saxophone", -14, -8, 0),
    "Soprano Saxophone": TransposingInstrument("Soprano Saxophone", -2, -1, 0),
    "Baritone Saxophone": TransposingInstrument("Baritone Saxophone", -21, -12, 0),
    "English Horn": TransposingInstrument("English Horn", -7, -4, 0),
    "Piccolo": TransposingInstrument("Piccolo", 0, 0, 1),
    "Contrabassoon": TransposingInstrument("Contrabassoon", 0, 0, -1),
    "Double Bass": TransposingInstrument("Double Bass", 0, 0, -1),
    "Guitar": TransposingInstrument("Guitar", 0, 0, -1),
    "Celesta": TransposingInstrument("Celesta", 0, 0, 1),
    "Xylophone": TransposingInstrument("Xylophone", 0, 0, 1),
    "Glockenspiel": TransposingInstrument("Glockenspiel", 0, 0, 2),
    "Crotales": TransposingInstrument("Crotales", 0, 0, 2),
}

# Practical written ranges (midi)
PRACTICAL_RANGES: dict[str, InstrumentRange] = {
    "Piccolo": InstrumentRange("Piccolo", 74, 108, "G"),
    "Flute": InstrumentRange("Flute", 60, 96, "G"),
    "Oboe": InstrumentRange("Oboe", 58, 93, "G"),
    "Clarinet in Bb": InstrumentRange("Clarinet in Bb", 50, 88, "G"),
    "Clarinet in A": InstrumentRange("Clarinet in A", 49, 87, "G"),
    "Bass Clarinet": InstrumentRange("Bass Clarinet", 38, 76, "G"),
    "Bassoon": InstrumentRange("Bassoon", 34, 75, "F"),
    "Contrabassoon": InstrumentRange("Contrabassoon", 22, 64, "F"),
    "Horn in F": InstrumentRange("Horn in F", 31, 65, "G"),
    "Trumpet in Bb": InstrumentRange("Trumpet in Bb", 52, 84, "G"),
    "Trumpet in C": InstrumentRange("Trumpet in C", 54, 86, "G"),
    "Trombone": InstrumentRange("Trombone", 40, 70, "F"),
    "Bass Trombone": InstrumentRange("Bass Trombone", 23, 70, "F"),
    "Tuba": InstrumentRange("Tuba", 26, 65, "F"),
    "Violin": InstrumentRange("Violin", 55, 105, "G"),
    "Viola": InstrumentRange("Viola", 48, 88, "C"),
    "Cello": InstrumentRange("Cello", 36, 81, "F"),
    "Double Bass": InstrumentRange("Double Bass", 28, 67, "F"),
    "Harp": InstrumentRange("Harp", 23, 103, "G"),
    "Piano": InstrumentRange("Piano", 21, 108, "G"),
    "Timpani": InstrumentRange("Timpani", 38, 58, "F"),
    "Xylophone": InstrumentRange("Xylophone", 65, 108, "G"),
    "Glockenspiel": InstrumentRange("Glockenspiel", 79, 108, "G"),
    "Soprano": InstrumentRange("Soprano", 60, 84, "G"),
    "Alto": InstrumentRange("Alto", 53, 77, "G"),
    "Tenor": InstrumentRange("Tenor", 48, 71, "G"),
    "Bass": InstrumentRange("Bass", 40, 64, "F"),
    "Choir": InstrumentRange("Choir", 40, 84, "G"),
}


def get_transposition(instrument_name: str) -> TransposingInstrument | None:
    """Get transposition info for an instrument, or None if non-transposing."""
    return TRANSPOSING_INSTRUMENTS.get(instrument_name)


def get_practical_range(instrument_name: str) -> InstrumentRange | None:
    """Get practical written range for an instrument."""
    return PRACTICAL_RANGES.get(instrument_name)


def is_in_range(instrument_name: str, midi_pitch: int, tolerance: int = 2) -> bool:
    """Check if a written pitch is within the practical range of an instrument."""
    rng = PRACTICAL_RANGES.get(instrument_name)
    if rng is None:
        return True  # Unknown instrument, assume OK
    return rng.min_midi - tolerance <= midi_pitch <= rng.max_midi + tolerance
