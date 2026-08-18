"""Deterministic Transposition Engine V1 tests.

Run with:
    PYTHONPATH=src python -m unittest tests.test_transposition -v
"""

from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from score_engine.score_ir import (
    Chord,
    Duration,
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
from score_engine.musicxml import MusicXMLImporter, MusicXMLExporter
from score_engine.transposition import (
    Interval,
    SafeTranspositionService,
    SpellingError,
    TranspositionEngine,
    TranspositionOperation,
    TransposeRequest,
)
from score_engine.transposition.instrument_map import (
    lookup_instrument_transposition,
    resolve_part_transposition,
    transposition_to_interval,
)
from score_engine.transposition.pitch_spelling import spelling_summary


try:
    from omr_normalization.issue_model import (
        OMREditSafety,
        OMRIssue,
        OMRNormalizationReport,
        OMRStatus,
    )
    from omr_normalization.quality_gate import OMRGateMode, OMRQualityGate
    _HAS_GATE = True
except Exception:  # pragma: no cover
    _HAS_GATE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_score_with_note(
    pitch: Pitch,
    key: KeySignature | None = None,
    part_name: str = "Test",
    part_id: str = "P1",
) -> Score:
    """Build a minimal single-note ScoreIR score."""
    score = Score(title="fixture")
    part = Part(id=part_id, name=part_name)
    measure = Measure(
        id=f"{part_id}-M1",
        number="1",
        key_signature=key,
        time_signature=None,
    )
    voice = Voice(id=f"{part_id}-V1")
    note = Note(
        id=f"{part_id}-M1-V1-N00",
        pitch=pitch,
        duration=Duration(1, 1),
        voice="1",
    )
    voice.events.append(note)
    measure.voices.append(voice)
    part.measures.append(measure)
    score.parts.append(part)
    return score


def make_musicxml(transpose_xml: str = "") -> str:
    """Return a minimal score-partwise MusicXML string."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Test</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        {transpose_xml}
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration>
        <voice>1</voice>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""


def import_xml_string(xml: str) -> Score:
    """Import a MusicXML string into ScoreIR."""
    tree = ET.ElementTree(ET.fromstring(xml))
    return MusicXMLImporter().import_tree(tree)


# ---------------------------------------------------------------------------
# Interval
# ---------------------------------------------------------------------------

class TestInterval(unittest.TestCase):
    """Named interval construction and arithmetic."""

    def test_major_third_semitones(self):
        self.assertEqual(Interval(3, "M").semitones, 4)

    def test_minor_third_semitones(self):
        self.assertEqual(Interval(3, "m").semitones, 3)

    def test_perfect_fifth_semitones(self):
        self.assertEqual(Interval(5, "P").semitones, 7)

    def test_perfect_octave_semitones(self):
        self.assertEqual(Interval(8, "P").semitones, 12)

    def test_compound_major_ninth_semitones(self):
        self.assertEqual(Interval(9, "M").semitones, 14)

    def test_compound_minor_tenth_semitones(self):
        self.assertEqual(Interval(10, "m").semitones, 15)

    def test_descending_interval(self):
        self.assertEqual(Interval(3, "M", -1).semitones, 4)

    def test_reject_augmented_quality(self):
        with self.assertRaises(ValueError):
            Interval(5, "A")

    def test_reject_diminished_quality(self):
        with self.assertRaises(ValueError):
            Interval(5, "d")

    def test_reject_major_quality_on_perfect_interval(self):
        with self.assertRaises(ValueError):
            Interval(4, "M")

    def test_reject_perfect_quality_on_major_interval(self):
        with self.assertRaises(ValueError):
            Interval(3, "P")

    def test_reject_invalid_number(self):
        with self.assertRaises(ValueError):
            Interval(0, "P")

    def test_reject_invalid_direction(self):
        with self.assertRaises(ValueError):
            Interval(3, "M", 2)

    def test_apply_major_third_up(self):
        self.assertEqual(Interval(3, "M").apply(Pitch("C", 0, 4)), Pitch("E", 0, 4))

    def test_apply_minor_third_down(self):
        self.assertEqual(Interval(3, "m", -1).apply(Pitch("C", 0, 4)), Pitch("A", 0, 3))

    def test_apply_compound_ninth_up(self):
        self.assertEqual(Interval(9, "M").apply(Pitch("C", 0, 4)), Pitch("D", 0, 5))

    def test_apply_b_major_second_up(self):
        self.assertEqual(Interval(2, "M").apply(Pitch("B", 0, 3)), Pitch("C", 1, 4))

    def test_inverted_interval(self):
        inv = Interval(3, "M", 1).inverted()
        self.assertEqual(inv.number, 3)
        self.assertEqual(inv.quality, "M")
        self.assertEqual(inv.direction, -1)


# ---------------------------------------------------------------------------
# Pitch spelling
# ---------------------------------------------------------------------------

class TestPitchSpelling(unittest.TestCase):
    """Immutable diatonic spelling."""

    def test_c_major_third_up(self):
        self.assertEqual(spelling_summary(Pitch("C", 0, 4), Interval(3, "M"))["target"], Pitch("E", 0, 4))

    def test_c_minor_third_down(self):
        self.assertEqual(spelling_summary(Pitch("C", 0, 4), Interval(3, "m", -1))["target"], Pitch("A", 0, 3))

    def test_compound_interval_spelling(self):
        self.assertEqual(spelling_summary(Pitch("C", 0, 4), Interval(9, "M"))["target"], Pitch("D", 0, 5))

    def test_no_enharmonic_override(self):
        # M3 from C must be E, never Fb.
        target = spelling_summary(Pitch("C", 0, 4), Interval(3, "M"))["target"]
        self.assertEqual(target.step, "E")

    def test_out_of_bound_spelling_raises(self):
        # B##3 + M2 requires C###4 (alter=3), outside V1 range.
        with self.assertRaises(SpellingError):
            Interval(2, "M").apply(Pitch("B", 2, 3))


# ---------------------------------------------------------------------------
# Instrument transposition mapping
# ---------------------------------------------------------------------------

class TestInstrumentMap(unittest.TestCase):
    """Instrument name → transposition and provenance resolution."""

    def test_lookup_bb_trumpet(self):
        t = lookup_instrument_transposition("Bb Trumpet")
        self.assertEqual(t, InstrumentTransposition(-1, -2, 0))

    def test_lookup_alto_sax(self):
        t = lookup_instrument_transposition("Eb Alto Saxophone")
        self.assertEqual(t, InstrumentTransposition(-5, -9, 0))

    def test_lookup_f_horn(self):
        t = lookup_instrument_transposition("F Horn")
        self.assertEqual(t, InstrumentTransposition(-4, -7, 0))

    def test_lookup_unknown(self):
        self.assertIsNone(lookup_instrument_transposition("Ondes Martenot"))

    def test_resolve_musicxml_provenance(self):
        part = Part(id="P1", name="Unknown")
        part.instrument.transposition = InstrumentTransposition(-1, -2, 0)
        part.transposition_events.append({"diatonic": -1, "chromatic": -2})
        resolved = resolve_part_transposition(part)
        self.assertEqual(resolved.provenance, "musicxml")
        self.assertTrue(resolved.supported)

    def test_resolve_identity_provenance(self):
        part = Part(id="P1", name="Trumpet")
        resolved = resolve_part_transposition(part)
        self.assertEqual(resolved.provenance, "identity")
        self.assertTrue(resolved.supported)

    def test_resolve_unknown_provenance(self):
        part = Part(id="P1", name="Ondes Martenot")
        resolved = resolve_part_transposition(part)
        self.assertEqual(resolved.provenance, "unknown")
        self.assertTrue(resolved.supported)

    def test_resolve_unsupported_variable(self):
        part = Part(id="P1", name="Test")
        part.has_variable_transposition = True
        part.transposition_events.append({"measure": "1"})
        resolved = resolve_part_transposition(part)
        self.assertFalse(resolved.supported)

    def test_transposition_to_interval_bb_trumpet(self):
        interval = transposition_to_interval(InstrumentTransposition(-1, -2, 0))
        self.assertEqual(str(interval), "-M2")

    def test_transposition_to_interval_alto_sax(self):
        interval = transposition_to_interval(InstrumentTransposition(-5, -9, 0))
        self.assertEqual(str(interval), "-M6")

    def test_transposition_to_interval_f_horn(self):
        interval = transposition_to_interval(InstrumentTransposition(-4, -7, 0))
        self.assertEqual(str(interval), "-P5")


# ---------------------------------------------------------------------------
# MusicXML <transpose> ingestion
# ---------------------------------------------------------------------------

class TestMusicXMLTransposeImport(unittest.TestCase):
    """MusicXMLImporter reads and classifies <transpose> metadata."""

    def test_imports_bb_trumpet_transpose(self):
        xml = make_musicxml(
            '<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>'
        )
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertEqual(part.instrument.transposition, InstrumentTransposition(-1, -2, 0))
        self.assertFalse(part.has_variable_transposition)
        self.assertEqual(len(part.transposition_events), 1)

    def test_imports_alto_sax_transpose(self):
        xml = make_musicxml(
            '<transpose><diatonic>-5</diatonic><chromatic>-9</chromatic></transpose>'
        )
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertEqual(part.instrument.transposition, InstrumentTransposition(-5, -9, 0))

    def test_default_c_instrument_no_transpose(self):
        xml = make_musicxml()
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertEqual(part.instrument.transposition, InstrumentTransposition())
        self.assertFalse(part.has_variable_transposition)
        self.assertEqual(len(part.transposition_events), 0)

    def test_flags_staff_specific_transpose(self):
        xml = make_musicxml(
            '<transpose number="1"><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>'
        )
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertTrue(part.has_variable_transposition)
        self.assertEqual(part.instrument.transposition, InstrumentTransposition())

    def test_flags_double_transpose(self):
        xml = make_musicxml(
            '<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic><double/></transpose>'
        )
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertTrue(part.has_variable_transposition)
        self.assertEqual(part.instrument.transposition, InstrumentTransposition())

    def test_flags_mid_part_change(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions>
        <transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
    </measure>
    <measure number="2">
      <attributes>
        <transpose><diatonic>-5</diatonic><chromatic>-9</chromatic></transpose>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><type>quarter</type></note>
    </measure>
  </part>
</score-partwise>
"""
        score = import_xml_string(xml)
        part = score.parts[0]
        self.assertTrue(part.has_variable_transposition)
        self.assertEqual(len(part.transposition_events), 2)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TestTranspositionEngine(unittest.TestCase):
    """End-to-end transposition engine behavior."""

    def test_relative_interval_whole_score(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("D", 0, 4))

    def test_relative_interval_measure_range(self):
        score = Score(title="range")
        part = Part(id="P1", name="Test")
        for i in range(1, 5):
            m = Measure(id=f"P1-M{i}", number=str(i))
            v = Voice(id=f"P1-V{i}")
            v.events.append(Note(
                id=f"P1-M{i}-V1-N00",
                pitch=Pitch("C", 0, 4),
                duration=Duration(1, 1),
                voice="1",
            ))
            m.voices.append(v)
            part.measures.append(m)
        score.parts.append(part)

        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"), measure_start=2, measure_end=3)
        )
        pitches = [m.voices[0].events[0].pitch for m in result.score.parts[0].measures]
        self.assertEqual(pitches[0], Pitch("C", 0, 4))
        self.assertEqual(pitches[1], Pitch("D", 0, 4))
        self.assertEqual(pitches[2], Pitch("D", 0, 4))
        self.assertEqual(pitches[3], Pitch("C", 0, 4))

    def test_key_signature_transposition(self):
        score = make_score_with_note(Pitch("C", 0, 4), key=KeySignature(0, "major"))
        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        self.assertEqual(
            result.score.parts[0].measures[0].key_signature,
            KeySignature(2, "major"),
        )

    def test_key_signature_restoration(self):
        score = Score(title="restore")
        part = Part(id="P1", name="Test")
        keys = [KeySignature(0, "major"), None, None, KeySignature(1, "major"), None]
        for i, key in enumerate(keys, start=1):
            m = Measure(id=f"P1-M{i}", number=str(i), key_signature=key)
            v = Voice(id=f"P1-V{i}")
            v.events.append(Note(
                id=f"P1-M{i}-V1-N00",
                pitch=Pitch("C", 0, 4),
                duration=Duration(1, 1),
                voice="1",
            ))
            m.voices.append(v)
            part.measures.append(m)
        score.parts.append(part)

        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"), measure_start=2, measure_end=3)
        )
        ms = result.score.parts[0].measures
        self.assertEqual(ms[1].key_signature, KeySignature(2, "major"))
        self.assertEqual(ms[2].key_signature, KeySignature(2, "major"))
        # M4 already has an explicit original key change, so it keeps G major.
        self.assertEqual(ms[3].key_signature, KeySignature(1, "major"))

    def test_no_restoration_at_part_end(self):
        score = Score(title="end")
        part = Part(id="P1", name="Test")
        for i in range(1, 4):
            m = Measure(id=f"P1-M{i}", number=str(i), key_signature=KeySignature(0, "major"))
            v = Voice(id=f"P1-V{i}")
            v.events.append(Note(
                id=f"P1-M{i}-V1-N00",
                pitch=Pitch("C", 0, 4),
                duration=Duration(1, 1),
                voice="1",
            ))
            m.voices.append(v)
            part.measures.append(m)
        score.parts.append(part)

        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"), measure_start=1, measure_end=3)
        )
        ms = result.score.parts[0].measures
        self.assertEqual(ms[-1].key_signature, KeySignature(2, "major"))

    def test_deep_copy_immutability(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        original_note = score.parts[0].measures[0].voices[0].events[0]
        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        self.assertEqual(original_note.pitch, Pitch("C", 0, 4))
        self.assertIsNot(result.score, score)

    def test_written_to_sounding_bb_trumpet(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].instrument.transposition = InstrumentTransposition(-1, -2, 0)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("B", -1, 3))

    def test_written_to_sounding_alto_sax(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].instrument.transposition = InstrumentTransposition(-5, -9, 0)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("E", -1, 3))

    def test_written_to_sounding_f_horn(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].instrument.transposition = InstrumentTransposition(-4, -7, 0)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("F", 0, 3))

    def test_sounding_to_written_bb_trumpet(self):
        score = make_score_with_note(Pitch("B", -1, 3))
        score.parts[0].instrument.transposition = InstrumentTransposition(-1, -2, 0)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.SOUNDING_TO_WRITTEN)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("C", 0, 4))

    def test_octave_change_piccolo(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].instrument.transposition = InstrumentTransposition(0, 0, 1)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("C", 0, 5))

    def test_octave_change_double_bass(self):
        score = make_score_with_note(Pitch("C", 0, 3))
        score.parts[0].instrument.transposition = InstrumentTransposition(0, 0, -1)
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("C", 0, 2))

    def test_unknown_transposition_does_not_block_relative(self):
        score = make_score_with_note(Pitch("C", 0, 4), part_name="Ondes Martenot")
        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("D", 0, 4))
        self.assertEqual(result.report.parts[0].transposition_provenance, "unknown")
        self.assertFalse(result.report.parts[0].sounding_audit_available)

    def test_unsupported_variable_blocks_conversion(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].has_variable_transposition = True
        score.parts[0].transposition_events.append({"measure": "1"})
        result = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("C", 0, 4))
        self.assertTrue(any("Unsupported" in w for w in result.report.parts[0].warnings))

    def test_out_of_bound_spelling_warning(self):
        score = make_score_with_note(Pitch("B", 2, 3))
        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        note = result.score.parts[0].measures[0].voices[0].events[0]
        # Pitch is unchanged because spelling failed.
        self.assertEqual(note.pitch, Pitch("B", 2, 3))
        self.assertTrue(any("SpellingError" in w or "alter" in w for w in result.report.warnings))

    def test_chord_pitches_are_transposed(self):
        score = Score(title="chord")
        part = Part(id="P1", name="Test")
        measure = Measure(id="P1-M1", number="1")
        voice = Voice(id="P1-V1")
        chord = Chord(id="P1-M1-V1-C00", notes=[
            Note(id="P1-M1-V1-N00", pitch=Pitch("C", 0, 4), duration=Duration(1, 1), voice="1"),
            Note(id="P1-M1-V1-N01", pitch=Pitch("E", 0, 4), duration=Duration(1, 1), voice="1", is_chord_tone=True),
            Note(id="P1-M1-V1-N02", pitch=Pitch("G", 0, 4), duration=Duration(1, 1), voice="1", is_chord_tone=True),
        ])
        voice.events.append(chord)
        measure.voices.append(voice)
        part.measures.append(measure)
        score.parts.append(part)

        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        notes = result.score.parts[0].measures[0].voices[0].events[0].notes
        self.assertEqual(notes[0].pitch, Pitch("D", 0, 4))
        self.assertEqual(notes[1].pitch, Pitch("F", 1, 4))
        self.assertEqual(notes[2].pitch, Pitch("A", 0, 4))

    def test_rests_are_unchanged(self):
        score = Score(title="rest")
        part = Part(id="P1", name="Test")
        measure = Measure(id="P1-M1", number="1")
        voice = Voice(id="P1-V1")
        voice.events.append(Rest(id="P1-M1-V1-R00", duration=Duration(1, 1), voice="1"))
        measure.voices.append(voice)
        part.measures.append(measure)
        score.parts.append(part)

        result = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        )
        self.assertIsInstance(result.score.parts[0].measures[0].voices[0].events[0], Rest)


