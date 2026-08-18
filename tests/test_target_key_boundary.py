"""Target-key transposition V1 boundary tests.

V1 does not implement transposition to a target key. These tests verify that
such requests are deterministically classified as unsupported, regardless of
the model's returned status, without hardcoding specific sentences.
"""

from __future__ import annotations

import unittest

from ai import TransposeIntent, TransposeIntentResolver
from score_engine.score_ir.score_ir import Score

from tests.e2e_fixtures import import_fixture, make_single_trumpet_musicxml


class TestTargetKeyBoundary(unittest.TestCase):
    """Target-key requests must be unsupported in V1."""

    @classmethod
    def setUpClass(cls):
        cls.score = import_fixture(make_single_trumpet_musicxml(measures=10))
        cls.resolver = TransposeIntentResolver()

    def _resolve(self, text: str, status: str = "ready", **fields) -> str:
        """Resolve a synthetic intent and return the resolver status."""
        intent = TransposeIntent(
            status=status,
            source_text=text,
            **fields,
        )
        result = self.resolver.resolve(intent, self.score)
        return result.status

    def test_chinese_move_to_eb_major_unsupported(self):
        self.assertEqual(
            self._resolve("把整首移到降E大调", status="needs_clarification"),
            "unsupported",
        )

    def test_chinese_change_to_d_major_unsupported(self):
        self.assertEqual(
            self._resolve("移成D大调", status="needs_clarification"),
            "unsupported",
        )

    def test_chinese_convert_to_f_minor_unsupported(self):
        self.assertEqual(
            self._resolve("转成F小调", status="needs_clarification"),
            "unsupported",
        )

    def test_english_transpose_to_eb_major_unsupported(self):
        self.assertEqual(
            self._resolve("transpose to Eb major", status="needs_clarification"),
            "unsupported",
        )

    def test_english_move_whole_score_to_d_major_unsupported(self):
        self.assertEqual(
            self._resolve(
                "move the whole score to D major",
                status="needs_clarification",
            ),
            "unsupported",
        )

    def test_target_key_in_interval_description_unsupported(self):
        """The model may put the target-key text into interval_description."""
        self.assertEqual(
            self._resolve(
                "把整首升大二度",
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="移到降E大调（目标调）",
                is_all_parts=True,
            ),
            "unsupported",
        )

    def test_target_key_in_clarification_question_unsupported(self):
        """The model may ask about target key in clarification_question."""
        self.assertEqual(
            self._resolve(
                "把整首移到降E大调",
                status="needs_clarification",
                clarification_question="请问您要移到降E大调吗？",
            ),
            "unsupported",
        )

    def test_model_already_unsupported_preserved(self):
        """If the model correctly returns unsupported, keep it."""
        self.assertEqual(
            self._resolve(
                "把整首移到降E大调",
                status="unsupported",
                clarification_question="Target-key transposition is not supported in V1.",
            ),
            "unsupported",
        )

    def test_interval_transpose_not_affected(self):
        self.assertEqual(
            self._resolve(
                "把整首升大二度",
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                is_all_parts=True,
            ),
            "ready",
        )

    def test_instrument_transposition_not_affected(self):
        self.assertEqual(
            self._resolve(
                "把Bb小号改成实际音高",
                status="ready",
                operation="written_to_sounding",
                part_description="Trumpet 1",
            ),
            "ready",
        )

    def test_ambiguous_request_not_affected(self):
        self.assertEqual(
            self._resolve(
                "后面一点降一点",
                status="needs_clarification",
                clarification_question="请说明具体音程。",
            ),
            "needs_clarification",
        )

    def test_interval_with_major_not_flagged(self):
        """'大二度' contains '大' but is not a target-key request."""
        self.assertEqual(
            self._resolve(
                "把整首升大二度",
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                is_all_parts=True,
            ),
            "ready",
        )


if __name__ == "__main__":
    unittest.main()
