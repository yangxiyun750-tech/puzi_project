"""Synthetic regression tests for MusicXMLImporter voice / cursor semantics.

All fixtures are generated in code. No real score, fixed measure number, part
ID, voice ID, staff ID, or filename is referenced. These tests protect the
correct handling of <forward>, <backup>, <voice>, <staff>, <chord/> and
divisions in multi-voice / multi-staff measures.
"""

from __future__ import annotations

import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from score_engine.musicxml import MusicXMLExporter, MusicXMLImporter
from score_engine.score_ir import Note, Rest, Score


_EPSILON = Fraction(1, 128)


def make_score(part_content: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1">
      <part-name>Test Part</part-name>
    </score-part>
  </part-list>
  <part id="P1">
{part_content}
  </part>
</score-partwise>
"""


def make_measure(
    number: int,
    content: str,
    divisions: int = 1,
    beats: int = 4,
    beat_type: int = 4,
) -> str:
    return f"""    <measure number="{number}">
      <attributes>
        <divisions>{divisions}</divisions>
        <time>
          <beats>{beats}</beats>
          <beat-type>{beat_type}</beat-type>
        </time>
        <clef>
          <sign>G</sign>
          <line>2</line>
        </clef>
      </attributes>
{content}
    </measure>"""


def make_note(
    duration: int,
    voice: int = 1,
    staff: int = 1,
    pitch_step: str = "C",
    pitch_octave: int = 4,
    chord: bool = False,
    type_name: str = "quarter",
) -> str:
    chord_tag = "      <chord/>\n" if chord else ""
    return f"""      <note>
{chord_tag}      <pitch>
        <step>{pitch_step}</step>
        <octave>{pitch_octave}</octave>
      </pitch>
      <duration>{duration}</duration>
      <voice>{voice}</voice>
      <staff>{staff}</staff>
      <type>{type_name}</type>
    </note>"""


def make_rest(duration: int, voice: int = 1, staff: int = 1, type_name: str = "quarter") -> str:
    return f"""      <note>
      <rest/>
      <duration>{duration}</duration>
      <voice>{voice}</voice>
      <staff>{staff}</staff>
      <type>{type_name}</type>
    </note>"""


def make_forward(duration: int, voice: int | None = None, staff: int = 1) -> str:
    voice_tag = f"      <voice>{voice}</voice>\n" if voice is not None else ""
    return f"""      <forward>
      <duration>{duration}</duration>
{voice_tag}      <staff>{staff}</staff>
    </forward>"""


def make_backup(duration: int) -> str:
    return f"""      <backup>
      <duration>{duration}</duration>
    </backup>"""


def import_xml(xml: str) -> Score:
    importer = MusicXMLImporter()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".musicxml", delete=False) as f:
        f.write(xml)
        path = Path(f.name)
    try:
        return importer.import_file(path)
    finally:
        path.unlink()


def voice_durations(score: Score) -> dict[str, Fraction]:
    result: dict[str, Fraction] = {}
    for part in score.parts:
        for measure in part.measures:
            for voice in measure.voices:
                result[f"M{measure.number}-{voice.id}"] = voice.total_duration
    return result


def assert_no_new_overflow(score: Score, expected: Fraction = Fraction(4)) -> None:
    for part in score.parts:
        for measure in part.measures:
            if measure.implicit:
                continue
            exp = measure.time_signature.quarters_per_measure if measure.time_signature else expected
            for voice in measure.voices:
                assert voice.total_duration <= exp + _EPSILON, (
                    f"{part.id} M{measure.number} {voice.id}: "
                    f"{voice.total_duration} > {exp}"
                )


def roundtrip(score: Score) -> Score:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "roundtrip.musicxml"
        MusicXMLExporter().export_file(score, path)
        return MusicXMLImporter().import_file(path)


class TestSingleVoiceForward(unittest.TestCase):
    """1. single voice + forward"""

    def test_forward_becomes_rest_in_default_voice(self):
        xml = make_score(make_measure(1, make_note(2) + make_forward(2)))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(len(m.voices), 1)
        self.assertEqual(m.voices[0].id, "P1-V1")
        self.assertEqual(m.voices[0].total_duration, Fraction(4))
        events = m.voices[0].events
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], Note)
        self.assertIsInstance(events[1], Rest)
        assert_no_new_overflow(score)


class TestTwoVoicesBackup(unittest.TestCase):
    """2. two voices + backup"""

    def test_backup_isolates_voice_cursors(self):
        xml = make_score(make_measure(
            1,
            make_note(4, voice=1) + make_backup(4) + make_note(4, voice=2),
        ))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(len(m.voices), 2)
        dur = voice_durations(score)
        self.assertEqual(dur["M1-P1-V1"], Fraction(4))
        self.assertEqual(dur["M1-P1-V2"], Fraction(4))
        assert_no_new_overflow(score)


class TestTwoVoicesBackupForward(unittest.TestCase):
    """3. two voices + backup + forward"""

    def test_forward_after_backup_targets_correct_voice(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1)
            + make_backup(2)
            + make_forward(2, voice=2)
            + make_note(2, voice=2),
        ))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(len(m.voices), 2)
        v1 = next(v for v in m.voices if v.id == "P1-V1")
        v2 = next(v for v in m.voices if v.id == "P1-V2")
        self.assertEqual(v1.total_duration, Fraction(2))
        self.assertEqual(v2.total_duration, Fraction(4))
        self.assertTrue(any(isinstance(e, Rest) for e in v2.events))
        self.assertFalse(any(isinstance(e, Rest) for e in v1.events))
        assert_no_new_overflow(score)


class TestSameStaffMultipleVoices(unittest.TestCase):
    """4. same staff / multiple voices"""

    def test_same_staff_voices_keep_independent_durations(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1, staff=1)
            + make_note(2, voice=2, staff=1)
            + make_backup(2)
            + make_note(2, voice=2, staff=1),
        ))
        score = import_xml(xml)
        dur = voice_durations(score)
        self.assertEqual(dur["M1-P1-V1"], Fraction(2))
        self.assertEqual(dur["M1-P1-V2"], Fraction(4))
        assert_no_new_overflow(score)


class TestMultipleStavesMultipleVoices(unittest.TestCase):
    """5. multiple staves / multiple voices"""

    def test_staff_switching_preserves_voice_cursor(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1, staff=1)
            + make_backup(2)
            + make_note(2, voice=1, staff=2)
            + make_backup(2)
            + make_note(2, voice=2, staff=2)
            + make_backup(2)
            + make_note(2, voice=2, staff=1),
        ))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(len(m.voices), 2)
        dur = voice_durations(score)
        self.assertEqual(dur["M1-P1-V1"], Fraction(4))
        self.assertEqual(dur["M1-P1-V2"], Fraction(4))
        for v in m.voices:
            for e in v.events:
                self.assertIn(e.staff, (1, 2))
        assert_no_new_overflow(score)


class TestForwardBeforeVoiceSwitch(unittest.TestCase):
    """6. forward before voice switch"""

    def test_forward_belongs_to_current_voice_not_next(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1)
            + make_forward(2, voice=1)
            + make_backup(4)
            + make_note(4, voice=2),
        ))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        v1 = next(v for v in m.voices if v.id == "P1-V1")
        v2 = next(v for v in m.voices if v.id == "P1-V2")
        self.assertEqual(v1.total_duration, Fraction(4))
        self.assertEqual(v2.total_duration, Fraction(4))
        self.assertTrue(any(isinstance(e, Rest) for e in v1.events))
        assert_no_new_overflow(score)


class TestForwardAfterBackup(unittest.TestCase):
    """7. forward after backup"""

    def test_forward_after_backup_targets_backed_up_voice(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1)
            + make_backup(2)
            + make_forward(1)
            + make_note(1, voice=1),
        ))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(len(m.voices), 1)
        self.assertEqual(m.voices[0].total_duration, Fraction(4))
        events = m.voices[0].events
        self.assertIsInstance(events[1], Rest)
        assert_no_new_overflow(score)


class TestChordPlusForward(unittest.TestCase):
    """8. chord + forward"""

    def test_chord_does_not_advance_cursor_before_forward(self):
        chord = make_note(2, voice=1) + make_note(2, voice=1, pitch_step="E", chord=True)
        xml = make_score(make_measure(1, chord + make_forward(2)))
        score = import_xml(xml)
        m = score.parts[0].measures[0]
        self.assertEqual(m.voices[0].total_duration, Fraction(4))
        events = m.voices[0].events
        self.assertEqual(len(events), 3)  # chord root + chord tone + rest
        self.assertFalse(events[0].is_chord_tone)
        self.assertTrue(events[1].is_chord_tone)
        self.assertIsInstance(events[2], Rest)
        assert_no_new_overflow(score)


class TestExplicitRestPlusBackup(unittest.TestCase):
    """9. explicit rest + backup"""

    def test_rest_advances_cursor_and_backup_works(self):
        xml = make_score(make_measure(
            1,
            make_rest(3, voice=1)
            + make_backup(3)
            + make_note(1, voice=2)
            + make_note(3, voice=2),
        ))
        score = import_xml(xml)
        dur = voice_durations(score)
        self.assertEqual(dur["M1-P1-V1"], Fraction(3))
        self.assertEqual(dur["M1-P1-V2"], Fraction(4))
        assert_no_new_overflow(score)


class TestDivisionsGreaterThanOneMultiVoice(unittest.TestCase):
    """10. divisions > 1 multi-voice"""

    def test_divisions_changes_preserved_across_voices(self):
        # divisions=2: quarter = duration 2, half = duration 4, whole = duration 8
        xml = make_score(make_measure(
            1,
            make_note(8, voice=1, type_name="whole")
            + make_backup(8)
            + make_note(2, voice=2, type_name="quarter")
            + make_note(2, voice=2, type_name="quarter")
            + make_note(2, voice=2, type_name="quarter")
            + make_note(2, voice=2, type_name="quarter"),
            divisions=2,
        ))
        score = import_xml(xml)
        dur = voice_durations(score)
        self.assertEqual(dur["M1-P1-V1"], Fraction(4))
        self.assertEqual(dur["M1-P1-V2"], Fraction(4))
        assert_no_new_overflow(score)


class TestRoundtripStability(unittest.TestCase):
    """Round-trip verification for voice-cursor fixtures."""

    def test_two_voices_backup_forward_roundtrip(self):
        xml = make_score(make_measure(
            1,
            make_note(2, voice=1)
            + make_backup(2)
            + make_forward(2, voice=2)
            + make_note(2, voice=2),
        ))
        original = import_xml(xml)
        reimported = roundtrip(original)
        orig_dur = voice_durations(original)
        reimp_dur = voice_durations(reimported)
        self.assertEqual(orig_dur, reimp_dur)
        assert_no_new_overflow(reimported)


if __name__ == "__main__":
    unittest.main()
