"""E2E fixtures for natural-language transposition acceptance tests.

Provides clean, synthetic MusicXML scores that pass the OMR Quality Gate in
STRICT mode and contain enough musical material to verify transposition
correctness end-to-end.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from score_engine.musicxml import MusicXMLImporter
from score_engine.score_ir.score_ir import (
    Chord,
    Duration,
    Instrument,
    InstrumentTransposition,
    KeySignature,
    Measure,
    Note,
    Part,
    Pitch,
    Rest,
    Score,
    Voice,
)


# ---------------------------------------------------------------------------
# MusicXML string builders
# ---------------------------------------------------------------------------

def _note_xml(
    step: str,
    octave: int,
    alter: int = 0,
    duration: int = 1,
    is_chord: bool = False,
    is_grace: bool = False,
    is_rest: bool = False,
) -> str:
    """Return a minimal <note> element string."""
    tags: list[str] = []
    if is_grace:
        tags.append('<grace slash="yes"/>')
    if is_chord:
        tags.append('<chord/>')
    if is_rest:
        tags.append('<rest/>')
    else:
        alter_tag = f"<alter>{alter}</alter>" if alter else ""
        tags.append(f"<pitch><step>{step}</step>{alter_tag}<octave>{octave}</octave></pitch>")
    tags.append(f"<duration>{duration}</duration>")
    tags.append("<type>quarter</type>")
    if is_rest:
        tags.append("<voice>1</voice>")
    else:
        tags.append("<voice>1</voice>")
    return "<note>" + "".join(tags) + "</note>"


def _measure_xml(
    number: int,
    divisions: int = 1,
    fifths: int = 0,
    include_chord: bool = False,
    include_grace: bool = False,
    is_rest_measure: bool = False,
    transpose_xml: str = "",
) -> str:
    """Build one <measure> element with total duration == 4."""
    attrs = [f'<divisions>{divisions}</divisions>']
    if number == 1 or fifths != 0:
        attrs.append(f'<key><fifths>{fifths}</fifths><mode>major</mode></key>')
    if number == 1:
        attrs.append('<time><beats>4</beats><beat-type>4</beat-type></time>')
        attrs.append('<clef><sign>G</sign><line>2</line></clef>')
    if transpose_xml:
        attrs.append(transpose_xml)

    notes: list[str] = []
    if is_rest_measure:
        notes.append(_note_xml("C", 4, duration=4, is_rest=True))
    else:
        # Pattern: quarter note + optional chord tones (1 div), quarter rest,
        # half rest. Total 4.
        notes.append(_note_xml("C", 4, duration=1))
        if include_chord:
            notes.append(_note_xml("E", 4, duration=1, is_chord=True))
            notes.append(_note_xml("G", 4, duration=1, is_chord=True))
        if include_grace:
            notes.append(_note_xml("B", 4, is_grace=True))
        notes.append(_note_xml("C", 4, duration=1, is_rest=True))
        notes.append(_note_xml("C", 4, duration=2, is_rest=True))

    return (
        f'<measure number="{number}" width="100">'
        + '<attributes>' + "".join(attrs) + '</attributes>'
        + "".join(notes)
        + '</measure>'
    )


def make_clean_musicxml(measures: int = 50, trumpets: int = 2) -> str:
    """Return a clean synthetic MusicXML string.

    Parts:
      - P1 Trumpet 1 (Bb transposition)
      - P2 Trumpet 2 (Bb transposition) if trumpets == 2
      - P3 Trombone
      - P4 Piano

    The score is designed to pass OMRNormalizer + Quality Gate STRICT.
    """
    parts_meta = []
    if trumpets >= 1:
        parts_meta.append(("P1", "Trumpet 1", "Trumpet", True))
    if trumpets >= 2:
        parts_meta.append(("P2", "Trumpet 2", "Trumpet", True))
    parts_meta.append(("P3", "Trombone", "Trombone", False))
    parts_meta.append(("P4", "Piano", "Piano", False))

    part_list = ""
    for pid, name, instr, _ in parts_meta:
        part_list += f'<score-part id="{pid}"><part-name>{name}</part-name></score-part>'

    parts_xml = ""
    for pid, name, instr, is_bb in parts_meta:
        transpose_xml = (
            "<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic><octave-change>0</octave-change></transpose>"
        ) if is_bb else ""

        measures_xml = ""
        for m in range(1, measures + 1):
            key_changes = {10: 2, 20: -3, 30: 1, 40: -2}
            fifths = key_changes.get(m, 0) if m != 1 else 0
            include_chord = m == 1
            include_grace = m == 1
            is_rest = m % 7 == 0  # every 7th measure is a rest measure
            measures_xml += _measure_xml(
                m,
                fifths=fifths,
                include_chord=include_chord,
                include_grace=include_grace,
                is_rest_measure=is_rest,
                transpose_xml=transpose_xml if m == 1 else "",
            )

        parts_xml += f'<part id="{pid}">{measures_xml}</part>'

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="4.0">'
        '<part-list>' + part_list + '</part-list>'
        + parts_xml
        + '</score-partwise>'
    )
    return xml


def make_single_trumpet_musicxml(measures: int = 50) -> str:
    """Clean score with only one Bb trumpet, trombone, piano."""
    return make_clean_musicxml(measures=measures, trumpets=1)


def import_fixture(xml_string: str) -> Score:
    """Import a MusicXML string into ScoreIR via a temporary file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".musicxml", delete=False, encoding="utf-8") as f:
        f.write(xml_string)
        path = f.name
    try:
        return MusicXMLImporter().import_file(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# ScoreIR fixture builders (fallback / comparison)
# ---------------------------------------------------------------------------

def make_scoreir_fixture(measures: int = 50, trumpets: int = 2) -> Score:
    """Build the same content directly as ScoreIR.

    Useful when we want to bypass MusicXML import for pure ScoreIR tests.
    """
    score = Score(title="E2E Transposition Fixture")
    if trumpets >= 1:
        score.parts.append(_make_scoreir_part("P1", "Trumpet 1", "Trumpet", InstrumentTransposition(-1, -2, 0), measures))
    if trumpets >= 2:
        score.parts.append(_make_scoreir_part("P2", "Trumpet 2", "Trumpet", InstrumentTransposition(-1, -2, 0), measures))
    score.parts.append(_make_scoreir_part("P3", "Trombone", "Trombone", InstrumentTransposition(), measures))
    score.parts.append(_make_scoreir_part("P4", "Piano", "Piano", InstrumentTransposition(), measures))
    return score


def _make_scoreir_part(
    part_id: str,
    name: str,
    instrument_name: str,
    transposition: InstrumentTransposition,
    measure_count: int,
) -> Part:
    part = Part(
        id=part_id,
        name=name,
        instrument=Instrument(name=instrument_name, transposition=transposition),
    )
    key_changes = {10: 2, 20: -3, 30: 1, 40: -2}
    for i in range(1, measure_count + 1):
        fifths = key_changes.get(i, 0) if i != 1 else 0
        measure = Measure(
            id=f"{part_id}-M{i}",
            number=str(i),
            key_signature=KeySignature(fifths=fifths, mode="major"),
        )
        voice = Voice(id=f"{part_id}-V{i}")

        is_rest = i % 7 == 0
        if is_rest:
            voice.events.append(Rest(id=f"{part_id}-M{i}-V1-R00", duration=Duration(4, 1), voice="1"))
        else:
            # Main note
            notes = [Note(
                id=f"{part_id}-M{i}-V1-N00",
                pitch=Pitch("C", 0, 4),
                duration=Duration(1, 1),
                voice="1",
            )]
            if i == 1:
                # Chord tones
                notes.append(Note(
                    id=f"{part_id}-M{i}-V1-N01",
                    pitch=Pitch("E", 0, 4),
                    duration=Duration(1, 1),
                    voice="1",
                    is_chord_tone=True,
                ))
                notes.append(Note(
                    id=f"{part_id}-M{i}-V1-N02",
                    pitch=Pitch("G", 0, 4),
                    duration=Duration(1, 1),
                    voice="1",
                    is_chord_tone=True,
                ))
                # Grace note
                notes.append(Note(
                    id=f"{part_id}-M{i}-V1-N03",
                    pitch=Pitch("B", 0, 4),
                    duration=Duration(0, 1),
                    voice="1",
                    is_grace=True,
                ))
            chord_or_note = Chord(id=f"{part_id}-M{i}-V1-C00", notes=notes) if len(notes) > 1 else notes[0]
            voice.events.append(chord_or_note)
            voice.events.append(Rest(id=f"{part_id}-M{i}-V1-R00", duration=Duration(1, 1), voice="1"))
            voice.events.append(Rest(id=f"{part_id}-M{i}-V1-R01", duration=Duration(2, 1), voice="1"))

        measure.voices.append(voice)
        part.measures.append(measure)
    return part


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def iter_notes(score: Score, part_ids: list[str] | None = None, measure_start: int = 1, measure_end: int | None = None):
    """Yield (part_id, measure_index_1based, event, note) tuples."""
    for part in score.parts:
        if part_ids is not None and part.id not in part_ids:
            continue
        end = measure_end if measure_end is not None else len(part.measures)
        for idx in range(measure_start, end + 1):
            measure = part.measures[idx - 1]
            for voice in measure.voices:
                for event in voice.events:
                    if isinstance(event, Note) and event.pitch is not None:
                        yield part.id, idx, event, event
                    elif isinstance(event, Chord):
                        for note in event.notes:
                            if note.pitch is not None:
                                yield part.id, idx, event, note


def count_notes(
    score: Score,
    part_ids: list[str] | None = None,
    measure_start: int = 1,
    measure_end: int | None = None,
    include_grace: bool = True,
) -> int:
    """Count Note objects in the selected range."""
    total = 0
    for _, _, _, note in iter_notes(score, part_ids, measure_start, measure_end):
        if note.is_grace and not include_grace:
            continue
        total += 1
    return total


def count_rests(score: Score, part_ids: list[str] | None = None, measure_start: int = 1, measure_end: int | None = None) -> int:
    """Count Rest objects in the selected range."""
    total = 0
    for part in score.parts:
        if part_ids is not None and part.id not in part_ids:
            continue
        end = measure_end if measure_end is not None else len(part.measures)
        for idx in range(measure_start, end + 1):
            measure = part.measures[idx - 1]
            for voice in measure.voices:
                for event in voice.events:
                    if isinstance(event, Rest):
                        total += 1
    return total


# ---------------------------------------------------------------------------
# MuseScore helpers
# ---------------------------------------------------------------------------

def find_musescore() -> Path | None:
    """Locate MuseScore 4 executable, mirroring src/qa/render_qa.py logic."""
    candidates = [
        Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
        Path(r"D:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
        Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
    ]
    env = os.getenv("MUSESCORE_EXE")
    if env:
        candidates.insert(0, Path(env))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def musescore_can_import(musicxml_path: Path, timeout: int = 300) -> tuple[bool, str]:
    """Try to import a MusicXML file with MuseScore and return (ok, message)."""
    exe = find_musescore()
    if exe is None:
        return False, "MuseScore not found"

    output = musicxml_path.with_suffix(".mscz")
    if output.exists():
        output.unlink()

    cmd = [str(exe), "-o", str(output), str(musicxml_path)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return False, f"MuseScore import timed out after {timeout}s"
    except Exception as exc:
        return False, f"MuseScore import failed: {exc}"

    ok = proc.returncode == 0 and output.exists() and output.stat().st_size > 0
    if not ok:
        stderr = proc.stderr.decode("utf-8", errors="replace")[:500]
        return False, f"MuseScore exit={proc.returncode}, stderr={stderr}"
    return True, f"MuseScore imported to {output}"
