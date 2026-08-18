"""Tests for the OMR Validation / Recovery / Normalization Layer.

All fixtures are synthetic MusicXML strings generated in code. No test
depends on a real score, fixed measure number, part ID, or filename.
Colores is used only in the integration test at the end.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lxml import etree

from omr_normalization import (
    DivisionsDetector,
    NotationDetector,
    OMRNormalizer,
    OMRReporter,
    RhythmDetector,
    StructureDetector,
)
from omr_normalization.issue_model import OMRCategory, OMRStatus


# ---------------------------------------------------------------------------
# Synthetic fixture builder
# ---------------------------------------------------------------------------

def make_score(part_content: str) -> str:
    """Wrap part content in a minimal score-partwise document."""
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
    notes: str,
    divisions: int = 1,
    beats: int = 4,
    beat_type: int = 4,
    implicit: bool = False,
) -> str:
    """Build one measure with the given inner MusicXML content."""
    implicit_attr = ' implicit="yes"' if implicit else ""
    return f"""    <measure number="{number}"{implicit_attr}>
      <attributes>
        <divisions>{divisions}</divisions>
        <time>
          <beats>{beats}</beats>
          <beat-type>{beat_type}</beat-type>
        </time>
      </attributes>
{notes}
    </measure>"""


def make_note(
    duration: int,
    voice: int = 1,
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
      <type>{type_name}</type>
    </note>"""


def make_rest(duration: int, voice: int = 1, type_name: str = "quarter") -> str:
    return f"""      <note>
      <rest/>
      <duration>{duration}</duration>
      <voice>{voice}</voice>
      <type>{type_name}</type>
    </note>"""


def make_forward(duration: int, voice: int = 1) -> str:
    return f"""      <forward>
      <duration>{duration}</duration>
      <voice>{voice}</voice>
    </forward>"""


def make_backup(duration: int) -> str:
    return f"""      <backup>
      <duration>{duration}</duration>
    </backup>"""


def parse_score(content: str) -> etree._ElementTree:
    return etree.ElementTree(etree.fromstring(content.encode("utf-8")))


# ---------------------------------------------------------------------------
# Rhythm detector tests
# ---------------------------------------------------------------------------

class TestRhythmDetector(unittest.TestCase):
    """Synthetic rhythm tests."""

    def test_normal_measure_passes(self):
        xml = make_score(make_measure(1, make_note(1) + make_note(1) + make_note(1) + make_note(1)))
        issues = RhythmDetector().detect(parse_score(xml))
        rhythm = [i for i in issues if i.category == OMRCategory.RHYTHM]
        self.assertEqual(len(rhythm), 0)

    def test_overflow_detected(self):
        # 5 quarters in 4/4
        xml = make_score(make_measure(1, make_note(1) * 5))
        issues = RhythmDetector().detect(parse_score(xml))
        overflow = [i for i in issues if i.check == "measure_overflow"]
        self.assertEqual(len(overflow), 1)
        self.assertEqual(overflow[0].status, OMRStatus.OMR_ERROR)
        self.assertEqual(overflow[0].severity, "high")

    def test_underflow_detected(self):
        # 3 quarters in 4/4
        xml = make_score(make_measure(1, make_note(1) * 3))
        issues = RhythmDetector().detect(parse_score(xml))
        underflow = [i for i in issues if i.check == "measure_underflow"]
        self.assertEqual(len(underflow), 1)
        self.assertEqual(underflow[0].status, OMRStatus.OMR_ERROR)

    def test_rest_fills_measure(self):
        xml = make_score(make_measure(1, make_rest(1) + make_rest(1) + make_rest(1) + make_rest(1)))
        issues = RhythmDetector().detect(parse_score(xml))
        rhythm = [i for i in issues if i.category == OMRCategory.RHYTHM]
        self.assertEqual(len(rhythm), 0)

    def test_chord_tones_do_not_count_extra(self):
        # 1 quarter chord + 3 more quarters = exactly 4
        chord = make_note(1, pitch_step="C") + make_note(1, voice=1, pitch_step="E", chord=True)
        xml = make_score(make_measure(1, chord + make_note(1) + make_note(1) + make_note(1)))
        issues = RhythmDetector().detect(parse_score(xml))
        rhythm = [i for i in issues if i.category == OMRCategory.RHYTHM]
        self.assertEqual(len(rhythm), 0)

    def test_valid_forward_converted(self):
        # Voice has 3 quarters, then a forward of 1 quarter -> safe to convert
        xml = make_score(make_measure(1, make_note(1) * 3 + make_forward(1)))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        forward_issues = [i for i in report.issues if i.check == "forward_element"]
        self.assertEqual(len(forward_issues), 1)
        self.assertEqual(len(report.fixes_applied), 1)
        self.assertEqual(report.fixes_applied[0]["fix_type"], "forward_to_rest")

    def test_conflicting_forward_not_converted(self):
        # Voice already has 4 quarters, forward of 1 would overflow -> do not convert
        xml = make_score(make_measure(1, make_note(1) * 4 + make_forward(1)))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        forward_issues = [i for i in report.issues if i.check == "forward_element"]
        self.assertEqual(len(forward_issues), 1)
        # No safe fix applied because conversion would create overflow.
        self.assertEqual(len(report.fixes_applied), 0)

    def test_backup_multi_voice(self):
        # Voice 1: 4 quarters. Backup 4, Voice 2: 4 quarters.
        content = (
            make_note(1, voice=1) * 4
            + make_backup(4)
            + make_note(1, voice=2) * 4
        )
        xml = make_score(make_measure(1, content))
        issues = RhythmDetector().detect(parse_score(xml))
        rhythm = [i for i in issues if i.category == OMRCategory.RHYTHM]
        self.assertEqual(len(rhythm), 0)


