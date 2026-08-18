"""Natural Language → TransposeRequest V1 tests.

Run with:
    PYTHONPATH=src python -m unittest tests.test_transpose_intent -v
"""

from __future__ import annotations

import json
import unittest

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
from score_engine.transposition import (
    Interval,
    TranspositionEngine,
    TranspositionOperation,
    TransposeRequest,
)
from ai import (
    AIClient,
    AIProviderError,
    AIRequest,
    AIResponse,
    EMPTY_CONTENT,
    EMPTY_RESPONSE,
    HTTP_ERROR,
    IntentContext,
    IntentValidator,
    LLMIntentProvider,
    MALFORMED_JSON,
    MockIntentProvider,
    OpenAICompatibleClient,
    ProviderAttempt,
    SCHEMA_MISMATCH,
    TIMEOUT,
    TransposeIntent,
    TransposeIntentResolver,
    TransposeIntentResult,
    build_intent_context,
)
from ai.intent_resolver import (
    IntervalResolver,
    MeasureResolver,
    PartResolver,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_part(
    part_id: str,
    name: str,
    instrument_name: str = "",
    transposition: InstrumentTransposition | None = None,
    measure_count: int = 4,
) -> Part:
    part = Part(
        id=part_id,
        name=name,
        instrument=Instrument(
            name=instrument_name,
            transposition=transposition or InstrumentTransposition(),
        ),
    )
    for i in range(1, measure_count + 1):
        measure = Measure(id=f"{part_id}-M{i}", number=str(i))
        voice = Voice(id=f"{part_id}-V{i}")
        voice.events.append(Note(
            id=f"{part_id}-M{i}-V1-N00",
            pitch=Pitch("C", 0, 4),
            duration=Duration(1, 1),
            voice="1",
        ))
        measure.voices.append(voice)
        part.measures.append(measure)
    return part


def make_test_score() -> Score:
    score = Score(title="Test Score")
    score.parts.append(make_part("P1", "Trumpet 1", "Trumpet", InstrumentTransposition(-1, -2, 0), 50))
    score.parts.append(make_part("P2", "Trumpet 2", "Trumpet", InstrumentTransposition(-1, -2, 0), 50))
    score.parts.append(make_part("P3", "Trombone", "Trombone", measure_count=50))
    score.parts.append(make_part("P4", "Piano", "Piano", measure_count=50))
    return score


# ---------------------------------------------------------------------------
# Mock provider + resolver end-to-end
# ---------------------------------------------------------------------------

def _make_resolver(response_map: dict[str, TransposeIntent]) -> tuple[MockIntentProvider, TransposeIntentResolver]:
    provider = MockIntentProvider(response_map)
    resolver = TransposeIntentResolver()
    return provider, resolver


def _resolve(provider: MockIntentProvider, resolver: TransposeIntentResolver, text: str, score: Score) -> TransposeIntentResult:
    context = build_intent_context(score)
    intent = provider.parse_transpose(text, context)
    return resolver.resolve(intent, score)


class TestTransposeIntentEndToEnd(unittest.TestCase):
    """Full NL → TransposeRequest flows using MockIntentProvider."""

    def setUp(self):
        self.score = make_test_score()

    def test_whole_score_up_major_second(self):
        text = "整首升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                is_all_parts=True,
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        req = result.request
        self.assertEqual(req.operation, TranspositionOperation.INTERVAL)
        self.assertEqual(req.interval, Interval(2, "M", 1))
        self.assertEqual(req.part_ids, ["P1", "P2", "P3", "P4"])
        self.assertEqual(req.measure_start, 1)
        self.assertEqual(req.measure_end, 50)

    def test_whole_score_down_minor_third(self):
        text = "整首降小三度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="down",
                interval_description="小三度",
                is_all_parts=True,
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        req = result.request
        self.assertEqual(req.interval, Interval(3, "m", -1))

    def test_trombone_up_octave(self):
        text = "把长号升一个八度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="八度",
                part_description="长号",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        req = result.request
        self.assertEqual(req.part_ids, ["P3"])
        self.assertEqual(req.interval, Interval(8, "P", 1))

    def test_trumpet_measure_range_up_major_second(self):
        text = "把32到48小节的Trumpet 1升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="Trumpet 1",
                measure_start_description="32",
                measure_end_description="48",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        req = result.request
        self.assertEqual(req.part_ids, ["P1"])
        self.assertEqual(req.measure_start, 32)
        self.assertEqual(req.measure_end, 48)
        self.assertEqual(req.interval, Interval(2, "M", 1))

    def test_english_transpose_request(self):
        text = "Transpose Trumpet 1 up a major second"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="major second",
                part_description="Trumpet 1",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.request.part_ids, ["P1"])
        self.assertEqual(result.request.interval, Interval(2, "M", 1))

    def test_part_id_measure_range_down_perfect_fifth(self):
        text = "P2第20到40小节降纯五度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="down",
                interval_description="纯五度",
                part_description="P2",
                measure_start_description="20",
                measure_end_description="40",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        req = result.request
        self.assertEqual(req.part_ids, ["P2"])
        self.assertEqual(req.measure_start, 20)
        self.assertEqual(req.measure_end, 40)
        self.assertEqual(req.interval, Interval(5, "P", -1))

    def test_nonexistent_instrument(self):
        text = "把小提琴升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="小提琴",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "invalid")
        self.assertIn("小提琴", result.clarification_question)

    def test_multiple_trumpets_ambiguity(self):
        text = "把小号升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="小号",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "needs_clarification")
        self.assertTrue(len(result.ambiguities) >= 2)

    def test_nonexistent_measure(self):
        text = "把P1第100小节升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="P1",
                measure_start_description="100",
                measure_end_description="100",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "invalid")
        self.assertIn("measure", result.clarification_question.lower())

    def test_start_greater_than_end(self):
        text = "把P1第40到20小节升大二度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="P1",
                measure_start_description="40",
                measure_end_description="20",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "invalid")
        self.assertIn("start", result.clarification_question.lower())

    def test_vague_down_a_key_clarification(self):
        text = "降一个调"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="needs_clarification",
                clarification_question="你希望降低什么音程？",
                confidence=0.3,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "needs_clarification")

    def test_vague_a_little_lower_clarification(self):
        text = "低一点"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="needs_clarification",
                clarification_question="请具体说明降低的音程。",
                confidence=0.3,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "needs_clarification")

    def test_unsupported_interval(self):
        text = "把P1升增四度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="增四度",
                part_description="P1",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "needs_clarification")
        self.assertIn("interval", result.clarification_question.lower())

    def test_explicit_written_pitch_basis(self):
        text = "把P1的记谱音高写出来"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="sounding_to_written",
                part_description="P1",
                basis="written",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.request.operation, TranspositionOperation.SOUNDING_TO_WRITTEN)

    def test_explicit_concert_pitch_basis(self):
        text = "把P1转成实际音高"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="written_to_sounding",
                part_description="P1",
                basis="concert",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.request.operation, TranspositionOperation.WRITTEN_TO_SOUNDING)

    def test_mock_provider_executes_transpose_engine(self):
        text = "把P3降纯五度"
        provider, resolver = _make_resolver({
            text: TransposeIntent(
                status="ready",
                operation="transpose",
                direction="down",
                interval_description="纯五度",
                part_description="P3",
                confidence=0.95,
            )
        })
        result = _resolve(provider, resolver, text, self.score)
        self.assertEqual(result.status, "ready")
        engine_result = TranspositionEngine().transpose(self.score, result.request)
        note = engine_result.score.get_part("P3").measures[0].voices[0].events[0]
        self.assertEqual(note.pitch, Pitch("F", 0, 3))


