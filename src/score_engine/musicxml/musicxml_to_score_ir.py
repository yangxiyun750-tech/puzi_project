"""MusicXML → ScoreIR importer (V1.1).

Fixes over V1:
- Tracks <divisions> per measure and stores it in Duration objects
- Chord-tone durations are kept as-is (not zeroed; downstream consumer decides)
- Parses tuplet, fermata, arpeggio
- Parses both <tie> (sound) and <tied> (notation)
- Backup/forward tracking: maintains per-voice time offsets so multi-voice
  measures are reconstructed correctly
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from score_engine.score_ir.score_ir import (
    Articulation,
    Clef,
    Duration,
    Dynamic,
    EditHistory,
    Instrument,
    InstrumentTransposition,
    KeySignature,
    Lyric,
    Measure,
    Note,
    Part,
    Pitch,
    RepairIssue,
    RepairLog,
    RepairType,
    Rest,
    Score,
    Slur,
    Staff,
    Tempo,
    Tie,
    TimeSignature,
    Voice,
    make_measure_id,
    make_note_id,
    make_part_id,
    make_staff_id,
    make_voice_id,
)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class MusicXMLImporter:
    """Import MusicXML score-partwise into ScoreIR."""

    def __init__(self) -> None:
        self.repair_log = RepairLog()

    def import_file(self, path: str | Path) -> Score:
        tree = ET.parse(path)
        return self.import_tree(tree)

    def import_tree(self, tree: ET.ElementTree) -> Score:
        root = tree.getroot()
        if root.tag not in ("score-partwise", "{http://www.musicxml.org/xsd/musicxml.xsd}score-partwise"):
            raise ValueError(f"Unsupported MusicXML root: {root.tag}")

        score = Score()
        score.title = self._extract_title(root)

        part_list = root.find("part-list")
        if part_list is None:
            raise ValueError("No part-list found")

        part_names: dict[str, str] = {}
        for score_part in part_list.findall("score-part"):
            pid = score_part.get("id", "")
            name = score_part.findtext("part-name", pid)
            part_names[pid] = name

        for idx, part_elem in enumerate(root.findall("part"), start=1):
            part = self._import_part(part_elem, part_names, idx)
            score.parts.append(part)

        return score

    def _extract_title(self, root: ET.Element) -> str:
        work = root.find("work")
        if work is not None:
            return work.findtext("work-title", "")
        credit = root.find("credit")
        if credit is not None:
            return credit.findtext("credit-words", "")
        return ""

    def _import_part(self, elem: ET.Element, part_names: dict[str, str], index: int) -> Part:
        part_id = elem.get("id", f"P{index}")
        part = Part(
            id=part_id,
            name=part_names.get(part_id, part_id),
            abbreviation="",
        )

        # Divisions are inherited across measures within a part
        current_divisions = 1
        for measure_elem in elem.findall("measure"):
            measure = self._import_measure(measure_elem, part, current_divisions)
            # Track divisions changes for inheritance
            div_elem = measure_elem.find("attributes/divisions")
            if div_elem is not None and div_elem.text:
                current_divisions = int(div_elem.text)
            part.measures.append(measure)

        return part

    def _import_measure(self, elem: ET.Element, part: Part, current_divisions: int) -> Measure:
        part_id = part.id
        number = elem.get("number", "0")
        measure = Measure(
            id=make_measure_id(part_id, number),
            number=number,
            implicit=elem.get("implicit", "no").lower() == "yes",
            divisions=current_divisions,
        )

        # Per-voice state: {voice_str: {"events": [...], "time": Fraction, "index": int}}
        voice_states: dict[str, dict] = {}

        # MusicXML measures are sequential. At any point there is a single
        # "current voice" whose cursor is being manipulated by backup/forward.
        # It is the voice of the most recent non-chord, non-grace note/rest.
        current_voice = "1"

        def _get_voice(v: str) -> dict:
            if v not in voice_states:
                voice_states[v] = {"events": [], "time": Fraction(0), "index": 0}
            return voice_states[v]

        def _expected_duration() -> Fraction:
            return (
                measure.time_signature.quarters_per_measure
                if measure.time_signature
                else Fraction(4)
            )

        for child in elem:
            tag = _local(child.tag)

            if tag == "attributes":
                self._import_attributes(child, measure)
                # Import transposition metadata if present
                self._import_transpose(child, part, measure)
                # Update divisions from measure attributes
                div_elem = child.find("divisions")
                if div_elem is not None and div_elem.text:
                    current_divisions = int(div_elem.text)
                measure.divisions = current_divisions
                # Also check key/time/clef inside attributes
                key = child.find("key")
                if key is not None:
                    fifths = key.findtext("fifths", "0")
                    mode = key.findtext("mode", "major")
                    measure.key_signature = KeySignature(int(fifths), mode)
                time = child.find("time")
                if time is not None:
                    beats = time.findtext("beats", "4")
                    beat_type = time.findtext("beat-type", "4")
                    measure.time_signature = TimeSignature(int(beats), int(beat_type))
                for clef_elem in child.findall("clef"):
                    cnum = int(clef_elem.get("number", "1"))
                    sign = clef_elem.findtext("sign", "G")
                    line = int(clef_elem.findtext("line", "2"))
                    measure.clefs[cnum] = Clef(sign, line)

            elif tag == "direction":
                self._import_direction(child, measure)

            elif tag == "note":
                is_chord_tone = child.find("chord") is not None
                is_grace = child.find("grace") is not None
                # A chord tone belongs to the current voice unless the element
                # explicitly says otherwise. Non-chord notes/rests become the
                # new current voice.
                voice_str = child.findtext("voice", current_voice if is_chord_tone else "1")
                if not is_chord_tone and not is_grace:
                    current_voice = voice_str

                vs = _get_voice(voice_str)
                note_index = vs["index"]
                vs["index"] += 1

                note = self._import_note(
                    child,
                    part_id,
                    number,
                    current_divisions,
                    voice=voice_str,
                    index=note_index,
                )
                vs["events"].append(note)

                # Only non-chord, non-grace events consume time in the voice.
                if not is_chord_tone and not is_grace:
                    vs["time"] += note.duration.quarters

            elif tag == "backup":
                dur = int(child.findtext("duration", "0") or 0)
                # Backup moves only the current voice's cursor backward.
                vs = _get_voice(current_voice)
                backup_q = Fraction(dur, current_divisions)
                vs["time"] = max(Fraction(0), vs["time"] - backup_q)

            elif tag == "forward":
                dur = int(child.findtext("duration", "0") or 0)
                # Forward may explicitly specify a voice; otherwise it applies
                # to the current voice (the one whose cursor is active).
                voice_str = child.findtext("voice", current_voice)
                current_voice = voice_str

                vs = _get_voice(current_voice)
                forward_q = Fraction(dur, current_divisions)
                current_total = vs["time"]
                expected = _expected_duration()

                # Create a Rest only when the silent time fits inside the
                # measure. If it would overflow, advance the cursor to record
                # the time but do not invent a rest in the wrong place.
                if dur > 0 and current_total + forward_q <= expected + Fraction(1, 128):
                    rest_id = make_note_id(part_id, number, current_voice, vs["index"])
                    vs["index"] += 1
                    vs["events"].append(
                        Rest(
                            id=rest_id,
                            duration=Duration(current_divisions, dur),
                            voice=current_voice,
                            staff=int(child.findtext("staff", "1")),
                        )
                    )
                vs["time"] += forward_q

            elif tag == "barline":
                measure.barlines.append({
                    "location": child.get("location", "right"),
                    "style": child.findtext("bar-style", ""),
                })

        # Build Voice objects from collected events
        for vnum_str, state in sorted(voice_states.items()):
            voice = Voice(id=make_voice_id(part_id, vnum_str))
            voice.events = state["events"]
            measure.voices.append(voice)

        return measure

    def _import_note(
        self,
        elem: ET.Element,
        part_id: str,
        measure_num: str,
        divisions: int,
        voice: str,
        index: int,
    ) -> Note:
        note_id = make_note_id(part_id, measure_num, voice, index)
        staff = int(elem.findtext("staff", "1"))
        note_type = elem.findtext("type", "quarter")
        dots = len(elem.findall("dot"))
        is_chord_tone = elem.find("chord") is not None
        is_grace = elem.find("grace") is not None

        # Duration
        duration_text = elem.findtext("duration", "1")
        duration_val = int(duration_text) if duration_text else 1
        duration = Duration(divisions=divisions, value=duration_val)

        # Pitch or rest
        pitch = None
        pitch_elem = elem.find("pitch")
        if pitch_elem is not None:
            step = pitch_elem.findtext("step", "C")
            alter_text = pitch_elem.findtext("alter", "0")
            alter = int(alter_text) if alter_text else 0
            octave = int(pitch_elem.findtext("octave", "4"))
            pitch = Pitch(step, alter, octave)

        note = Note(
            id=note_id,
            pitch=pitch,
            duration=duration,
            voice=voice,
            staff=staff,
            type=note_type,
            dots=dots,
            is_chord_tone=is_chord_tone,
            is_grace=is_grace,
        )

        # <tie> outside <notations> (sound element)
        for tie_elem in elem.findall("tie"):
            note.ties.append(Tie(tie_elem.get("type", ""), int(tie_elem.get("number", "1"))))

        # Notations
        notations = elem.find("notations")
        if notations is not None:
            for child in notations:
                tag = _local(child.tag)
                if tag == "tied":
                    note.ties.append(Tie(child.get("type", ""), int(child.get("number", "1"))))
                elif tag == "slur":
                    note.slurs.append(Slur(
                        child.get("type", ""),
                        int(child.get("number", "1")),
                        child.get("placement", ""),
                    ))
                elif tag == "articulations":
                    for art in child:
                        art_tag = _local(art.tag)
                        note.articulations.append(Articulation(art_tag))
                elif tag == "tuplet":
                    note.tuplet = child.get("type", "")
                elif tag == "fermata":
                    note.fermata = True
                elif tag == "arpeggiate":
                    note.arpeggiate = True

        # Lyric
        for lyric_elem in elem.findall("lyric"):
            lyric = Lyric(
                number=lyric_elem.get("number", "1"),
                syllabic=lyric_elem.findtext("syllabic", "single"),
                text=lyric_elem.findtext("text", ""),
                extend_type=(lyric_elem.find("extend") is not None and
                             lyric_elem.find("extend").get("type") or None),
            )
            note.lyrics.append(lyric)

        return note

    def _import_attributes(self, elem: ET.Element, measure: Measure) -> None:
        # Key signature
        key = elem.find("key")
        if key is not None:
            fifths = key.findtext("fifths", "0")
            mode = key.findtext("mode", "major")
            measure.key_signature = KeySignature(int(fifths), mode)

        # Time signature
        time = elem.find("time")
        if time is not None:
            beats = time.findtext("beats", "4")
            beat_type = time.findtext("beat-type", "4")
            measure.time_signature = TimeSignature(int(beats), int(beat_type))

        # Divisions
        div = elem.find("divisions")
        if div is not None and div.text:
            measure.divisions = int(div.text)

        # Clefs
        for clef_elem in elem.findall("clef"):
            number = int(clef_elem.get("number", "1"))
            sign = clef_elem.findtext("sign", "G")
            line = int(clef_elem.findtext("line", "2"))
            measure.clefs[number] = Clef(sign, line)

    def _import_transpose(self, elem: ET.Element, part: Part, measure: Measure) -> None:
        """Read MusicXML <transpose> and record transposition metadata.

        V1 records metadata and flags unsupported cases:
        - per-staff <transpose number="...">
        - <double/> transposition
        - mid-part changes to a different transposition
        """
        transpose_elems = elem.findall("transpose")
        if not transpose_elems:
            return

        for tx in transpose_elems:
            staff_attr = tx.get("number", "")
            diatonic = int(tx.findtext("diatonic", "0") or 0)
            chromatic = int(tx.findtext("chromatic", "0") or 0)
            octave_change = int(tx.findtext("octave-change", "0") or 0)
            has_double = tx.find("double") is not None

            event = {
                "measure": measure.number,
                "diatonic": diatonic,
                "chromatic": chromatic,
                "octave_change": octave_change,
                "staff_specific": bool(staff_attr),
                "double": has_double,
            }
            part.transposition_events.append(event)

            if staff_attr or has_double:
                # V1 unsupported: per-staff or double transposition.
                part.has_variable_transposition = True
                continue

            current = part.instrument.transposition
            if current.diatonic == 0 and current.chromatic == 0 and current.octave_change == 0:
                # First transposition metadata for this part.
                part.instrument.transposition = InstrumentTransposition(
                    diatonic=diatonic,
                    chromatic=chromatic,
                    octave_change=octave_change,
                )
                part.instrument.transposition_chromatic = chromatic
                part.instrument.transposition_octave = octave_change
            elif (
                current.diatonic != diatonic
                or current.chromatic != chromatic
                or current.octave_change != octave_change
            ):
                # Mid-part change to a different transposition.
                part.has_variable_transposition = True

    def _import_direction(self, elem: ET.Element, measure: Measure) -> None:
        direction_type = elem.find("direction-type")
        if direction_type is None:
            return

        metronome = direction_type.find("metronome")
        if metronome is not None:
            beat_unit = metronome.findtext("beat-unit", "quarter")
            per_minute = metronome.findtext("per-minute", "120")
            measure.tempo = Tempo(beat_unit, int(per_minute))

        dynamics = direction_type.find("dynamics")
        if dynamics is not None:
            for child in dynamics:
                mark = _local(child.tag)
                measure.dynamics.append(Dynamic(mark))


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------


def test_import() -> None:
    path = Path("D:/puzi_project/colores_test/baseline/colores_audiveris_raw.musicxml")
    if not path.exists():
        print(f"SKIP: {path} not found")
        return

    importer = MusicXMLImporter()
    score = importer.import_file(path)

    print(f"Title: {score.title}")
    print(f"Parts: {len(score.parts)}")
    for part in score.parts:
        print(f"  {part.id}: {part.name} — {len(part.measures)} measures")
        if part.measures:
            m = part.measures[0]
            print(f"    M1: {len(m.voices)} voices, key={m.key_signature}, time={m.time_signature}, divisions={m.divisions}")


if __name__ == "__main__":
    test_import()
