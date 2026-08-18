"""OpenAI-compatible AI client.

This is an optional integration client. It is NOT imported by the core intent
layer, so the project does not depend on OpenAI/Kimi at runtime unless the
caller explicitly uses this module.

Configuration is read from environment variables only:
- LLM_API_KEY   (required)
- LLM_BASE_URL  (optional, defaults to OpenAI v1/chat/completions)
- LLM_MODEL     (optional)

Supports any API that exposes the OpenAI chat-completions protocol, including
OpenAI, Kimi (Moonshot), and many local/vLLM servers.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ai import AIClient, AIProviderError, AIRequest, AIResponse
from ai.json_extraction import JSONExtractor
from ai.provider_capability import ProviderCapability
from ai.provider_diagnostics import ProviderAttempt, _preview, error_reason_from_attempt


DEFAULT_BASE_URL = "https://api.openai.com/v1/chat/completions"
_PREVIEW_LIMIT = 300


@dataclass
class OpenAICompatibleClient(AIClient):
    """Call an OpenAI-compatible chat completions endpoint.

    Example:
        client = OpenAICompatibleClient.from_env()
        provider = LLMIntentProvider(client=client, model=client.model)
    """

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = ""
    timeout: int = 120
    capabilities: ProviderCapability = field(default_factory=ProviderCapability)

    @classmethod
    def from_env(cls) -> "OpenAICompatibleClient":
        """Create a client from environment variables.

        Raises:
            RuntimeError: if LLM_API_KEY is not set.
        """
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("LLM_API_KEY environment variable is not set")
        return cls(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("LLM_MODEL", ""),
            capabilities=ProviderCapability.from_env(),
        )

    def call(self, request: AIRequest) -> AIResponse:
        """Send a chat completion request and return the assistant content."""
        model = request.model or self.model
        if not model:
            raise RuntimeError("No model specified for OpenAICompatibleClient")

        messages: list[dict[str, str]] = []
        if request.context:
            system = request.context.get("system")
            if system:
                messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if self.capabilities.supports_temperature:
            payload["temperature"] = 0.0
        if request.max_tokens and self.capabilities.supports_max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.response_format and self.capabilities.supports_response_format:
            payload["response_format"] = request.response_format
        if request.extra_body:
            payload.update(request.extra_body)

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers=headers,
            method="POST",
        )

        start = time.perf_counter()
        attempt = ProviderAttempt(attempt=1)
        error_body = ""

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.perf_counter() - start) * 1000
                raw = resp.read()
                attempt.latency_ms = latency_ms
                attempt.http_status = resp.getcode()
                attempt.response_body_empty = not raw
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            attempt.latency_ms = latency_ms
            attempt.http_status = exc.code
            attempt.exception_type = type(exc).__name__
            attempt.is_timeout = self._is_timeout_exception(exc)
            error_body = exc.read().decode("utf-8", errors="replace")
            # Never include the API key in error messages.
            raise AIProviderError(
                f"LLM API HTTP {exc.code}: {error_body[:1024]}",
                attempt=attempt,
            ) from exc
        except TimeoutError as exc:
            attempt.latency_ms = (time.perf_counter() - start) * 1000
            attempt.exception_type = type(exc).__name__
            attempt.is_timeout = True
            raise AIProviderError(
                "LLM API request timed out", attempt=attempt
            ) from exc
        except Exception as exc:
            attempt.latency_ms = (time.perf_counter() - start) * 1000
            attempt.exception_type = type(exc).__name__
            attempt.is_timeout = self._is_timeout_exception(exc)
            raise AIProviderError(
                f"LLM API request failed: {exc}", attempt=attempt
            ) from exc

        # Privacy-safe preview of the raw response body.
        raw_text = raw.decode("utf-8", errors="replace")
        attempt.response_body_head = _preview(raw_text, _PREVIEW_LIMIT)

        if not raw:
            attempt.content_empty = True
            raise AIProviderError(
                "LLM API returned an empty response body", attempt=attempt
            )

        try:
            body = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            attempt.json_parse_failed = True
            raise AIProviderError(
                f"LLM API response was not valid JSON: {exc}", attempt=attempt
            ) from exc

        choices = body.get("choices", [])
        extraction = self._extract_content(choices)
        content = extraction["content"]
        attempt.source_field = extraction["source_field"]
        attempt.extraction_action = extraction["extraction_action"]
        attempt.has_reasoning_content = extraction["has_reasoning_content"]
        attempt.has_tool_calls = extraction["has_tool_calls"]
        raw_content = extraction["raw_content"]
        attempt.raw_content_head = _preview(raw_content, _PREVIEW_LIMIT)
        attempt.raw_content_tail = raw_content[-_PREVIEW_LIMIT:] if len(raw_content) > _PREVIEW_LIMIT else ""
        reasoning_content = extraction.get("reasoning_content", "")
        attempt.reasoning_content_head = _preview(reasoning_content, _PREVIEW_LIMIT)
        attempt.reasoning_content_tail = reasoning_content[-_PREVIEW_LIMIT:] if len(reasoning_content) > _PREVIEW_LIMIT else ""
        attempt.finish_reason = extraction["finish_reason"]

        usage = body.get("usage", {})
        attempt.usage = usage if isinstance(usage, dict) else {}
        attempt.model = str(body.get("model", model))
        attempt.content_empty = not content

        if not content:
            raise AIProviderError(
                "LLM API response contained no usable assistant content",
                attempt=attempt,
            )

        return AIResponse(
            content=content,
            model=attempt.model,
            usage=attempt.usage,
            diagnostics=attempt,
        )

    @staticmethod
    def _extract_content(choices: Any) -> dict[str, Any]:
        """Extract assistant text and provenance from a choices array.

        Tolerates several provider/reasoning-model response shapes:
        - choices[0].message.tool_calls[0].function.arguments  (structured)
        - choices[0].message.content
        - choices[0].message.reasoning_content
        - choices[0].text

        The source priority is: tool_calls > content > reasoning_content > text.
        For each candidate source, deterministic JSON extraction is attempted;
        the first source that yields valid JSON is returned. If no source yields
        valid JSON, the highest-priority non-empty raw text is returned together
        with the extraction failure metadata so the caller can classify it.
        """
        result: dict[str, Any] = {
            "content": "",
            "raw_content": "",
            "reasoning_content": "",
            "source_field": "",
            "extraction_action": "",
            "has_reasoning_content": False,
            "has_tool_calls": False,
            "finish_reason": None,
        }
        if not choices or not isinstance(choices, list):
            return result
        first = choices[0]
        if not isinstance(first, dict):
            return result

        result["finish_reason"] = first.get("finish_reason")
        message = first.get("message", {}) or {}
        if not isinstance(message, dict):
            message = {}

        # Collect candidate sources in priority order.
        candidates: list[tuple[str, str]] = []

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            call = tool_calls[0]
            if isinstance(call, dict):
                function = call.get("function", {}) or {}
                args = function.get("arguments")
                if args:
                    candidates.append(("tool_calls", str(args)))

        content = message.get("content")
        if content:
            candidates.append(("content", str(content)))

        reasoning = message.get("reasoning_content")
        if reasoning:
            candidates.append(("reasoning_content", str(reasoning)))
            result["reasoning_content"] = str(reasoning)

        text = first.get("text")
        if text:
            candidates.append(("text", str(text)))

        # Track metadata from the first candidate that has the relevant field.
        for source_field, raw in candidates:
            if source_field == "reasoning_content":
                result["has_reasoning_content"] = True
            if source_field == "tool_calls":
                result["has_tool_calls"] = True

        # Try deterministic JSON extraction on each source in priority order.
        first_failure: tuple[str, str, str, str] | None = None
        for source_field, raw in candidates:
            extraction = JSONExtractor.normalize(raw)
            if extraction.success:
                result["source_field"] = source_field
                result["extraction_action"] = extraction.action
                result["raw_content"] = raw
                result["content"] = extraction.text
                return result
            if first_failure is None:
                first_failure = (source_field, raw, extraction.action, extraction.failure_subtype)

        # No source produced valid JSON. Return the highest-priority raw text so
        # the provider layer can classify the failure.
        if first_failure is not None:
            source_field, raw, action, _subtype = first_failure
            result["source_field"] = source_field
            result["extraction_action"] = action
            result["raw_content"] = raw
            result["content"] = raw.strip()
            return result

        return result

    @staticmethod
    def _is_timeout_exception(exc: BaseException) -> bool:
        """Heuristic to classify an exception as a timeout."""
        name = type(exc).__name__.lower()
        if "timeout" in name:
            return True
        msg = str(exc).lower()
        return "timed out" in msg or "timeout" in msg