# ---------------------------------------------------------------------------
# Resolver unit tests
# ---------------------------------------------------------------------------

class TestPartResolver(unittest.TestCase):
    def setUp(self):
        self.score = make_test_score()
        self.resolver = PartResolver(self.score)

    def test_exact_id_match(self):
        ids, reason = self.resolver.resolve("P2", False)
        self.assertEqual(ids, ["P2"])
        self.assertEqual(reason, "exact_id")

    def test_name_match_single(self):
        ids, reason = self.resolver.resolve("Trombone", False)
        self.assertEqual(ids, ["P3"])
        self.assertEqual(reason, "name_match")

    def test_chinese_alias_match(self):
        ids, reason = self.resolver.resolve("长号", False)
        self.assertEqual(ids, ["P3"])

    def test_ambiguous_chinese_trumpet(self):
        ids, reason = self.resolver.resolve("小号", False)
        self.assertIsNone(ids)
        self.assertTrue(reason.startswith("ambiguous_match"))

    def test_not_found(self):
        ids, reason = self.resolver.resolve("Violin", False)
        self.assertIsNone(ids)
        self.assertEqual(reason, "not_found")

    def test_all_parts(self):
        ids, reason = self.resolver.resolve("", True)
        self.assertEqual(ids, ["P1", "P2", "P3", "P4"])

    def test_part_id_in_parenthetical_description(self):
        """Model-added disambiguation like '长号 (Trombone, P3)' resolves to P3."""
        ids, reason = self.resolver.resolve("长号 (Trombone, P3)", False)
        self.assertEqual(ids, ["P3"])
        self.assertEqual(reason, "id_in_description")

    def test_part_id_after_comma(self):
        ids, reason = self.resolver.resolve("Trombone, P3", False)
        self.assertEqual(ids, ["P3"])
        self.assertEqual(reason, "id_in_description")

    def test_part_id_with_slash(self):
        ids, reason = self.resolver.resolve("Trumpet 1 / P1", False)
        self.assertEqual(ids, ["P1"])
        self.assertEqual(reason, "id_in_description")

    def test_chinese_with_bb_trumpet_and_part_id(self):
        ids, reason = self.resolver.resolve("Bb小号 (Trumpet 1 / P1)", False)
        self.assertEqual(ids, ["P1"])
        self.assertEqual(reason, "id_in_description")

    def test_unknown_part_id_not_found(self):
        ids, reason = self.resolver.resolve("P99", False)
        self.assertIsNone(ids)
        self.assertEqual(reason, "not_found")

    def test_unknown_part_id_in_description_not_found(self):
        ids, reason = self.resolver.resolve("不存在的 P99", False)
        self.assertIsNone(ids)
        self.assertEqual(reason, "not_found")


