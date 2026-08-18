"""Regression tests for run_real_provider_reliability runner helpers.

Ensures the runner does not crash when core intent objects lack diagnostic
fields and that malformed_json_subtype is read from ProviderAttempt only.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from ai import (
    AIClient,
    AIRequest,
    AIResponse,
    LLMIntentProvider,
    ProviderAttempt,
    TransposeIntent,
    TransposeIntentResolver,
    build_intent_context,
)
from ai.provider_diagnostics import (
    MALFORMED_JSON,
    classify_malformed_json,
)
from score_engine.score_ir import (
    Duration,
    Instrument,
    InstrumentTransposition,
    Measure,
    Note,
    Part,
    Pitch,
    Score,
    Voice,
)

import run_real_provider_reliability as runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeAIClient(AIClient):
    """Test double that returns a fixed or sequenced response or raises."""

    def __init__(self, response_content: str | Exception | list[str | Exception]) -> None:
        if isinstance(response_content, list):
            self._responses = response_content
        else:
            self._responses = [response_content]
        self._call_count = 0

    def call(self, request: AIRequest) -> AIResponse:
        idx = min(self._call_count, len(self._responses) - 1)
        item = self._responses[idx]
        self._call_count += 1
        if isinstance(item, BaseException):
            raise item
        return AIResponse(content=item, model="fake")


def make_test_score() -> Score:
    score = Score(title="Runner Test")
    part = Part(
        id="P1",
        name="Trumpet 1",
        instrument=Instrument(name="Trumpet", transposition=InstrumentTransposition(-1, -2, 0)),
    )
    measure = Measure(id="P1-M1", number="1")
    voice = Voice(id="P1-V1")
    voice.events.append(Note(
        id="P1-M1-N00",
        pitch=Pitch("C", 0, 4),
        duration=Duration(1, 1),
        voice="1",
    ))
    measure.voices.append(voice)
    part.measures.append(measure)
    score.parts.append(part)
    return score


# ---------------------------------------------------------------------------
# Runner helper unit tests
# ---------------------------------------------------------------------------

class TestRunnerHelpers(unittest.TestCase):
    def test_extract_malformed_subtype_from_last_attempt(self):
        a1 = ProviderAttempt(attempt=1, malformed_json_subtype="")
        a2 = ProviderAttempt(attempt=2, malformed_json_subtype="truncated")
        self.assertEqual(runner._extract_malformed_subtype((a1, a2)), "truncated")

    def test_extract_malformed_subtype_empty_diagnostics(self):
        self.assertEqual(runner._extract_malformed_subtype(()), "")
        self.assertEqual(runner._extract_malformed_subtype(tuple()), "")

    def test_extract_malformed_subtype_missing_field_safe(self):
        @dataclass
        class LegacyAttempt:
            attempt: int

        self.assertEqual(runner._extract_malformed_subtype((LegacyAttempt(1),)), "")

    def test_safe_error_reason_present(self):
        @dataclass
        class Obj:
            error_reason: str

        self.assertEqual(runner._safe_error_reason(Obj("timeout")), "timeout")

    def test_safe_error_reason_missing(self):
        self.assertEqual(runner._safe_error_reason(object()), "")
        self.assertEqual(runner._safe_error_reason(None), "")


# ---------------------------------------------------------------------------
# Runner _run_case regression tests
# ---------------------------------------------------------------------------

class TestRunnerRunCase(unittest.TestCase):
    def setUp(self):
        self.score = make_test_score()

    def test_success_result_no_malformed_subtype(self):
        client = FakeAIClient(
            '{"status": "ready", "operation": "transpose", "direction": "up", '
            '"interval_description": "大二度", "is_all_parts": true, "confidence": 0.9}'
        )
        provider = LLMIntentProvider(client, max_retries=0)
        record = runner._run_case("整首升大二度", provider, self.score)
        self.assertEqual(record.resolver_status, "ready")
        self.assertEqual(record.error_reason, "")
        self.assertEqual(record.malformed_json_subtype, "")

    def test_provider_error_malformed_json(self):
        client = FakeAIClient('not json at all')
        provider = LLMIntentProvider(client, max_retries=0)
        record = runner._run_case("升大二度", provider, self.score)
        self.assertEqual(record.resolver_status, "provider_error")
        self.assertEqual(record.error_reason, MALFORMED_JSON)
        self.assertEqual(record.malformed_json_subtype, "completely_invalid")
        self.assertEqual(len(record.attempts), 1)
        self.assertEqual(record.attempts[0].malformed_json_subtype, "completely_invalid")

    def test_provider_error_non_malformed_json(self):
        from ai.provider_diagnostics import EMPTY_CONTENT
        client = FakeAIClient("")
        provider = LLMIntentProvider(client, max_retries=0)
        record = runner._run_case("升大二度", provider, self.score)
        self.assertEqual(record.resolver_status, "provider_error")
        self.assertEqual(record.error_reason, EMPTY_CONTENT)
        self.assertEqual(record.malformed_json_subtype, "")

    def test_retry_recovery_success(self):
        client = FakeAIClient([
            "not json at all",
            '{"status": "ready", "operation": "transpose", "direction": "up", '
            '"interval_description": "大二度", "is_all_parts": true, "confidence": 0.9}',
        ])
        provider = LLMIntentProvider(client, max_retries=1)
        record = runner._run_case("整首升大二度", provider, self.score)
        self.assertEqual(record.resolver_status, "ready")
        self.assertTrue(record.recovered_by_retry)
        self.assertEqual(len(record.attempts), 2)
        self.assertEqual(record.attempts[0].malformed_json_subtype, "completely_invalid")

    def test_missing_diagnostics_fields_does_not_crash(self):
        """Simulate an old AIClient that returns AIResponse without diagnostics."""
        class MinimalClient(AIClient):
            def call(self, request: AIRequest) -> AIResponse:
                return AIResponse(
                    content='{"status": "ready", "operation": "transpose", "direction": "up", '
                            '"interval_description": "大二度", "is_all_parts": true}'
                )

        provider = LLMIntentProvider(MinimalClient(), max_retries=0)
        record = runner._run_case("整首升大二度", provider, self.score)
        self.assertEqual(record.resolver_status, "ready")


if __name__ == "__main__":
    unittest.main()