# ---------------------------------------------------------------------------
# Structure detector tests
# ---------------------------------------------------------------------------

class TestStructureDetector(unittest.TestCase):
    """Synthetic structure tests."""

    def test_missing_measure_detected(self):
        xml = make_score(
            make_measure(1, make_note(1) * 4)
            + make_measure(3, make_note(1) * 4)
        )
        issues = StructureDetector().detect(parse_score(xml))
        missing = [i for i in issues if i.check == "missing_measure"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].measure_number, "2")

    def test_empty_measure_detected(self):
        xml = make_score(make_measure(1, ""))
        issues = StructureDetector().detect(parse_score(xml))
        empty = [i for i in issues if i.check == "empty_measure"]
        self.assertEqual(len(empty), 1)

    def test_part_measure_count_mismatch(self):
        # Two parts with different measure counts
        part1 = make_measure(1, make_note(1) * 4)
        part2 = make_measure(1, make_note(1) * 4) + make_measure(2, make_note(1) * 4)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>A</part-name></score-part>
    <score-part id="P2"><part-name>B</part-name></score-part>
  </part-list>
  <part id="P1">
{part1}
  </part>
  <part id="P2">
{part2}
  </part>
</score-partwise>
"""
        issues = StructureDetector().detect(parse_score(xml))
        mismatch = [i for i in issues if i.check == "part_measure_count_mismatch"]
        self.assertEqual(len(mismatch), 1)


# ---------------------------------------------------------------------------
# Divisions detector tests
# ---------------------------------------------------------------------------

class TestDivisionsDetector(unittest.TestCase):
    """Synthetic divisions tests."""

    def test_divisions_change_reported(self):
        m1 = make_measure(1, make_note(1) * 4, divisions=2)
        m2 = make_measure(2, make_note(6) * 4, divisions=6)
        xml = make_score(m1 + m2)
        issues = DivisionsDetector().detect(parse_score(xml))
        changes = [i for i in issues if i.check == "divisions_change"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].status, OMRStatus.INFO)

    def test_divisions_variety_reported(self):
        m1 = make_measure(1, make_note(1) * 4, divisions=2)
        m2 = make_measure(2, make_note(6) * 4, divisions=6)
        m3 = make_measure(3, make_note(12) * 4, divisions=12)
        xml = make_score(m1 + m2 + m3)
        issues = DivisionsDetector().detect(parse_score(xml))
        variety = [i for i in issues if i.check == "divisions_variety"]
        self.assertEqual(len(variety), 1)
        self.assertEqual(variety[0].evidence["divisions_seen"], [2, 6, 12])


# ---------------------------------------------------------------------------
# Notation detector tests
# ---------------------------------------------------------------------------

class TestNotationDetector(unittest.TestCase):
    """Synthetic notation-pairing tests."""

    def test_tie_pairing_ok(self):
        # Build two tied quarter notes manually
        n1 = """      <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>2</duration>
      <voice>1</voice>
      <type>quarter</type>
      <tie type="start"/>
      <notations><tied type="start"/></notations>
    </note>"""
        n2 = """      <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>2</duration>
      <voice>1</voice>
      <type>quarter</type>
      <tie type="stop"/>
      <notations><tied type="stop"/></notations>
    </note>"""
        xml = make_score(make_measure(1, n1 + n2))
        issues = NotationDetector().detect(parse_score(xml))
        tie_issues = [i for i in issues if i.check == "tie_pairing"]
        self.assertEqual(len(tie_issues), 0)

    def test_unterminated_tie_detected(self):
        n1 = """      <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>2</duration>
      <voice>1</voice>
      <type>quarter</type>
      <tie type="start"/>
      <notations><tied type="start"/></notations>
    </note>"""
        xml = make_score(make_measure(1, n1))
        issues = NotationDetector().detect(parse_score(xml))
        unterminated = [i for i in issues if i.check == "tie_pairing" and "UNTERMINATED" in i.issue_id]
        self.assertEqual(len(unterminated), 1)

    def test_dangling_slur_stop_detected(self):
        n1 = """      <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>4</duration>
      <voice>1</voice>
      <type>quarter</type>
      <notations><slur type="stop" number="1"/></notations>
    </note>"""
        xml = make_score(make_measure(1, n1))
        issues = NotationDetector().detect(parse_score(xml))
        dangling = [i for i in issues if i.check == "slur_pairing" and "DANGLE-STOP" in i.issue_id]
        self.assertEqual(len(dangling), 1)

    def test_tuplet_pairing_ok(self):
        n1 = """      <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>2</duration>
      <voice>1</voice>
      <type>eighth</type>
      <notations><tuplet type="start" number="1"/></notations>
    </note>"""
        n2 = """      <note>
      <pitch><step>D</step><octave>4</octave></pitch>
      <duration>2</duration>
      <voice>1</voice>
      <type>eighth</type>
      <notations><tuplet type="stop" number="1"/></notations>
    </note>"""
        xml = make_score(make_measure(1, n1 + n2))
        issues = NotationDetector().detect(parse_score(xml))
        tuplet_issues = [i for i in issues if i.check == "tuplet_pairing"]
        self.assertEqual(len(tuplet_issues), 0)


# ---------------------------------------------------------------------------
# Normalizer integration tests
# ---------------------------------------------------------------------------

class TestOMRNormalizer(unittest.TestCase):
    """Integration tests for the normalizer on synthetic scores."""

    def test_normalizer_runs_without_crash(self):
        xml = make_score(make_measure(1, make_note(1) * 4))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        self.assertEqual(len(report.issues), 0)
        self.assertIsNotNone(report.output_path)

    def test_report_serialization(self):
        xml = make_score(make_measure(1, make_note(1) * 5))  # overflow
        report = OMRNormalizer().normalize(write_to_temp(xml))
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            md_path = Path(tmpdir) / "report.md"
            OMRReporter.save_json(report, json_path)
            OMRReporter.save_markdown(report, md_path)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            data = report.to_dict()
            self.assertIn("issues", data)
            self.assertIn("fixes_applied", data)

    def test_raw_input_preserved(self):
        xml = make_score(make_measure(1, make_forward(1)))
        raw_path = write_to_temp(xml)
        original_text = Path(raw_path).read_text(encoding="utf-8")
        report = OMRNormalizer().normalize(raw_path)
        self.assertTrue(Path(raw_path).exists())
        self.assertEqual(Path(raw_path).read_text(encoding="utf-8"), original_text)


# ---------------------------------------------------------------------------
# Colores integration test
# ---------------------------------------------------------------------------

class TestColoresIntegration(unittest.TestCase):
    """Colores is used only as an integration fixture, never as a rule source."""

    def test_colores_normalizer_runs(self):
        path = Path("colores_v2/omr/Colores_-_Piano_Reduction_raw.musicxml")
        if not path.exists():
            self.skipTest("Colores raw MusicXML not found")
        report = OMRNormalizer().normalize(path, output_path=None)
        # We expect many OMR issues; the point is that detection runs.
        self.assertGreater(len(report.issues), 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_to_temp(content: str) -> str:
    with tempfile.NamedTemporaryFile(
        suffix=".musicxml", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


if __name__ == "__main__":
    unittest.main()
