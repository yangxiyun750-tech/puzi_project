"""AI model invocation layer — decoupled from score logic.

This layer is responsible ONLY for:
- Understanding user natural-language intent
- Calling external AI models for visual score inspection
- Returning structured results

It does NOT modify ScoreIR directly. All musical edits are performed
deterministically by the Score Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIRequest:
    """A request to an AI model."""
    prompt: str
    image_path: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    max_tokens: int = 4096
    response_format: dict[str, Any] | None = None
    extra_body: dict[str, Any] | None = None


@dataclass
class AIResponse:
    """A response from an AI model."""
    content: str
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    diagnostics: Any | None = None  # ProviderAttempt on error, else None


class AIProviderError(RuntimeError):
    """Raised when an AI provider call fails.

    Carries a ``ProviderAttempt`` with structured diagnostics so callers can
    classify the failure without parsing error strings.
    """

    def __init__(self, message: str, attempt: Any):
        super().__init__(message)
        self.attempt = attempt


class AIClient(ABC):
    """Abstract base class for AI model clients.

    Implementations should wrap specific APIs (OpenAI, Anthropic, local models,
    etc.) without exposing them to the score engine.
    """

    @abstractmethod
    def call(self, request: AIRequest) -> AIResponse:
        """Send a request to the AI model."""
        ...


class NullAIClient(AIClient):
    """Placeholder client that returns empty responses.

    Used when no AI model is configured. All calls return empty content
    with confidence 0.0, causing downstream code to fall back to
    HUMAN_REVIEW.
    """

    def call(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            content="",
            model="null",
            confidence=0.0,
        )


# ---------------------------------------------------------------------------
# Natural-language transpose intent layer
# ---------------------------------------------------------------------------

from .intent_parser import (
    AIIntentProvider,
    LLMIntentProvider,
    MockIntentProvider,
)
from .intent_resolver import TransposeIntentResolver, build_intent_context
from .intent_schema import (
    IntentContext,
    TransposeIntent,
    TransposeIntentResult,
    ValidationResult,
)
from .intent_validator import IntentValidator
from .openai_compatible_client import OpenAICompatibleClient
from .provider_capability import ProviderCapability
from .provider_diagnostics import (
    EMPTY_CONTENT,
    EMPTY_RESPONSE,
    HTTP_ERROR,
    MALFORMED_JSON,
    MALFORMED_CODE_FENCE_WRAPPED,
    MALFORMED_COMPLETELY_INVALID,
    MALFORMED_EMPTY_CONTENT_OTHER_FIELD,
    MALFORMED_JSON_IN_REASONING_CONTENT,
    MALFORMED_JSON_IN_TOOL_CALLS,
    MALFORMED_MULTIPLE_OBJECTS,
    MALFORMED_NATURAL_LANGUAGE_WRAPPED,
    MALFORMED_OTHER,
    MALFORMED_TRUNCATED,
    SCHEMA_MISMATCH,
    TIMEOUT,
    UNKNOWN_PROVIDER_ERROR,
    UNSUPPORTED_RESPONSE_FORMAT,
    ProviderAttempt,
    classify_malformed_json,
    error_reason_from_attempt,
)

__all__ = [
    # Core AI client
    "AIClient",
    "AIRequest",
    "AIResponse",
    "AIProviderError",
    "NullAIClient",
    # Provider capability
    "ProviderCapability",
    # Provider diagnostics
    "ProviderAttempt",
    "error_reason_from_attempt",
    "classify_malformed_json",
    "HTTP_ERROR",
    "TIMEOUT",
    "EMPTY_RESPONSE",
    "EMPTY_CONTENT",
    "MALFORMED_JSON",
    "SCHEMA_MISMATCH",
    "UNSUPPORTED_RESPONSE_FORMAT",
    "UNKNOWN_PROVIDER_ERROR",
    "MALFORMED_COMPLETELY_INVALID",
    "MALFORMED_CODE_FENCE_WRAPPED",
    "MALFORMED_NATURAL_LANGUAGE_WRAPPED",
    "MALFORMED_MULTIPLE_OBJECTS",
    "MALFORMED_TRUNCATED",
    "MALFORMED_JSON_IN_REASONING_CONTENT",
    "MALFORMED_JSON_IN_TOOL_CALLS",
    "MALFORMED_EMPTY_CONTENT_OTHER_FIELD",
    "MALFORMED_OTHER",
    # Transpose intent layer
    "AIIntentProvider",
    "LLMIntentProvider",
    "MockIntentProvider",
    "TransposeIntent",
    "TransposeIntentResult",
    "IntentContext",
    "ValidationResult",
    "IntentValidator",
    "TransposeIntentResolver",
    "build_intent_context",
    "OpenAICompatibleClient",
]