class TestMeasureResolver(unittest.TestCase):
    def setUp(self):
        self.score = make_test_score()

    def test_range_resolved(self):
        start, end, reason = MeasureResolver.resolve("32", "48", ["P1"], self.score)
        self.assertEqual(start, 32)
        self.assertEqual(end, 48)
        self.assertEqual(reason, "resolved")

    def test_single_measure(self):
        start, end, reason = MeasureResolver.resolve("10", None, ["P1"], self.score)
        self.assertEqual(start, 10)
        self.assertEqual(end, 10)

    def test_full_range_default(self):
        start, end, reason = MeasureResolver.resolve(None, None, ["P1"], self.score)
        self.assertEqual(start, 1)
        self.assertEqual(end, 50)
        self.assertEqual(reason, "full_range")

    def test_start_greater_than_end(self):
        start, end, reason = MeasureResolver.resolve("48", "32", ["P1"], self.score)
        self.assertIsNone(start)
        self.assertIn("start_greater_than_end", reason)

    def test_measure_not_found(self):
        start, end, reason = MeasureResolver.resolve("100", "100", ["P1"], self.score)
        self.assertIsNone(start)
        self.assertIn("measure_not_found", reason)

    def test_nonstandard_measure_number(self):
        # Rename P1 measure 2 to display number "X1" and resolve by display number.
        score = make_test_score()
        score.get_part("P1").measures[1].number = "X1"
        start, end, reason = MeasureResolver.resolve("1", "X1", ["P1"], score)
        self.assertEqual(start, 1)
        self.assertEqual(end, 2)
        self.assertEqual(reason, "resolved")


class TestIntervalResolver(unittest.TestCase):
    def test_major_second_up(self):
        self.assertEqual(
            IntervalResolver.resolve("大二度", "up"),
            Interval(2, "M", 1),
        )

    def test_minor_third_down(self):
        self.assertEqual(
            IntervalResolver.resolve("小三度", "down"),
            Interval(3, "m", -1),
        )

    def test_octave(self):
        self.assertEqual(
            IntervalResolver.resolve("一个八度", "up"),
            Interval(8, "P", 1),
        )

    def test_english_major_third(self):
        self.assertEqual(
            IntervalResolver.resolve("major third", "up"),
            Interval(3, "M", 1),
        )

    def test_unsupported_interval(self):
        self.assertIsNone(IntervalResolver.resolve("增四度", "up"))


# ---------------------------------------------------------------------------
# Status-semantics regression tests (V1.1)
# ---------------------------------------------------------------------------

class TestStatusSemantics(unittest.TestCase):
    """Deterministic normalization of model status for non-existent parts.

    The model may return needs_clarification for a part that does not exist in
    the score. If the user request is otherwise complete, the resolver should
    classify it as invalid instead of asking again. This must be generic: no
    hardcoding of instruments, part ids, or source text.
    """

    def setUp(self):
        self.score = make_test_score()
        self.resolver = TransposeIntentResolver()

    def _resolve(self, intent: TransposeIntent) -> TransposeIntentResult:
        return self.resolver.resolve(intent, self.score)

    def _make_complete_interval_intent(
        self,
        part_description: str,
        status: str = "needs_clarification",
    ) -> TransposeIntent:
        return TransposeIntent(
            status=status,
            operation="transpose",
            direction="up",
            interval_description="八度",
            part_description=part_description,
            confidence=0.9,
            source_text=f"把{part_description}升八度",
        )

    def test_nonexistent_horn_from_model_clarification_is_invalid(self):
        intent = self._make_complete_interval_intent("圆号")
        result = self._resolve(intent)
        self.assertEqual(result.status, "invalid")
        self.assertIn("圆号", result.clarification_question)

    def test_nonexistent_arbitrary_instrument_is_invalid(self):
        intent = self._make_complete_interval_intent("Violin")
        result = self._resolve(intent)
        self.assertEqual(result.status, "invalid")
        self.assertIn("Violin", result.clarification_question)

    def test_nonexistent_part_id_is_invalid(self):
        intent = self._make_complete_interval_intent("P99")
        result = self._resolve(intent)
        self.assertEqual(result.status, "invalid")
        self.assertIn("P99", result.clarification_question)

    def test_nonexistent_instrument_from_ready_intent_is_invalid(self):
        intent = self._make_complete_interval_intent("小提琴", status="ready")
        result = self._resolve(intent)
        self.assertEqual(result.status, "invalid")

    def test_ambiguous_trumpet_stays_needs_clarification(self):
        # Two trumpets exist; "小号" cannot be resolved uniquely.
        intent = self._make_complete_interval_intent("小号")
        result = self._resolve(intent)
        self.assertEqual(result.status, "needs_clarification")

    def test_vague_request_stays_needs_clarification(self):
        # No part, no interval: user did not provide enough information.
        intent = TransposeIntent(
            status="needs_clarification",
            operation="transpose",
            direction="down",
            interval_description=None,
            part_description=None,
            clarification_question="请具体说明降低的音程。",
            confidence=0.25,
            source_text="后面一点降一点",
        )
        result = self._resolve(intent)
        self.assertEqual(result.status, "needs_clarification")

    def test_existing_part_not_overridden_when_model_asks_clarification(self):
        # If the part exists, preserve the model's needs_clarification.
        intent = self._make_complete_interval_intent("长号")
        result = self._resolve(intent)
        self.assertEqual(result.status, "needs_clarification")

    def test_existing_trombone_ready_remains_ready(self):
        intent = self._make_complete_interval_intent("长号", status="ready")
        result = self._resolve(intent)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.request.part_ids, ["P3"])


