"""AI intent providers for transpose requests.

The parser layer is deliberately thin:
- ``AIIntentProvider`` defines the interface.
- ``LLMIntentProvider`` wraps any ``AIClient`` and asks the model to emit JSON.
- ``MockIntentProvider`` returns deterministic responses for tests.

No provider modifies ScoreIR. They only produce ``TransposeIntent`` candidates.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Any

from score_engine.transposition.interval import Interval

from . import AIClient, AIProviderError, AIRequest, AIResponse
from .intent_schema import IntentContext, TransposeIntent
from .json_extraction import JSONExtractor
from .provider_diagnostics import (
    EMPTY_CONTENT,
    MALFORMED_JSON,
    ProviderAttempt,
    SCHEMA_MISMATCH,
    UNKNOWN_PROVIDER_ERROR,
    classify_malformed_json,
    error_reason_from_attempt,
)


class AIIntentProvider(ABC):
    """Abstract provider that turns natural language into a transpose intent."""

    @abstractmethod
    def parse_transpose(self, user_text: str, context: IntentContext) -> TransposeIntent:
        """Return a structured transpose intent candidate."""
        ...


@dataclass
class LLMIntentProvider(AIIntentProvider):
    """Provider that uses an LLM via any ``AIClient`` implementation.

    The prompt is small and contains only:
    - the user's request
    - a compact part table
    - min/max measure numbers
    - supported interval vocabulary
    - the required JSON schema

    Robustness features:
    - Forces structured output via ``response_format`` (JSON Object by default).
    - Bounded single retry on provider/parse failures.
    - Distinguishes transient provider errors (``provider_error``) from genuine
      user-invalid requests (``invalid``).
    - Returns structured per-attempt diagnostics (no prompt or API key exposed).
    """

    client: AIClient
    model: str = ""
    max_tokens: int = 1024
    response_format_mode: str = "json_object"  # "json_object" or "json_schema"
    disable_thinking: bool = True
    max_retries: int = 1

    # Lexical values that should be treated as semantic null in nullable
    # description fields. Whole-value match only (trim + case-insensitive).
    _SEMANTIC_NULL_LITERALS: frozenset[str] = frozenset(
        {"null", "none", "nil", "n/a"}
    )

    @classmethod
    def _normalize_nullable(cls, value) -> str | None:
        """Return ``None`` for lexical null-ish values, else the original value.

        Only whole-field matches are normalized. Values like "measure none"
        or "null interval" are preserved so natural-language content is not
        accidentally erased.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower() in cls._SEMANTIC_NULL_LITERALS:
            return None
        return text

    def parse_transpose(self, user_text: str, context: IntentContext) -> TransposeIntent:
        prompt = self._build_prompt(user_text, context)
        response_format = self._build_response_format()
        extra_body = self._build_extra_body()
        request = AIRequest(
            prompt=prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            response_format=response_format,
            extra_body=extra_body,
        )

        attempts: list[ProviderAttempt] = []
        last_error: Exception | None = None
        max_attempts = max(1, self.max_retries + 1)

        for attempt_idx in range(1, max_attempts + 1):
            attempt = ProviderAttempt(attempt=attempt_idx)
            response: AIResponse | None = None

            try:
                response = self.client.call(request)
            except AIProviderError as exc:
                attempt = exc.attempt
                if not isinstance(attempt, ProviderAttempt):
                    attempt = ProviderAttempt(attempt=attempt_idx)
                attempt.attempt = attempt_idx
                attempts.append(attempt)
                last_error = exc
                continue
            except Exception as exc:
                attempt.exception_type = type(exc).__name__
                attempt.error_detail = str(exc)[:500]
                attempts.append(attempt)
                last_error = exc
                continue

            # Successful HTTP response; populate attempt telemetry.
            attempt.model = response.model or ""
            attempt.usage = response.usage or {}
            if response.diagnostics is not None and isinstance(response.diagnostics, ProviderAttempt):
                attempt.latency_ms = response.diagnostics.latency_ms
                attempt.http_status = response.diagnostics.http_status
                attempt.has_reasoning_content = response.diagnostics.has_reasoning_content
                attempt.has_tool_calls = response.diagnostics.has_tool_calls
                attempt.source_field = response.diagnostics.source_field
                attempt.raw_content_head = response.diagnostics.raw_content_head
                attempt.finish_reason = response.diagnostics.finish_reason
                attempt.response_body_head = response.diagnostics.response_body_head

            intent = self._parse_response(response, user_text, attempt)
            if intent.status != "provider_error":
                # Surface the full attempt chain so callers can see retries.
                if attempts:
                    intent = replace(
                        intent,
                        diagnostics=tuple(attempts) + intent.diagnostics,
                    )
                return intent

            attempts.extend(intent.diagnostics)
            last_error = Exception(intent.clarification_question)

        # All retries exhausted: surface as provider_error with diagnostics.
        final_attempt = attempts[-1] if attempts else ProviderAttempt(attempt=max_attempts)
        error_reason = self._resolve_error_reason(attempts, final_attempt)
        error_msg = f"LLM provider failed after {len(attempts)} attempt(s)"
        if last_error:
            error_msg = f"{error_msg}: {last_error}"

        return TransposeIntent(
            status="provider_error",
            error_reason=error_reason,
            clarification_question=error_msg,
            confidence=0.0,
            source_text=user_text,
            diagnostics=tuple(attempts),
        )

    def _build_prompt(self, user_text: str, context: IntentContext) -> str:
        parts_json = json.dumps(context.available_parts, ensure_ascii=False, indent=2)
        intervals_json = json.dumps(context.supported_intervals, ensure_ascii=False)

        schema = {
            "status": "ready | needs_clarification | unsupported | invalid",
            "operation": "transpose | written_to_sounding | sounding_to_written | null",
            "direction": "up | down | null",
            "interval_description": "string or null",
            "part_description": "string or null",
            "measure_start_description": "string or null",
            "measure_end_description": "string or null",
            "is_all_parts": "boolean",
            "basis": "written | sounding | concert | null",
            "clarification_question": "string or null",
            "confidence": "0.0 to 1.0",
        }

        return (
            "You are a music-score intent parser. Extract the user's transpose "
            "request into JSON. Do not guess; if the request is ambiguous, "
            "return status=needs_clarification and a helpful question in the "
            "same language as the user. If the request is not a transpose "
            "operation or asks for an unsupported interval, return "
            "status=unsupported. "
            "Transposition to a specific target key (e.g., '移到降E大调', "
            "'移成D大调', 'transpose to Eb major') is not supported; return "
            "status=unsupported.\n\n"
            f"Available parts:\n{parts_json}\n\n"
            f"Measure numbers range from {context.min_measure} to {context.max_measure}.\n\n"
            f"Supported intervals: {intervals_json}\n\n"
            "Direction keywords:\n"
            "- up: 升, 上移, 提高, up, raise\n"
            "- down: 降, 下移, 降低, down, lower\n\n"
            "Basis keywords:\n"
            "- written_to_sounding: 实际音高, 实际听响, concert pitch, sounding pitch\n"
            "- sounding_to_written: 记谱音高, written pitch\n"
            "- If no basis is given, default to operation=transpose (interval transposition).\n\n"
            "Return ONLY a single JSON object matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"User request: {user_text}\n"
        )

    def _build_response_format(self) -> dict[str, Any] | None:
        """Return the OpenAI-compatible response_format payload.

        Defaults to JSON Object for broad relay compatibility. JSON Schema is
        available via ``response_format_mode="json_schema"`` when the relay
        supports OpenAI Structured Outputs.
        """
        if self.response_format_mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "transpose_intent",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": [
                                    "ready",
                                    "needs_clarification",
                                    "unsupported",
                                    "invalid",
                                ],
                            },
                            "operation": {
                                "type": ["string", "null"],
                                "enum": [
                                    "transpose",
                                    "written_to_sounding",
                                    "sounding_to_written",
                                    None,
                                ],
                            },
                            "direction": {
                                "type": ["string", "null"],
                                "enum": ["up", "down", None],
                            },
                            "interval_description": {"type": ["string", "null"]},
                            "part_description": {"type": ["string", "null"]},
                            "measure_start_description": {"type": ["string", "null"]},
                            "measure_end_description": {"type": ["string", "null"]},
                            "is_all_parts": {"type": "boolean"},
                            "basis": {
                                "type": ["string", "null"],
                                "enum": ["written", "sounding", "concert", None],
                            },
                            "clarification_question": {"type": ["string", "null"]},
                            "confidence": {"type": "number"},
                        },
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                },
            }
        if self.response_format_mode == "json_object":
            return {"type": "json_object"}
        return None

    def _build_extra_body(self) -> dict[str, Any] | None:
        """Best-effort provider knobs to reduce reasoning noise.

        Only injects Moonshot/Kimi-specific parameters when the configured
        model looks like a Kimi model, so strict OpenAI-compatible relays for
        other providers are not bothered with unknown fields.
        """
        if not self.disable_thinking:
            return None
        model = (self.model or "").lower()
        if not model and hasattr(self.client, "model"):
            model = (self.client.model or "").lower()
        if "kimi" not in model:
            return None
        # Moonshot/Kimi exposes ``enable_thinking``.
        return {"enable_thinking": False}

    def _parse_response(
        self,
        response: AIResponse,
        user_text: str,
        attempt: ProviderAttempt,
    ) -> TransposeIntent:
        raw_content = (response.content or "").strip()
        attempt.content_empty = not raw_content

        if not raw_content:
            attempt.error_reason = EMPTY_CONTENT
            attempt.error_detail = "AI model returned an empty response."
            return TransposeIntent(
                status="provider_error",
                error_reason=EMPTY_CONTENT,
                clarification_question=attempt.error_detail,
                confidence=0.0,
                source_text=user_text,
                diagnostics=(attempt,),
            )

        # Deterministic normalization: fences, prose wrapping, single-object
        # isolation, and conservative truncation checks.
        extraction = JSONExtractor.normalize(raw_content)
        attempt.extraction_action = extraction.action

        if not extraction.success:
            attempt.json_parse_failed = True
            attempt.error_reason = MALFORMED_JSON
            subtype = classify_malformed_json(
                extraction.text,
                attempt.source_field,
                attempt.has_reasoning_content,
                attempt.has_tool_calls,
                extraction.action,
            )
            attempt.malformed_json_subtype = subtype
            attempt.error_detail = f"AI response was not valid JSON ({subtype})"
            return TransposeIntent(
                status="provider_error",
                error_reason=MALFORMED_JSON,
                clarification_question=attempt.error_detail,
                confidence=0.0,
                source_text=user_text,
                diagnostics=(attempt,),
            )

        content = extraction.text
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            # Defensive: the extractor already validated, but normalize again.
            attempt.json_parse_failed = True
            attempt.error_reason = MALFORMED_JSON
            subtype = classify_malformed_json(
                content,
                attempt.source_field,
                attempt.has_reasoning_content,
                attempt.has_tool_calls,
                extraction.action,
            )
            attempt.malformed_json_subtype = subtype
            attempt.error_detail = f"AI response was not valid JSON ({subtype}): {exc}"
            return TransposeIntent(
                status="provider_error",
                error_reason=MALFORMED_JSON,
                clarification_question=attempt.error_detail,
                confidence=0.0,
                source_text=user_text,
                diagnostics=(attempt,),
            )

        if not isinstance(data, dict):
            attempt.json_parse_failed = True
            attempt.error_reason = SCHEMA_MISMATCH
            attempt.malformed_json_subtype = "schema_mismatch"
            attempt.error_detail = "AI response was not a JSON object."
            return TransposeIntent(
                status="provider_error",
                error_reason=SCHEMA_MISMATCH,
                clarification_question=attempt.error_detail,
                confidence=0.0,
                source_text=user_text,
                diagnostics=(attempt,),
            )

        # Preserve the extracted raw JSON for diagnostics (no API key here).
        attempt.extracted_json = dict(data)

        # Deterministic semantic-null normalization: treat lexical null-ish
        # strings ("null", "none", "nil", "n/a", whitespace) as None in
        # nullable description fields. Preserve the existing lowercasing for
        # fields that the resolver expects to be normalized.
        interval_description = self._normalize(self._normalize_nullable(data.get("interval_description")))
        part_description = self._normalize(self._normalize_nullable(data.get("part_description")))
        measure_start_description = self._normalize(self._normalize_nullable(data.get("measure_start_description")))
        measure_end_description = self._normalize(self._normalize_nullable(data.get("measure_end_description")))
        basis = self._normalize(self._normalize_nullable(data.get("basis")))
        clarification_question = self._normalize_nullable(data.get("clarification_question")) or ""

        return TransposeIntent(
            status=self._normalize_status(data.get("status")),
            operation=self._normalize(data.get("operation")),
            direction=self._normalize(data.get("direction")),
            interval_description=interval_description,
            part_description=part_description,
            measure_start_description=measure_start_description,
            measure_end_description=measure_end_description,
            is_all_parts=bool(data.get("is_all_parts", False)),
            basis=basis,
            clarification_question=clarification_question,
            confidence=float(data.get("confidence", 0.0)),
            source_text=user_text,
            diagnostics=(attempt,),
        )

    @staticmethod
    def _resolve_error_reason(
        attempts: list[ProviderAttempt],
        final_attempt: ProviderAttempt,
    ) -> str:
        """Pick the most specific machine-readable reason from the attempt chain."""
        # Content-level reasons from parsed responses are the most actionable.
        for attempt in attempts:
            if attempt.error_reason:
                return attempt.error_reason
        # Fallback to reason derived from the final failed HTTP attempt.
        return error_reason_from_attempt(final_attempt)

    @staticmethod
    def _normalize(value) -> str | None:
        if value is None:
            return None
        value = str(value).strip().lower()
        return value if value else None

    @staticmethod
    def _normalize_status(value) -> str:
        allowed = {"ready", "needs_clarification", "unsupported", "invalid", "provider_error"}
        value = str(value or "invalid").strip().lower()
        return value if value in allowed else "invalid"


@dataclass
class MockIntentProvider(AIIntentProvider):
    """Deterministic provider for tests. Returns pre-configured intents."""

    response_map: dict[str, TransposeIntent]
    default: TransposeIntent | None = None

    def parse_transpose(self, user_text: str, context: IntentContext) -> TransposeIntent:
        return self.response_map.get(user_text, self.default or TransposeIntent())
