"""Tests for the OMR Quality Gate.

The gate classifies issues by edit safety and decides whether a normalized
score is safe for deterministic downstream editing. All fixtures are
synthetic; no fixed measure numbers, part IDs, or filenames are used.
"""

from __future__ import annotations

import unittest

from omr_normalization import OMRGateMode, OMRNormalizer, OMRQualityGate
from omr_normalization.issue_model import OMREditSafety, OMRStatus
from tests.test_omr_normalization import (
    make_forward,
    make_measure,
    make_note,
    make_score,
    parse_score,
    write_to_temp,
)


class TestQualityGateStrict(unittest.TestCase):
    """STRICT mode blocks on unresolved blocking_for_edit issues."""

    def test_clean_score_is_allowed(self):
        xml = make_score(make_measure(1, make_note(1) * 4))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertEqual(result.status, "clean")
        self.assertTrue(result.allowed)
        self.assertTrue(result.allows_deterministic_edit)
        self.assertEqual(len(result.blocking_issues), 0)

    def test_informational_only_is_allowed(self):
        # Divisions change is informational; score is otherwise clean.
        # divisions=2 means two divisions per quarter, so quarter notes have duration=2.
        m1 = make_measure(1, make_note(1) * 4, divisions=1)
        m2 = make_measure(2, make_note(2) * 4, divisions=2)
        xml = make_score(m1 + m2)
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertTrue(result.allowed)
        self.assertTrue(result.allows_deterministic_edit)
        self.assertEqual(len(result.blocking_issues), 0)
        self.assertTrue(all(
            i.edit_safety == OMREditSafety.INFORMATIONAL
            for i in result.info
        ))

    def test_unresolved_overflow_blocks(self):
        xml = make_score(make_measure(1, make_note(1) * 5))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.allowed)
        self.assertFalse(result.allows_deterministic_edit)
        self.assertEqual(len(result.blocking_issues), 1)
        self.assertEqual(result.blocking_issues[0].check, "measure_overflow")

    def test_unresolved_underflow_blocks(self):
        xml = make_score(make_measure(1, make_note(1) * 3))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.allows_deterministic_edit)
        self.assertEqual(len(result.blocking_issues), 1)
        self.assertEqual(result.blocking_issues[0].check, "measure_underflow")

    def test_missing_measure_blocks(self):
        m1 = make_measure(1, make_note(1) * 4)
        m3 = make_measure(3, make_note(1) * 4)
        xml = make_score(m1 + m3)
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.allows_deterministic_edit)
        self.assertTrue(any(i.check == "missing_measure" for i in result.blocking_issues))

    def test_safe_fixed_forward_does_not_block(self):
        # 3 quarters + 1 quarter forward -> safely converted to rest.
        xml = make_score(make_measure(1, make_note(1) * 3 + make_forward(1)))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        forward_issues = [i for i in report.issues if i.check == "forward_element"]
        self.assertEqual(len(forward_issues), 1)
        self.assertEqual(forward_issues[0].status, OMRStatus.SAFE_FIX_APPLIED)
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertTrue(result.allowed)
        self.assertTrue(result.allows_deterministic_edit)
        self.assertEqual(len(result.blocking_issues), 0)


class TestQualityGatePermissive(unittest.TestCase):
    """PERMISSIVE mode allows editing but surfaces warnings."""

    def test_permissive_allows_severe_issues_with_degraded_status(self):
        xml = make_score(make_measure(1, make_note(1) * 5))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.PERMISSIVE)
        self.assertEqual(result.status, "degraded")
        self.assertTrue(result.allowed)
        self.assertTrue(result.allows_deterministic_edit)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].check, "measure_overflow")

    def test_permissive_clean_when_only_info(self):
        m1 = make_measure(1, make_note(1) * 4, divisions=1)
        m2 = make_measure(2, make_note(2) * 4, divisions=2)
        xml = make_score(m1 + m2)
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.PERMISSIVE)
        self.assertEqual(result.status, "clean")
        self.assertTrue(result.allowed)


class TestQualityGateRegression(unittest.TestCase):
    """Provenance/delta checks for downstream regression protection."""

    def test_non_blocking_notation_issue_allows_edit(self):
        # Unterminated slur is non_blocking for deterministic pitch edits.
        slur_note = make_note(1)
        slur_note = slur_note.replace(
            "    </note>",
            "      <notations>\n        <slur type=\"start\" number=\"1\"/>\n      </notations>\n    </note>",
        )
        xml = make_score(make_measure(1, slur_note * 4))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        self.assertEqual(result.status, "degraded")
        self.assertTrue(result.allows_deterministic_edit)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].check, "slur_pairing")

    def test_gate_summary_counts_are_consistent(self):
        xml = make_score(make_measure(1, make_note(1) * 5))
        report = OMRNormalizer().normalize(write_to_temp(xml))
        result = OMRQualityGate().check(report, OMRGateMode.STRICT)
        summary = result.summary
        self.assertEqual(summary["total_issues"], len(report.issues))
        self.assertEqual(summary["blocking_for_edit"], len(result.blocking_issues))
        self.assertEqual(summary["warnings"], len(result.warnings))


if __name__ == "__main__":
    unittest.main()