# ---------------------------------------------------------------------------
# LLM provider tests (no real API)
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
        return AIResponse(
            content=item,
            model="fake",
            confidence=0.9,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class TestLLMIntentProvider(unittest.TestCase):
    def test_parses_valid_json(self):
        client = FakeAIClient('''
        {
          "status": "ready",
          "operation": "transpose",
          "direction": "up",
          "interval_description": "大二度",
          "part_description": "P1",
          "is_all_parts": false,
          "confidence": 0.95
        }
        ''')
        provider = LLMIntentProvider(client)
        context = IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )
        intent = provider.parse_transpose("把P1升大二度", context)
        self.assertEqual(intent.status, "ready")
        self.assertEqual(intent.operation, "transpose")
        self.assertEqual(intent.interval_description, "大二度")
        self.assertEqual(intent.part_description, "p1")

    def test_invalid_json_returns_provider_error(self):
        client = FakeAIClient("not json at all")
        provider = LLMIntentProvider(client)
        context = IntentContext()
        intent = provider.parse_transpose("升大二度", context)
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.confidence, 0.0)

    def test_empty_content_returns_provider_error(self):
        client = FakeAIClient("")
        provider = LLMIntentProvider(client)
        context = IntentContext()
        intent = provider.parse_transpose("升大二度", context)
        self.assertEqual(intent.status, "provider_error")
        self.assertIn("empty", intent.clarification_question.lower())

    def test_unknown_status_in_valid_json_returns_invalid(self):
        client = FakeAIClient('{"status": "magic_status"}')
        provider = LLMIntentProvider(client)
        context = IntentContext()
        intent = provider.parse_transpose("升大二度", context)
        self.assertEqual(intent.status, "invalid")

    def test_retries_once_on_empty_response(self):
        client = FakeAIClient(["", '{"status": "ready", "is_all_parts": true, "confidence": 0.9}'])
        provider = LLMIntentProvider(client)
        context = IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )
        intent = provider.parse_transpose("整首升大二度", context)
        self.assertEqual(intent.status, "ready")
        self.assertEqual(client.call_count, 2)

    def test_provider_error_after_retry_exhausted(self):
        client = FakeAIClient(["", ""])
        provider = LLMIntentProvider(client, max_retries=1)
        context = IntentContext()
        intent = provider.parse_transpose("升大二度", context)
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(client.call_count, 2)

    def test_strips_markdown_fences(self):
        client = FakeAIClient('''```json
        {
          "status": "needs_clarification",
          "clarification_question": "Which part?"
        }
        ```''')
        provider = LLMIntentProvider(client)
        context = IntentContext()
        intent = provider.parse_transpose("升大二度", context)
        self.assertEqual(intent.status, "needs_clarification")
        self.assertEqual(intent.clarification_question, "Which part?")

    def test_empty_content_has_error_reason(self):
        client = FakeAIClient("")
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, EMPTY_CONTENT)
        self.assertEqual(len(intent.diagnostics), 1)
        self.assertTrue(intent.diagnostics[0].content_empty)

    def test_malformed_json_has_error_reason(self):
        client = FakeAIClient("not json")
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, MALFORMED_JSON)
        self.assertTrue(intent.diagnostics[0].json_parse_failed)

    def test_non_dict_json_has_schema_mismatch_reason(self):
        client = FakeAIClient('["unexpected"]')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, SCHEMA_MISMATCH)

    def test_client_error_maps_to_provider_error(self):
        attempt = ProviderAttempt(
            attempt=1,
            http_status=500,
            exception_type="HTTPError",
            error_detail="internal server error",
        )
        client = FakeAIClient(AIProviderError("boom", attempt=attempt))
        provider = LLMIntentProvider(client)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, HTTP_ERROR)
        self.assertEqual(intent.diagnostics[0].http_status, 500)

    def test_timeout_maps_to_provider_error(self):
        attempt = ProviderAttempt(
            attempt=1,
            exception_type="TimeoutError",
            is_timeout=True,
        )
        client = FakeAIClient(AIProviderError("timeout", attempt=attempt))
        provider = LLMIntentProvider(client)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, TIMEOUT)

    def test_retry_recovery_exposes_diagnostics(self):
        bad_attempt = ProviderAttempt(
            attempt=1,
            http_status=200,
            content_empty=True,
        )
        client = FakeAIClient([
            AIProviderError("empty", attempt=bad_attempt),
            '{"status": "ready", "is_all_parts": true, "confidence": 0.9}',
        ])
        provider = LLMIntentProvider(client)
        context = IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )
        intent = provider.parse_transpose("整首升大二度", context)
        self.assertEqual(intent.status, "ready")
        self.assertEqual(len(intent.diagnostics), 2)
        self.assertTrue(intent.diagnostics[0].content_empty)


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestIntentValidator(unittest.TestCase):
    def setUp(self):
        self.validator = IntentValidator()
        self.score = make_test_score()

    def test_valid_interval_request(self):
        request = TransposeRequest(
            interval=Interval(2, "M"),
            part_ids=["P1"],
            measure_start=1,
            measure_end=10,
        )
        result = self.validator.validate_request(request, self.score)
        self.assertTrue(result.valid)

    def test_missing_interval_for_interval_operation(self):
        # TransposeRequest itself rejects a missing interval for INTERVAL operation.
        with self.assertRaises(ValueError):
            TransposeRequest(
                operation=TranspositionOperation.INTERVAL,
                interval=None,
                part_ids=["P1"],
            )

    def test_hallucinated_part_id(self):
        request = TransposeRequest(
            interval=Interval(2, "M"),
            part_ids=["P99"],
        )
        result = self.validator.validate_request(request, self.score)
        self.assertFalse(result.valid)
        self.assertIn("P99", result.reason)

    def test_measure_out_of_range(self):
        request = TransposeRequest(
            interval=Interval(2, "M"),
            part_ids=["P1"],
            measure_start=100,
            measure_end=100,
        )
        result = self.validator.validate_request(request, self.score)
        self.assertFalse(result.valid)

    def test_invalid_intent_status(self):
        intent = TransposeIntent(status="unknown_status")
        result = self.validator.validate_intent(intent)
        self.assertFalse(result.valid)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

