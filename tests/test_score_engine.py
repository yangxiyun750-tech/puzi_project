"""Regression tests for the complete Score Engine pipeline.

Uses unittest (standard library) so no external dependencies are required.

Run with:
    PYTHONPATH=src python -m unittest tests.test_score_engine -v
"""

from __future__ import annotations

import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from omr_normalization import OMRNormalizer
from score_engine.musicxml import MusicXMLImporter, MusicXMLExporter
from score_engine.score_ir import Score, Note, Pitch, Duration, Rest
from score_engine.validation import InstrumentIdentityResolver, RoundtripValidator


_EPSILON = Fraction(1, 128)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def get_colores_score() -> Score:
    """Import ScoreIR from raw Colores MusicXML."""
    path = Path("colores_v2/omr/Colores_-_Piano_Reduction_raw.musicxml")
    importer = MusicXMLImporter()
    return importer.import_file(path)


# ---------------------------------------------------------------------------
# Test: MusicXML → ScoreIR import
# ---------------------------------------------------------------------------

class TestMusicXMLImport(unittest.TestCase):
    """Verify MusicXML → ScoreIR import correctness."""

    @classmethod
    def setUpClass(cls):
        cls.score = get_colores_score()

    def test_import_parts(self):
        self.assertEqual(len(self.score.parts), 2)
        self.assertEqual(self.score.parts[0].id, "P1")
        self.assertEqual(self.score.parts[1].id, "P2")

    def test_import_measure_counts(self):
        p1 = self.score.get_part("P1")
        p2 = self.score.get_part("P2")
        self.assertEqual(len(p1.measures), 256)
        self.assertEqual(len(p2.measures), 259)

    def test_import_divisions(self):
        """Divisions must be tracked correctly (2, 6, or 12)."""
        p1 = self.score.get_part("P1")
        divisions_seen = {m.divisions for m in p1.measures}
        self.assertEqual(divisions_seen, {2, 6, 12})

    def test_import_chord_tones(self):
        """Chord tones must be marked as is_chord_tone=True."""
        p2 = self.score.get_part("P2")
        chord_tones = 0
        for m in p2.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note) and e.is_chord_tone:
                        chord_tones += 1
        self.assertGreater(chord_tones, 0)

    def test_import_ties(self):
        """Ties must be parsed from both <tie> and <tied>."""
        p1 = self.score.get_part("P1")
        tie_count = 0
        for m in p1.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note):
                        tie_count += len(e.ties)
        self.assertGreater(tie_count, 0)

    def test_import_slurs(self):
        """Slurs must be parsed."""
        p1 = self.score.get_part("P1")
        slur_count = 0
        for m in p1.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note):
                        slur_count += len(e.slurs)
        self.assertGreater(slur_count, 0)

    def test_import_tuplets(self):
        """Tuplets must be parsed."""
        p1 = self.score.get_part("P1")
        tuplet_count = 0
        for m in p1.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note) and e.tuplet:
                        tuplet_count += 1
        self.assertGreater(tuplet_count, 0)

    def test_import_fermatas(self):
        """Fermatas must be parsed."""
        p1 = self.score.get_part("P1")
        fermata_count = 0
        for m in p1.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note) and e.fermata:
                        fermata_count += 1
        self.assertGreater(fermata_count, 0)

    def test_import_arpeggio(self):
        """Arpeggio must be parsed."""
        p2 = self.score.get_part("P2")
        arpeg_count = 0
        for m in p2.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Note) and e.arpeggiate:
                        arpeg_count += 1
        self.assertGreater(arpeg_count, 0)

    def test_voice_total_duration_excludes_chord_tones(self):
        """Chord tones must NOT contribute to voice total duration."""
        p2 = self.score.get_part("P2")
        for m in p2.measures[:10]:
            for v in m.voices:
                self.assertLessEqual(
                    v.total_duration, 4,
                    f"M{m.number} {v.id}: {v.total_duration} > 4"
                )


# ---------------------------------------------------------------------------
# Test: ScoreIR → MusicXML export
# ---------------------------------------------------------------------------

