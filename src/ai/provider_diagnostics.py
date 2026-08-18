"""Structured diagnostics for AI provider calls.

This module provides machine-readable error reasons and per-attempt telemetry
so that intermittent provider failures can be classified without leaking
sensitive request data (prompts, API keys) in logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MACHINE_READABLE_ERROR_REASONS = {
    "http_error",
    "timeout",
    "empty_response",
    "empty_content",
    "malformed_json",
    "schema_mismatch",
    "unsupported_response_format",
    "unknown_provider_error",
}


@dataclass
class ProviderAttempt:
    """Telemetry for a single provider call attempt."""

    attempt: int
    latency_ms: float = 0.0
    http_status: int | None = None
    exception_type: str | None = None
    is_timeout: bool = False
    response_body_empty: bool = True
    content_empty: bool = True
    has_reasoning_content: bool = False
    has_tool_calls: bool = False
    json_parse_failed: bool = False
    # Where the usable text was taken from: content / reasoning_content /
    # tool_calls / text / unknown.
    source_field: str = ""
    # What deterministic extraction step produced the final candidate, e.g.
    # none / strip_fence / extract_embedded / empty / multiple_objects /
    # truncated / completely_invalid.
    extraction_action: str = ""
    # Privacy-safe preview of the model output before normalization.
    raw_content_head: str = ""
    raw_content_tail: str = ""
    # Privacy-safe preview of the model's reasoning_content, when present.
    reasoning_content_head: str = ""
    reasoning_content_tail: str = ""
    # Privacy-safe preview of the full HTTP response body.
    response_body_head: str = ""
    response_body_tail: str = ""
    finish_reason: str | None = None
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    # The parsed JSON object extracted from the model output, when available.
    extracted_json: dict[str, Any] = field(default_factory=dict)
    error_reason: str = ""
    error_detail: str = ""
    malformed_json_subtype: str = ""


# Machine-readable reasons for provider_error.
HTTP_ERROR = "http_error"
TIMEOUT = "timeout"
EMPTY_RESPONSE = "empty_response"
EMPTY_CONTENT = "empty_content"
MALFORMED_JSON = "malformed_json"
SCHEMA_MISMATCH = "schema_mismatch"
UNSUPPORTED_RESPONSE_FORMAT = "unsupported_response_format"
UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"

# Subtypes for malformed_json.
MALFORMED_COMPLETELY_INVALID = "completely_invalid"
MALFORMED_CODE_FENCE_WRAPPED = "code_fence_wrapped"
MALFORMED_NATURAL_LANGUAGE_WRAPPED = "natural_language_wrapped"
MALFORMED_MULTIPLE_OBJECTS = "multiple_objects"
MALFORMED_TRUNCATED = "truncated"
MALFORMED_JSON_IN_REASONING_CONTENT = "json_in_reasoning_content"
MALFORMED_JSON_IN_TOOL_CALLS = "json_in_tool_calls"
MALFORMED_EMPTY_CONTENT_OTHER_FIELD = "empty_content_other_field"
MALFORMED_SCHEMA_MISMATCH = "schema_mismatch"
MALFORMED_OTHER = "other"


def _preview(text: str, limit: int = 300) -> str:
    """Return a privacy-safe head/tail preview of a string."""
    if not text:
        return ""
    if len(text) <= 2 * limit:
        return text
    return text[:limit] + "\n...\n" + text[-limit:]


def classify_malformed_json(
    content: str,
    source_field: str,
    has_reasoning_content: bool,
    has_tool_calls: bool,
    extraction_action: str = "",
) -> str:
    """Classify why the model output could not be parsed as a JSON object.

    This is intentionally conservative: it reports what the text looks like
    without trying to recover from it. When ``extraction_action`` is supplied
    by the deterministic ``JSONExtractor``, it is used as the primary signal.
    """
    # Prefer the deterministic extractor's own classification when available.
    if extraction_action:
        action_to_subtype = {
            "empty": MALFORMED_COMPLETELY_INVALID,
            "multiple_objects": MALFORMED_MULTIPLE_OBJECTS,
            "truncated": MALFORMED_TRUNCATED,
            "completely_invalid": MALFORMED_COMPLETELY_INVALID,
        }
        subtype = action_to_subtype.get(extraction_action)
        if subtype:
            if source_field == "reasoning_content":
                return MALFORMED_JSON_IN_REASONING_CONTENT
            if source_field == "tool_calls":
                return MALFORMED_JSON_IN_TOOL_CALLS
            return subtype

    stripped = content.strip()

    if source_field == "reasoning_content":
        return MALFORMED_JSON_IN_REASONING_CONTENT
    if source_field == "tool_calls":
        return MALFORMED_JSON_IN_TOOL_CALLS

    if not stripped:
        if has_reasoning_content or has_tool_calls:
            return MALFORMED_EMPTY_CONTENT_OTHER_FIELD
        return MALFORMED_COMPLETELY_INVALID

    # Markdown JSON fence.
    if stripped.startswith("```") and "```" in stripped[3:]:
        return MALFORMED_CODE_FENCE_WRAPPED

    # Multiple JSON objects.
    object_starts = [m.start() for m in __import__("re").finditer(r"\{\s*\"", stripped)]
    if len(object_starts) > 1:
        return MALFORMED_MULTIPLE_OBJECTS

    # Truncation heuristics.
    open_braces = stripped.count("{")
    close_braces = stripped.count("}")
    open_brackets = stripped.count("[")
    close_brackets = stripped.count("]")
    if open_braces != close_braces or open_brackets != close_brackets:
        return MALFORMED_TRUNCATED

    # Natural language around JSON.
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace > 0 or (last_brace >= 0 and last_brace < len(stripped) - 1):
        return MALFORMED_NATURAL_LANGUAGE_WRAPPED

    return MALFORMED_COMPLETELY_INVALID


def error_reason_from_attempt(attempt: ProviderAttempt, error_body: str = "") -> str:
    """Map a failed attempt to a machine-readable reason."""
    if attempt.is_timeout:
        return TIMEOUT
    if attempt.http_status is not None and attempt.http_status >= 400:
        if attempt.http_status == 400 and _mentions_response_format(error_body):
            return UNSUPPORTED_RESPONSE_FORMAT
        return HTTP_ERROR
    if attempt.response_body_empty:
        return EMPTY_RESPONSE
    if attempt.json_parse_failed:
        return MALFORMED_JSON
    if attempt.content_empty:
        return EMPTY_CONTENT
    return UNKNOWN_PROVIDER_ERROR


def _mentions_response_format(text: str) -> bool:
    """Return True if an error body mentions response_format / structured output."""
    if not text:
        return False
    lowered = text.lower()
    keywords = (
        "response_format",
        "json_schema",
        "json_object",
        "structured output",
        "unsupported format",
    )
    return any(kw in lowered for kw in keywords)
