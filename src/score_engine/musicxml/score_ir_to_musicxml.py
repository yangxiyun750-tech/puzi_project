"""ScoreIR → MusicXML exporter (V1.1).

Fixes over V1:
- Outputs the correct <divisions> value stored in each Measure
- Exports tuplet, fermata, arpeggio
- Exports both <tie> (sound) and <tied> (notation) for compatibility
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from score_engine.score_ir.score_ir import (
    Articulation,
    Chord,
    Clef,
    Dynamic,
    KeySignature,
    Lyric,
    Measure,
    Note,
    Rest,
    Score,
    Slur,
    Tempo,
    Tie,
    TimeSignature,
)


def _add_child(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    e = ET.SubElement(parent, tag)
    if text:
        e.text = text
    return e


class MusicXMLExporter:
    """Export ScoreIR to MusicXML score-partwise."""

    def export(self, score: Score) -> ET.ElementTree:
        root = ET.Element("score-partwise", version="4.0")

        # Part list
        part_list = ET.SubElement(root, "part-list")
        for part in score.parts:
            score_part = ET.SubElement(part_list, "score-part", id=part.id)
            _add_child(score_part, "part-name", part.name)

        # Parts
        for part in score.parts:
            part_elem = ET.SubElement(root, "part", id=part.id)
            for measure in part.measures:
                self._export_measure(measure, part_elem)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        return tree

    def export_file(self, score: Score, path: str | Path) -> None:
        tree = self.export(score)
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def _export_measure(self, measure: Measure, elem: ET.Element) -> None:
        meas = ET.SubElement(elem, "measure", number=measure.number)
        if measure.implicit:
            meas.set("implicit", "yes")

        # Attributes
        attrs = ET.SubElement(meas, "attributes")

        if measure.divisions != 1:
            ET.SubElement(attrs, "divisions").text = str(measure.divisions)

        if measure.key_signature:
            key = ET.SubElement(attrs, "key")
            ET.SubElement(key, "fifths").text = str(measure.key_signature.fifths)
            if measure.key_signature.mode != "major":
                ET.SubElement(key, "mode").text = measure.key_signature.mode

        if measure.time_signature:
            time = ET.SubElement(attrs, "time")
            ET.SubElement(time, "beats").text = str(measure.time_signature.beats)
            ET.SubElement(time, "beat-type").text = str(measure.time_signature.beat_type)

        for staff_num, clef in sorted(measure.clefs.items()):
            clef_elem = ET.SubElement(attrs, "clef", number=str(staff_num))
            ET.SubElement(clef_elem, "sign").text = clef.sign
            if clef.line:
                ET.SubElement(clef_elem, "line").text = str(clef.line)

        # Directions (tempo, dynamics)
        if measure.tempo:
            direction = ET.SubElement(meas, "direction", placement="above")
            direction_type = ET.SubElement(direction, "direction-type")
            metronome = ET.SubElement(direction_type, "metronome", parentheses="no")
            ET.SubElement(metronome, "beat-unit").text = measure.tempo.beat_unit
            ET.SubElement(metronome, "per-minute").text = str(measure.tempo.per_minute)
            ET.SubElement(direction, "sound", tempo=str(measure.tempo.per_minute))

        if measure.dynamics:
            direction = ET.SubElement(meas, "direction", placement="below")
            direction_type = ET.SubElement(direction, "direction-type")
            dynamics_elem = ET.SubElement(direction_type, "dynamics")
            for dyn in measure.dynamics:
                ET.SubElement(dynamics_elem, dyn.mark)

        # Voices
        for voice in measure.voices:
            for event in voice.events:
                if isinstance(event, Chord):
                    self._export_chord(event, meas)
                elif isinstance(event, Rest):
                    self._export_rest(event, meas)
                elif isinstance(event, Note):
                    self._export_note(event, meas)

        # Barlines
        for barline_info in measure.barlines:
            barline = ET.SubElement(meas, "barline", location=barline_info.get("location", "right"))
            if barline_info.get("style"):
                ET.SubElement(barline, "bar-style").text = barline_info["style"]

    def _export_note(self, note: Note, elem: ET.Element) -> None:
        note_elem = ET.SubElement(elem, "note")
        if note.is_chord_tone:
            ET.SubElement(note_elem, "chord")
        if note.pitch is not None:
            pitch = ET.SubElement(note_elem, "pitch")
            ET.SubElement(pitch, "step").text = note.pitch.step
            if note.pitch.alter:
                ET.SubElement(pitch, "alter").text = str(note.pitch.alter)
            ET.SubElement(pitch, "octave").text = str(note.pitch.octave)
        else:
            ET.SubElement(note_elem, "rest")

        ET.SubElement(note_elem, "duration").text = str(note.duration.value)
        ET.SubElement(note_elem, "voice").text = note.voice
        ET.SubElement(note_elem, "type").text = note.type
        if note.dots:
            for _ in range(note.dots):
                ET.SubElement(note_elem, "dot")
        if note.staff > 1:
            ET.SubElement(note_elem, "staff").text = str(note.staff)

        # Tie sound element (outside notations)
        for tie in note.ties:
            ET.SubElement(note_elem, "tie", type=tie.type, number=str(tie.number))

        # Notations
        notations_elem = None

        # Tied notation elements
        for tie in note.ties:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            ET.SubElement(notations_elem, "tied", type=tie.type, number=str(tie.number))

        for slur in note.slurs:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            attrs = {"type": slur.type, "number": str(slur.number)}
            if slur.placement:
                attrs["placement"] = slur.placement
            ET.SubElement(notations_elem, "slur", **attrs)

        for art in note.articulations:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            articulations = notations_elem.find("articulations")
            if articulations is None:
                articulations = ET.SubElement(notations_elem, "articulations")
            ET.SubElement(articulations, art.mark)

        if note.tuplet:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            ET.SubElement(notations_elem, "tuplet", type=note.tuplet, number="1")

        if note.fermata:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            ET.SubElement(notations_elem, "fermata")

        if note.arpeggiate:
            if notations_elem is None:
                notations_elem = ET.SubElement(note_elem, "notations")
            ET.SubElement(notations_elem, "arpeggiate")

        # Lyrics
        for lyric in note.lyrics:
            lyric_elem = ET.SubElement(note_elem, "lyric", number=lyric.number)
            ET.SubElement(lyric_elem, "syllabic").text = lyric.syllabic
            ET.SubElement(lyric_elem, "text").text = lyric.text
            if lyric.extend_type:
                ET.SubElement(lyric_elem, "extend", type=lyric.extend_type)

    def _export_rest(self, rest: Rest, elem: ET.Element) -> None:
        note_elem = ET.SubElement(elem, "note")
        rest_elem = ET.SubElement(note_elem, "rest")
        if rest.display_step and rest.display_octave:
            ET.SubElement(rest_elem, "display-step").text = rest.display_step
            ET.SubElement(rest_elem, "display-octave").text = str(rest.display_octave)
        ET.SubElement(note_elem, "duration").text = str(rest.duration.value)
        ET.SubElement(note_elem, "voice").text = rest.voice
        ET.SubElement(note_elem, "type").text = rest.type
        if rest.dots:
            for _ in range(rest.dots):
                ET.SubElement(note_elem, "dot")

    def _export_chord(self, chord, elem: ET.Element) -> None:
        for idx, note in enumerate(chord.notes):
            note.is_chord_tone = (idx > 0)
            self._export_note(note, elem)
