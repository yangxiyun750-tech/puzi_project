"""ScoreIR V1 — Unified Intermediate Representation for musical scores.

This module defines the canonical data model used between MusicXML import,
MuseScore export, and future AI editing. Every editable object carries a
stable ID of the form:

    PartID-MeasureNumber-VoiceID-EventIndex

Example: P2-M36-V1-N04

The model supports:
- Score → Part → Staff → Measure → Voice → Event hierarchy
- Pitch (written vs sounding), Duration, Rest, Chord
- KeySignature, TimeSignature, Clef, Tempo
- Dynamics, Articulations, Ties, Slurs, Lyrics
- EditHistory for future Undo/Redo
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any


# ---------------------------------------------------------------------------
# Stable ID helpers
# ---------------------------------------------------------------------------

_event_counter = itertools.count(1)


def make_note_id(part_id: str, measure_number: int | str, voice_id: str, index: int) -> str:
    """Stable ID for a note/rest/chord event."""
    return f"{part_id}-M{measure_number}-{voice_id}-N{index:02d}"


def make_measure_id(part_id: str, measure_number: int | str) -> str:
    return f"{part_id}-M{measure_number}"


def make_staff_id(part_id: str, staff_number: int) -> str:
    return f"{part_id}-S{staff_number}"


def make_voice_id(part_id: str, voice_number: int | str) -> str:
    return f"{part_id}-V{voice_number}"


def make_part_id(part_index: int) -> str:
    return f"P{part_index}"


# ---------------------------------------------------------------------------
# Primitive value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pitch:
    """Written pitch (what appears on the page)."""
    step: str  # A-G
    alter: int = 0  # -2 .. +2
    octave: int = 4  # Middle C = C4

    @property
    def midi(self) -> int:
        pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[self.step]
        return 12 * (self.octave + 1) + pc + self.alter

    def sounding(self, chromatic: int = 0, octave_change: int = 0) -> "Pitch":
        """Compute sounding pitch given transposition."""
        sounding_midi = self.midi + chromatic + 12 * octave_change
        # Simple respell — sufficient for V1
        octave = (sounding_midi // 12) - 1
        pc = sounding_midi % 12
        # Pick enharmonic spelling closest to written pitch
        candidates = []
        for step in "CDEFGAB":
            base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
            alter = pc - base
            if -2 <= alter <= 2:
                candidates.append((abs(alter), step, alter))
        candidates.sort()
        if candidates:
            _, step, alter = candidates[0]
            return Pitch(step, alter, octave)
        # Fallback
        return Pitch("C", 0, 4)


@dataclass(frozen=True, slots=True)
class Duration:
    """Absolute duration in divisions (MusicXML <divisions> units)."""
    divisions: int  # units per quarter note
    value: int  # actual duration in divisions

    @property
    def quarters(self) -> Fraction:
        return Fraction(self.value, self.divisions) if self.divisions else Fraction(0)

    def type_name(self) -> str:
        q = self.quarters
        if q == 4:
            return "whole"
        if q == 3:
            return "half-dot"
        if q == 2:
            return "half"
        if q == Fraction(3, 2):
            return "quarter-dot"
        if q == 1:
            return "quarter"
        if q == Fraction(1, 2):
            return "eighth"
        if q == Fraction(1, 4):
            return "16th"
        if q == Fraction(1, 8):
            return "32nd"
        return f"{q} quarters"


@dataclass(frozen=True, slots=True)
class KeySignature:
    fifths: int  # -7 .. +7
    mode: str = "major"


@dataclass(frozen=True, slots=True)
class TimeSignature:
    beats: int
    beat_type: int

    @property
    def quarters_per_measure(self) -> Fraction:
        return Fraction(self.beats * 4, self.beat_type)


@dataclass(frozen=True, slots=True)
class Clef:
    sign: str  # G, F, C, percussion
    line: int = 0
    octave_change: int = 0


# ---------------------------------------------------------------------------
# Music object hierarchy
# ---------------------------------------------------------------------------


@dataclass
class Tempo:
    beat_unit: str = "quarter"
    per_minute: int = 120


@dataclass
class Dynamic:
    mark: str  # p, mf, f, ff, etc.


@dataclass
class Articulation:
    mark: str  # staccato, tenuto, accent, etc.


@dataclass
class Tie:
    type: str  # start | stop
    number: int = 1


@dataclass
class Slur:
    type: str  # start | stop | continue
    number: int = 1
    placement: str = ""


@dataclass
class Lyric:
    number: str = "1"
    syllabic: str = "single"
    text: str = ""
    extend_type: str | None = None  # start | stop | continue


@dataclass
class Note:
    """A single note event (not a chord)."""
    id: str
    pitch: Pitch | None = None  # None for rest
    duration: Duration = field(default_factory=lambda: Duration(1, 1))
    voice: str = "1"
    staff: int = 1
    type: str = "quarter"  # whole, half, quarter, ...
    dots: int = 0
    is_chord_tone: bool = False
    is_grace: bool = False
    accidental: str | None = None
    ties: list[Tie] = field(default_factory=list)
    slurs: list[Slur] = field(default_factory=list)
    articulations: list[Articulation] = field(default_factory=list)
    lyrics: list[Lyric] = field(default_factory=list)
    stem_direction: str = ""
    beam: str = ""  # begin | continue | end | forward hook | backward hook
    # Extended notation objects (V1.1)
    tuplet: str = ""  # start | stop
    fermata: bool = False
    arpeggiate: bool = False

    @property
    def is_rest(self) -> bool:
        return self.pitch is None


@dataclass
class Rest:
    """Explicit rest object (usually merged into Note with pitch=None)."""
    id: str
    duration: Duration = field(default_factory=lambda: Duration(1, 1))
    voice: str = "1"
    staff: int = 1
    type: str = "quarter"
    dots: int = 0
    display_step: str = "B"
    display_octave: int = 4


@dataclass
class Chord:
    """A group of simultaneous notes sharing the same onset."""
    id: str
    notes: list[Note] = field(default_factory=list)

    @property
    def duration(self) -> Duration:
        return self.notes[0].duration if self.notes else Duration(1, 1)

    @property
    def voice(self) -> str:
        return self.notes[0].voice if self.notes else "1"

    @property
    def staff(self) -> int:
        return self.notes[0].staff if self.notes else 1


@dataclass
class Voice:
    """A single rhythmic voice layer within a measure.

    This is a *rhythmic* voice (e.g., voice 1 = RH, voice 5 = LH in Piano).
    It is NOT a vocal/human voice. Do not confuse with Vocal Part.
    A single staff may contain multiple voice layers for polyphonic notation.
    """
    id: str
    events: list[Note | Chord | Rest] = field(default_factory=list)

    @property
    def total_duration(self) -> Fraction:
        """Sum of event durations, excluding chord-tone durations.

        Chord tones (<chord/> in MusicXML) share the same onset as the
        first note of the chord and do not consume additional time. Their
        duration must not be added to the measure total.
        """
        total = Fraction(0)
        for e in self.events:
            if isinstance(e, Note) and e.is_chord_tone:
                continue
            if hasattr(e, "duration"):
                total += e.duration.quarters
        return total


@dataclass
class Measure:
    """One measure in one part."""
    id: str
    number: str
    implicit: bool = False  # pickup measure
    key_signature: KeySignature | None = None
    time_signature: TimeSignature | None = None
    clefs: dict[int, Clef] = field(default_factory=dict)  # staff_number -> clef
    tempo: Tempo | None = None
    dynamics: list[Dynamic] = field(default_factory=list)
    voices: list[Voice] = field(default_factory=list)
    barlines: list[dict[str, Any]] = field(default_factory=list)
    divisions: int = 1  # MusicXML divisions in effect for this measure

    # Removed the @property divisions that always returned 1


@dataclass
class Staff:
    """One physical staff within a part."""
    id: str
    number: int
    clef: Clef = field(default_factory=lambda: Clef("G", 2))
    measures: list[Measure] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class InstrumentTransposition:
    """Instrument transposition metadata following MusicXML semantics.

    For a transposing instrument, the relationship is:
        sounding_pitch = written_pitch + transposition

    Examples:
        Bb Trumpet:   diatonic=-1, chromatic=-2, octave_change=0
        Eb Alto Sax:  diatonic=-5, chromatic=-9, octave_change=0
        F Horn:       diatonic=-4, chromatic=-7, octave_change=0
        Piccolo:      diatonic=0, chromatic=0, octave_change=1
        Double Bass:  diatonic=0, chromatic=0, octave_change=-1
    """
    diatonic: int = 0       # Staff-step offset from written to sounding
    chromatic: int = 0      # Semitone offset from written to sounding
    octave_change: int = 0  # Additional octave displacement

    def __bool__(self) -> bool:
        return not (self.diatonic == 0 and self.chromatic == 0 and self.octave_change == 0)


@dataclass
class Instrument:
    """MuseScore instrument definition."""
    id: str = ""
    name: str = ""
    sound: str = ""
    midi_program: int = 0
    midi_channel: int = 1
    transposition_chromatic: int = 0
    transposition_octave: int = 0
    transposition: InstrumentTransposition = field(default_factory=InstrumentTransposition)


@dataclass
class Part:
    """One instrumental or vocal part."""
    id: str
    name: str = ""
    abbreviation: str = ""
    instrument: Instrument = field(default_factory=Instrument)
    staves: list[Staff] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    # Minimal metadata extension for transposition handling.
    # transposition_events records per-measure transposition metadata when
    # MusicXML provides <transpose> elements.
    transposition_events: list[dict[str, Any]] = field(default_factory=list)
    has_variable_transposition: bool = False


@dataclass
class Score:
    """Root of the ScoreIR tree."""
    title: str = ""
    parts: list[Part] = field(default_factory=list)
    page_layout: dict[str, Any] = field(default_factory=dict)

    def get_part(self, part_id: str) -> Part | None:
        for p in self.parts:
            if p.id == part_id:
                return p
        return None


# ---------------------------------------------------------------------------
# Edit History (preparation for Undo/Redo)
# ---------------------------------------------------------------------------


@dataclass
class ScoreEdit:
    """A single atomic edit operation."""
    edit_id: str
    operation: str  # transpose, change_pitch, change_rhythm, replace_instrument, ...
    target_id: str  # e.g. P2-M36-V1-N04
    parameters: dict[str, Any] = field(default_factory=dict)
    previous_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class EditHistory:
    """Ordered list of edits with undo/redo support."""
    edits: list[ScoreEdit] = field(default_factory=list)
    current_index: int = 0

    def apply(self, edit: ScoreEdit) -> None:
        """Apply a new edit, truncating any redo history."""
        del self.edits[self.current_index:]
        self.edits.append(edit)
        self.current_index = len(self.edits)

    def can_undo(self) -> bool:
        return self.current_index > 0

    def can_redo(self) -> bool:
        return self.current_index < len(self.edits)

    def undo(self) -> ScoreEdit | None:
        if self.can_undo():
            self.current_index -= 1
            return self.edits[self.current_index]
        return None

    def redo(self) -> ScoreEdit | None:
        if self.can_redo():
            edit = self.edits[self.current_index]
            self.current_index += 1
            return edit
        return None


# ---------------------------------------------------------------------------
# Repair classification (V2)
# ---------------------------------------------------------------------------


class RepairType:
    SAFE = "SAFE_REPAIR"
    MUSICAL = "MUSICAL_REPAIR"
    VISUAL = "NEEDS_VISUAL_RECOVERY"


@dataclass
class RepairIssue:
    """One issue found during reconstruction."""
    issue_id: str
    repair_type: str  # SAFE_REPAIR | MUSICAL_REPAIR | NEEDS_VISUAL_RECOVERY
    severity: str  # low | medium | high
    part_id: str
    measure_number: str
    description: str
    original_content: dict[str, Any] = field(default_factory=dict)
    applied_fix: dict[str, Any] = field(default_factory=dict)
    needs_human_review: bool = False


@dataclass
class RepairLog:
    """Log of all repairs applied to a score."""
    issues: list[RepairIssue] = field(default_factory=list)

    def add(self, issue: RepairIssue) -> None:
        self.issues.append(issue)

    def by_type(self, repair_type: str) -> list[RepairIssue]:
        return [i for i in self.issues if i.repair_type == repair_type]

    def by_severity(self, severity: str) -> list[RepairIssue]:
        return [i for i in self.issues if i.severity == severity]

    def open_issues(self) -> list[RepairIssue]:
        return [i for i in self.issues if i.needs_human_review]