class TestBuildIntentContext(unittest.TestCase):
    def test_builds_minimal_context(self):
        score = make_test_score()
        context = build_intent_context(score)
        self.assertEqual(len(context.available_parts), 4)
        self.assertEqual(context.min_measure, 1)
        self.assertEqual(context.max_measure, 50)
        self.assertTrue(len(context.supported_intervals) > 0)


# ---------------------------------------------------------------------------
# OpenAI-compatible client extraction
# ---------------------------------------------------------------------------

class TestOpenAICompatibleContentExtraction(unittest.TestCase):
    def test_extracts_message_content(self):
        choices = [{"message": {"content": "  hello  "}}]
        info = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(info["content"], "hello")
        self.assertEqual(info["source_field"], "content")
        self.assertFalse(info["has_reasoning_content"])
        self.assertFalse(info["has_tool_calls"])

    def test_falls_back_to_reasoning_content(self):
        choices = [{"message": {"content": None, "reasoning_content": "{\"status\": \"ready\"}"}}]
        info = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(info["content"], '{"status": "ready"}')
        self.assertEqual(info["source_field"], "reasoning_content")
        self.assertTrue(info["has_reasoning_content"])
        self.assertFalse(info["has_tool_calls"])

    def test_falls_back_to_tool_call_arguments(self):
        choices = [{
            "message": {
                "content": "",
                "tool_calls": [{"function": {"arguments": '{"status": "ready"}'}}],
            }
        }]
        info = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(info["content"], '{"status": "ready"}')
        self.assertEqual(info["source_field"], "tool_calls")
        self.assertFalse(info["has_reasoning_content"])
        self.assertTrue(info["has_tool_calls"])

    def test_returns_empty_for_missing_choices(self):
        info1 = OpenAICompatibleClient._extract_content([])
        self.assertEqual(info1["content"], "")
        info2 = OpenAICompatibleClient._extract_content(None)
        self.assertEqual(info2["content"], "")


# ---------------------------------------------------------------------------
# Malformed JSON classification
# ---------------------------------------------------------------------------

