"""Provider capability flags for OpenAI-compatible compatibility.

This module lets callers declare which optional OpenAI chat-completions
features a given relay/model supports, so that unsupported parameters can be
omitted instead of causing HTTP 400.

Capabilities are intentionally explicit and orthogonal to model names:
code never branches on "kimi", "duoyuanx", or any other provider identifier.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean-ish environment variable."""
    value = os.getenv(name, "")
    if not value:
        return default
    return value.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ProviderCapability:
    """Supported optional features of an OpenAI-compatible endpoint.

    All flags default to ``True`` (standard OpenAI behavior). Set the
    corresponding environment variable to ``false`` / ``0`` / ``no`` to disable.

    Environment variables:
        LLM_SUPPORTS_TEMPERATURE
        LLM_SUPPORTS_MAX_TOKENS
        LLM_SUPPORTS_RESPONSE_FORMAT
        LLM_SUPPORTS_TOOL_CALLS
        LLM_SUPPORTS_SYSTEM_ROLE
    """

    supports_temperature: bool = True
    supports_max_tokens: bool = True
    supports_response_format: bool = True
    supports_tool_calls: bool = True
    supports_system_role: bool = True

    @classmethod
    def from_env(cls) -> "ProviderCapability":
        """Build capabilities from environment variables."""
        return cls(
            supports_temperature=_env_bool("LLM_SUPPORTS_TEMPERATURE", True),
            supports_max_tokens=_env_bool("LLM_SUPPORTS_MAX_TOKENS", True),
            supports_response_format=_env_bool("LLM_SUPPORTS_RESPONSE_FORMAT", True),
            supports_tool_calls=_env_bool("LLM_SUPPORTS_TOOL_CALLS", True),
            supports_system_role=_env_bool("LLM_SUPPORTS_SYSTEM_ROLE", True),
        )

    def summary(self) -> dict[str, bool]:
        """Return a plain dict for diagnostics and logging."""
        return {
            "temperature": self.supports_temperature,
            "max_tokens": self.supports_max_tokens,
            "response_format": self.supports_response_format,
            "tool_calls": self.supports_tool_calls,
            "system_role": self.supports_system_role,
        }