# ---------------------------------------------------------------------------
# SafeTranspositionService
# ---------------------------------------------------------------------------

class TestSafeTranspositionService(unittest.TestCase):
    """OMR Quality Gate integration."""

    def test_no_gate_allows_transpose(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        service = SafeTranspositionService()
        result = service.transpose(score, TransposeRequest(interval=Interval(2, "M")))
        self.assertEqual(result.report.status, "ok")

    @unittest.skipUnless(_HAS_GATE, "OMR gate not available")
    def test_clean_gate_allows_transpose(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        report = OMRNormalizationReport(input_path="x", output_path="x")
        service = SafeTranspositionService()
        result = service.transpose(
            score,
            TransposeRequest(interval=Interval(2, "M")),
            omr_report=report,
            mode=OMRGateMode.STRICT,
        )
        self.assertEqual(result.report.status, "ok")

    @unittest.skipUnless(_HAS_GATE, "OMR gate not available")
    def test_strict_blocked_gate_blocks(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        report = OMRNormalizationReport(
            input_path="x",
            output_path="x",
            issues=[
                OMRIssue(
                    issue_id="OVR-1",
                    category="RHYTHM",
                    check="measure_overflow",
                    status=OMRStatus.OMR_ERROR,
                    severity="high",
                    edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                    part_id="P1",
                    measure_number="1",
                    description="overflow",
                )
            ],
        )
        service = SafeTranspositionService()
        result = service.transpose(
            score,
            TransposeRequest(interval=Interval(2, "M")),
            omr_report=report,
            mode=OMRGateMode.STRICT,
        )
        self.assertEqual(result.report.status, "blocked")
        self.assertEqual(
            result.score.parts[0].measures[0].voices[0].events[0].pitch,
            Pitch("C", 0, 4),
        )

    @unittest.skipUnless(_HAS_GATE, "OMR gate not available")
    def test_permissive_blocked_gate_allows_with_warning(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        report = OMRNormalizationReport(
            input_path="x",
            output_path="x",
            issues=[
                OMRIssue(
                    issue_id="OVR-1",
                    category="RHYTHM",
                    check="measure_overflow",
                    status=OMRStatus.OMR_ERROR,
                    severity="high",
                    edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                    part_id="P1",
                    measure_number="1",
                    description="overflow",
                )
            ],
        )
        service = SafeTranspositionService()
        result = service.transpose(
            score,
            TransposeRequest(interval=Interval(2, "M")),
            omr_report=report,
            mode=OMRGateMode.PERMISSIVE,
        )
        self.assertEqual(result.report.status, "ok")
        self.assertEqual(
            result.score.parts[0].measures[0].voices[0].events[0].pitch,
            Pitch("D", 0, 4),
        )
        self.assertTrue(any("OMR" in w for w in result.report.warnings))


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestTranspositionRoundtrip(unittest.TestCase):
    """MusicXML export → re-import preserves transposed semantics."""

    def test_transpose_then_roundtrip(self):
        score = make_score_with_note(Pitch("C", 0, 4), key=KeySignature(0, "major"))
        transposed = TranspositionEngine().transpose(
            score, TransposeRequest(interval=Interval(2, "M"))
        ).score

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "transposed.musicxml"
            MusicXMLExporter().export_file(transposed, path)
            reimported = MusicXMLImporter().import_file(path)

        note = reimported.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("D", 0, 4))
        self.assertEqual(
            reimported.parts[0].measures[0].key_signature,
            KeySignature(2, "major"),
        )

    def test_written_to_sounding_roundtrip(self):
        score = make_score_with_note(Pitch("C", 0, 4))
        score.parts[0].instrument.transposition = InstrumentTransposition(-1, -2, 0)
        converted = TranspositionEngine().transpose(
            score, TransposeRequest(operation=TranspositionOperation.WRITTEN_TO_SOUNDING)
        ).score

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "converted.musicxml"
            MusicXMLExporter().export_file(converted, path)
            reimported = MusicXMLImporter().import_file(path)

        note = reimported.parts[0].measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("B", -1, 3))


if __name__ == "__main__":
    unittest.main()