class TestMalformedJsonClassification(unittest.TestCase):
    def test_code_fence_wrapped(self):
        from ai.provider_diagnostics import (
            MALFORMED_CODE_FENCE_WRAPPED,
            classify_malformed_json,
        )
        text = '```json\n{"status": "ready"}\n```'
        self.assertEqual(
            classify_malformed_json(text, "content", False, False),
            MALFORMED_CODE_FENCE_WRAPPED,
        )

    def test_natural_language_wrapped(self):
        from ai.provider_diagnostics import (
            MALFORMED_NATURAL_LANGUAGE_WRAPPED,
            classify_malformed_json,
        )
        text = 'Here is the JSON: {"status": "ready"} Hope this helps.'
        self.assertEqual(
            classify_malformed_json(text, "content", False, False),
            MALFORMED_NATURAL_LANGUAGE_WRAPPED,
        )

    def test_multiple_objects(self):
        from ai.provider_diagnostics import (
            MALFORMED_MULTIPLE_OBJECTS,
            classify_malformed_json,
        )
        text = '{"a":1}{"b":2}'
        self.assertEqual(
            classify_malformed_json(text, "content", False, False),
            MALFORMED_MULTIPLE_OBJECTS,
        )

    def test_truncated(self):
        from ai.provider_diagnostics import (
            MALFORMED_TRUNCATED,
            classify_malformed_json,
        )
        text = '{"status": "ready"'
        self.assertEqual(
            classify_malformed_json(text, "content", False, False),
            MALFORMED_TRUNCATED,
        )

    def test_json_in_reasoning_content(self):
        from ai.provider_diagnostics import (
            MALFORMED_JSON_IN_REASONING_CONTENT,
            classify_malformed_json,
        )
        self.assertEqual(
            classify_malformed_json("", "reasoning_content", True, False),
            MALFORMED_JSON_IN_REASONING_CONTENT,
        )

    def test_empty_content_other_field(self):
        from ai.provider_diagnostics import (
            MALFORMED_EMPTY_CONTENT_OTHER_FIELD,
            classify_malformed_json,
        )
        self.assertEqual(
            classify_malformed_json("", "", False, True),
            MALFORMED_EMPTY_CONTENT_OTHER_FIELD,
        )

    def test_completely_invalid(self):
        from ai.provider_diagnostics import (
            MALFORMED_COMPLETELY_INVALID,
            classify_malformed_json,
        )
        self.assertEqual(
            classify_malformed_json("not json at all", "content", False, False),
            MALFORMED_COMPLETELY_INVALID,
        )

    def test_malformed_json_subtype_stored_on_attempt(self):
        client = FakeAIClient('not json at all')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, MALFORMED_JSON)
        self.assertFalse(hasattr(intent, "malformed_json_subtype"))
        self.assertEqual(len(intent.diagnostics), 1)
        self.assertEqual(intent.diagnostics[0].malformed_json_subtype, "completely_invalid")


# ---------------------------------------------------------------------------
# Deterministic JSON extraction unit tests
# ---------------------------------------------------------------------------

class TestJSONExtractor(unittest.TestCase):
    def test_clean_json_object(self):
        from ai.json_extraction import JSONExtractor

        text = '{"status": "ready", "confidence": 0.9}'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "none")
        self.assertEqual(result.failure_subtype, "")

    def test_strip_json_code_fence(self):
        from ai.json_extraction import JSONExtractor

        text = '```json\n{"status": "ready"}\n```'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "strip_fence")
        self.assertEqual(result.text, '{"status": "ready"}')

    def test_strip_generic_code_fence(self):
        from ai.json_extraction import JSONExtractor

        text = '```\n{"status": "ready"}\n```'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "strip_fence")

    def test_extract_json_from_prose_prefix(self):
        from ai.json_extraction import JSONExtractor

        text = 'Here is the parsed intent: {"status": "ready"}.'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "extract_embedded")
        self.assertEqual(result.text, '{"status": "ready"}')

    def test_extract_json_from_prose_suffix(self):
        from ai.json_extraction import JSONExtractor

        text = 'The result is {"status": "needs_clarification"}. Hope that helps.'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "extract_embedded")

    def test_extract_json_from_fenced_and_wrapped(self):
        from ai.json_extraction import JSONExtractor

        text = 'Sure! ```json\n{"status": "ready"}\n``` Done.'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.text, '{"status": "ready"}')

    def test_multiple_json_objects_rejected(self):
        from ai.json_extraction import JSONExtractor

        text = '{"status": "ready"}{"status": "ready"}'
        result = JSONExtractor.normalize(text)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_subtype, "multiple_objects")

    def test_multiple_json_objects_with_prose_rejected(self):
        from ai.json_extraction import JSONExtractor

        text = 'First: {"a":1} second: {"b":2}'
        result = JSONExtractor.normalize(text)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_subtype, "multiple_objects")

    def test_truncated_json_unrecoverable_missing_close(self):
        from ai.json_extraction import JSONExtractor

        text = '{"status": "ready"'
        result = JSONExtractor.normalize(text)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_subtype, "truncated")

    def test_truncated_json_unrecoverable_mid_string(self):
        from ai.json_extraction import JSONExtractor

        text = '{"status": "ready", "clarification_question": "What do you'
        result = JSONExtractor.normalize(text)
        self.assertFalse(result.success)
        self.assertEqual(result.failure_subtype, "truncated")

    def test_empty_content(self):
        from ai.json_extraction import JSONExtractor

        result = JSONExtractor.normalize("")
        self.assertFalse(result.success)
        self.assertEqual(result.action, "empty_content")
        self.assertEqual(result.failure_subtype, "empty_content")

    def test_completely_invalid(self):
        from ai.json_extraction import JSONExtractor

        result = JSONExtractor.normalize("not json at all")
        self.assertFalse(result.success)
        self.assertEqual(result.failure_subtype, "completely_invalid")

    def test_nested_braces_inside_strings(self):
        from ai.json_extraction import JSONExtractor

        text = '{"question": "What {is} this?", "status": "ready"}'
        result = JSONExtractor.normalize(text)
        self.assertTrue(result.success)
        self.assertEqual(result.action, "none")