class TestMusicXMLExport(unittest.TestCase):
    """Verify ScoreIR → MusicXML export correctness."""

    @classmethod
    def setUpClass(cls):
        cls.score = get_colores_score()

    def test_export_creates_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_export.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(self.score, out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_export_preserves_part_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_export.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(self.score, out)

            importer = MusicXMLImporter()
            reimported = importer.import_file(out)
            self.assertEqual(len(reimported.parts), 2)

    def test_export_preserves_measure_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_export.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(self.score, out)

            importer = MusicXMLImporter()
            reimported = importer.import_file(out)
            self.assertEqual(len(reimported.get_part("P1").measures), 256)
            self.assertEqual(len(reimported.get_part("P2").measures), 259)

    def test_export_preserves_divisions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_export.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(self.score, out)

            importer = MusicXMLImporter()
            reimported = importer.import_file(out)
            p1 = reimported.get_part("P1")
            divisions_seen = {m.divisions for m in p1.measures}
            self.assertEqual(divisions_seen, {2, 6, 12})

    def test_export_preserves_tuplets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_export.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(self.score, out)

            importer = MusicXMLImporter()
            reimported = importer.import_file(out)
            p1 = reimported.get_part("P1")
            tuplet_count = sum(
                1 for m in p1.measures for v in m.voices for e in v.events
                if isinstance(e, Note) and e.tuplet
            )
            self.assertGreater(tuplet_count, 0)


# ---------------------------------------------------------------------------
# Test: Instrument Identity Resolution
# ---------------------------------------------------------------------------

class TestInstrumentIdentity(unittest.TestCase):
    """Verify instrument identity resolution."""

    @classmethod
    def setUpClass(cls):
        cls.score = get_colores_score()
        cls.resolver = InstrumentIdentityResolver(
            pdf_text="Colores for Bass Trombone solo & Piano"
        )
        cls.identities = cls.resolver.resolve(cls.score)

    def test_resolve_bass_trombone(self):
        p1 = next(i for i in self.identities if i.part_id == "P1")
        self.assertEqual(p1.canonical_instrument, "Bass Trombone")
        self.assertEqual(p1.confidence, "high")
        self.assertFalse(p1.is_vocal)

    def test_resolve_piano(self):
        p2 = next(i for i in self.identities if i.part_id == "P2")
        self.assertEqual(p2.canonical_instrument, "Piano")
        self.assertEqual(p2.confidence, "high")
        self.assertFalse(p2.is_vocal)

    def test_no_vocal_parts(self):
        vocal = [i for i in self.identities if i.is_vocal]
        self.assertEqual(len(vocal), 0)


# ---------------------------------------------------------------------------
# Test: Round-trip validation
# ---------------------------------------------------------------------------

class TestRoundtrip(unittest.TestCase):
    """Verify MusicXML → ScoreIR → MusicXML round-trip."""

    def test_roundtrip_semantics(self):
        path = Path("colores_v2/omr/Colores_-_Piano_Reduction_raw.musicxml")
        importer = MusicXMLImporter()
        original = importer.import_file(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "roundtrip.musicxml"
            exporter = MusicXMLExporter()
            exporter.export_file(original, out)

            reimported = importer.import_file(out)

            validator = RoundtripValidator()
            report = validator.validate(original, reimported)

            errors = [f for f in report.findings if f.severity == "ERROR"]
            self.assertEqual(
                len(errors), 0,
                f"Round-trip errors: {[e.description for e in errors[:5]]}"
            )


# ---------------------------------------------------------------------------
# Test: Forward → Rest conversion
# ---------------------------------------------------------------------------

class TestForwardToRest(unittest.TestCase):
    """Verify forward elements are converted to rests correctly."""

    @classmethod
    def setUpClass(cls):
        cls.score = get_colores_score()

    def test_forward_creates_rest(self):
        """Forward elements must create explicit rests in ScoreIR."""
        p2 = self.score.get_part("P2")
        rest_count = 0
        for m in p2.measures:
            for v in m.voices:
                for e in v.events:
                    if isinstance(e, Rest):
                        rest_count += 1
        self.assertGreater(rest_count, 0)

    def test_no_new_overflows_introduced_by_score_engine(self):
        """Score Engine must not introduce new measure overflows.

        Compares per-voice overflows found in the raw OMR MusicXML with those
        present after import into ScoreIR. Any overflow present in the ScoreIR
        output but absent from the raw input is a regression.
        """
        raw_path = Path("colores_v2/omr/Colores_-_Piano_Reduction_raw.musicxml")

        # Raw OMR overflow set from the normalization layer (provenance).
        raw_report = OMRNormalizer().detect_only(raw_path)
        raw_overflows = set()
        for issue in raw_report.issues:
            if issue.check == "measure_overflow":
                raw_overflows.add((issue.part_id, issue.measure_number, issue.voice_id))

        # ScoreIR-processed overflow set.
        def overflow_set(score: Score) -> set[tuple[str, str, str]]:
            result: set[tuple[str, str, str]] = set()
            for part in score.parts:
                for measure in part.measures:
                    if measure.implicit:
                        continue
                    expected = (
                        measure.time_signature.quarters_per_measure
                        if measure.time_signature
                        else Fraction(4)
                    )
                    for voice in measure.voices:
                        if voice.total_duration > expected + _EPSILON:
                            result.add((part.id, measure.number, voice.id))
            return result

        processed_overflows = overflow_set(self.score)
        new_overflows = processed_overflows - raw_overflows

        self.assertEqual(
            new_overflows,
            set(),
            f"Score Engine introduced new overflows: {new_overflows}"
        )


if __name__ == "__main__":
    unittest.main()