# ---------------------------------------------------------------------------
# Provider normalization regression tests
# ---------------------------------------------------------------------------

class TestProviderNormalizationRegression(unittest.TestCase):
    def _context(self) -> IntentContext:
        return IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )

    def test_clean_json_in_content(self):
        client = FakeAIClient('{"status": "ready", "is_all_parts": true, "confidence": 0.9}')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("整首升大二度", self._context())
        self.assertEqual(intent.status, "ready")
        self.assertEqual(intent.diagnostics[0].extraction_action, "none")

    def test_clean_json_in_reasoning_content(self):
        choices = [{
            "message": {
                "content": "",
                "reasoning_content": '{"status": "ready", "is_all_parts": true, "confidence": 0.9}',
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "reasoning_content")
        self.assertEqual(extraction["extraction_action"], "none")
        self.assertTrue(extraction["has_reasoning_content"])

    def test_fenced_json_extracted(self):
        client = FakeAIClient('```json\n{"status": "ready", "is_all_parts": true, "confidence": 0.9}\n```')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("整首升大二度", self._context())
        self.assertEqual(intent.status, "ready")
        self.assertEqual(intent.diagnostics[0].extraction_action, "strip_fence")

    def test_prefix_suffix_prose_extracted(self):
        client = FakeAIClient(
            'Here is the intent: {"status": "ready", "operation": "transpose", '
            '"direction": "up", "interval_description": "大二度", "is_all_parts": true, '
            '"confidence": 0.9}. Let me know if you need anything else.'
        )
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("整首升大二度", self._context())
        self.assertEqual(intent.status, "ready")
        self.assertEqual(intent.diagnostics[0].extraction_action, "extract_embedded")

    def test_multiple_objects_returns_provider_error(self):
        client = FakeAIClient('{"status": "ready"}{"status": "ready"}')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, MALFORMED_JSON)
        self.assertEqual(intent.diagnostics[0].malformed_json_subtype, "multiple_objects")
        self.assertEqual(intent.diagnostics[0].extraction_action, "multiple_objects")

    def test_truncated_unrecoverable_returns_provider_error(self):
        client = FakeAIClient('{"status": "ready"')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, MALFORMED_JSON)
        self.assertEqual(intent.diagnostics[0].malformed_json_subtype, "truncated")
        self.assertEqual(intent.diagnostics[0].extraction_action, "truncated")

    def test_empty_content_returns_provider_error(self):
        client = FakeAIClient("")
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, EMPTY_CONTENT)

    def test_malformed_json_subtype_preserved(self):
        client = FakeAIClient('not json at all')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, MALFORMED_JSON)
        self.assertEqual(intent.diagnostics[0].malformed_json_subtype, "completely_invalid")

    def test_valid_json_schema_mismatch(self):
        client = FakeAIClient('["unexpected"]')
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("升大二度", IntentContext())
        self.assertEqual(intent.status, "provider_error")
        self.assertEqual(intent.error_reason, SCHEMA_MISMATCH)

    def test_tool_calls_structured_arguments(self):
        choices = [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "function": {
                        "arguments": '{"status": "ready", "is_all_parts": true, "confidence": 0.9}'
                    }
                }],
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "tool_calls")
        self.assertEqual(extraction["extraction_action"], "none")
        self.assertTrue(extraction["has_tool_calls"])
        self.assertEqual(
            json.loads(extraction["content"]).get("status"),
            "ready",
        )

    def test_source_priority_content_over_reasoning(self):
        choices = [{
            "message": {
                "content": '{"status": "ready"}',
                "reasoning_content": '{"status": "needs_clarification"}',
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "content")
        self.assertEqual(extraction["content"], '{"status": "ready"}')

    def test_source_priority_reasoning_when_content_empty(self):
        choices = [{
            "message": {
                "content": "",
                "reasoning_content": '{"status": "ready"}',
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "reasoning_content")
        self.assertEqual(extraction["content"], '{"status": "ready"}')

    def test_source_priority_tool_calls_highest(self):
        choices = [{
            "message": {
                "content": '{"status": "invalid"}',
                "reasoning_content": '{"status": "needs_clarification"}',
                "tool_calls": [{
                    "function": {
                        "arguments": '{"status": "ready"}'
                    }
                }],
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "tool_calls")
        self.assertEqual(extraction["content"], '{"status": "ready"}')

    def test_reasoning_content_with_prose_extracted(self):
        choices = [{
            "message": {
                "content": "",
                "reasoning_content": 'The user wants: {"status": "ready", "is_all_parts": true, "confidence": 0.9}',
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "reasoning_content")
        self.assertEqual(extraction["extraction_action"], "extract_embedded")
        self.assertEqual(json.loads(extraction["content"]).get("status"), "ready")

    def test_content_garbage_reasoning_clean_cascade(self):
        choices = [{
            "message": {
                "content": "not json at all",
                "reasoning_content": '{"status": "ready"}',
            }
        }]
        extraction = OpenAICompatibleClient._extract_content(choices)
        self.assertEqual(extraction["source_field"], "reasoning_content")
        self.assertEqual(extraction["extraction_action"], "none")


# ---------------------------------------------------------------------------
# Semantic-null normalization tests
# ---------------------------------------------------------------------------

class TestSemanticNullNormalization(unittest.TestCase):
    """Deterministic lexical-null normalization for nullable description fields."""

    def _context(self) -> IntentContext:
        return IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )

    def _build_json(
        self,
        measure_start=None,
        measure_end=None,
        interval="大二度",
        part="P1",
        basis=None,
        clarification=None,
    ) -> str:
        data = {
            "status": "ready",
            "operation": "transpose",
            "direction": "up",
            "interval_description": interval,
            "part_description": part,
            "measure_start_description": measure_start,
            "measure_end_description": measure_end,
            "is_all_parts": False,
            "basis": basis,
            "clarification_question": clarification,
            "confidence": 0.95,
        }
        return json.dumps(data, ensure_ascii=False)

    def test_json_null_measure_descriptions_become_none(self):
        client = FakeAIClient(self._build_json(measure_start=None, measure_end=None))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_start_description)
        self.assertIsNone(intent.measure_end_description)

    def test_string_null_measure_end_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_start=None, measure_end="null"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_uppercase_null_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end="NULL"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_padded_none_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end=" none "))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_empty_string_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end=""))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_whitespace_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end="   \t\n  "))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_n_a_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end="N/A"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_nil_normalized_to_none(self):
        client = FakeAIClient(self._build_json(measure_end="nil"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.measure_end_description)

    def test_normal_measure_description_unchanged(self):
        client = FakeAIClient(self._build_json(measure_start="32", measure_end="48"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertEqual(intent.measure_start_description, "32")
        self.assertEqual(intent.measure_end_description, "48")

    def test_phrase_containing_none_not_normalized(self):
        client = FakeAIClient(self._build_json(measure_end="measure none"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertEqual(intent.measure_end_description, "measure none")

    def test_phrase_containing_null_not_normalized(self):
        client = FakeAIClient(self._build_json(interval="null interval"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertEqual(intent.interval_description, "null interval")

    def test_null_interval_still_caught_by_resolver(self):
        """Required interval field normalized to None must not fake success."""
        client = FakeAIClient(self._build_json(interval="null"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.interval_description)
        # Resolver should ask for clarification because interval is missing.
        resolver = TransposeIntentResolver()
        score = make_test_score()
        result = resolver.resolve(intent, score)
        self.assertEqual(result.status, "needs_clarification")

    def test_null_basis_normalized_to_none(self):
        client = FakeAIClient(self._build_json(basis="NULL"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertIsNone(intent.basis)

    def test_null_clarification_question_becomes_empty(self):
        client = FakeAIClient(self._build_json(clarification="none"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertEqual(intent.clarification_question, "")

    def test_clarification_question_preserved_case(self):
        client = FakeAIClient(self._build_json(clarification="Which PART?"))
        provider = LLMIntentProvider(client, max_retries=0)
        intent = provider.parse_transpose("把P1升大二度", self._context())
        self.assertEqual(intent.clarification_question, "Which PART?")

    def test_iteration_four_exact_reproduction_becomes_ready(self):
        """The exact K3 iteration 4 response after semantic-null normalization."""
        data = {
            "status": "ready",
            "operation": "transpose",
            "direction": "up",
            "interval_description": "major second / 大二度",
            "part_description": "整首",
            "measure_start_description": None,
            "measure_end_description": "null",
            "is_all_parts": True,
            "basis": None,
            "clarification_question": None,
            "confidence": 0.95,
        }
        client = FakeAIClient(json.dumps(data, ensure_ascii=False))
        provider = LLMIntentProvider(client, max_retries=0)
        context = IntentContext(
            available_parts=[{"id": "P1", "name": "Trumpet"}],
            min_measure=1,
            max_measure=50,
            supported_intervals=["大二度"],
        )
        intent = provider.parse_transpose("把整首升大二度", context)
        self.assertIsNone(intent.measure_end_description)
        resolver = TransposeIntentResolver()
        score = make_test_score()
        result = resolver.resolve(intent, score)
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.request.measure_start, 1)
        self.assertEqual(result.request.measure_end, 50)


if __name__ == "__main__":
    unittest.main()
