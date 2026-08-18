"""Provider capability / OpenAI-compatible compatibility tests.

These tests verify that OpenAICompatibleClient omits unsupported optional
parameters based on ProviderCapability flags, without hard-coding any provider
or model name.
"""

from __future__ import annotations

import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch

from ai import AIRequest, OpenAICompatibleClient, ProviderCapability


class _MockHTTPResponse:
    """Minimal mock for urllib.request.urlopen return value."""

    def __init__(self, body: dict, status: int = 200):
        self._body = json.dumps(body).encode("utf-8")
        self._status = status

    def read(self):
        return self._body

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _capture_payload_from_call(client: OpenAICompatibleClient, request: AIRequest) -> dict:
    """Call client.call and return the JSON payload that was sent."""
    response_body = {
        "id": "test",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"status": "ok"}'},
        }],
        "usage": {},
    }

    captured: dict = {}

    def fake_urlopen(req, **kwargs):
        captured["data"] = req.data
        return _MockHTTPResponse(response_body, 200)

    with patch("urllib.request.urlopen", fake_urlopen):
        client.call(request)

    assert captured["data"] is not None
    return json.loads(captured["data"].decode("utf-8"))


class TestProviderCapability(unittest.TestCase):
    def test_default_capabilities_all_true(self):
        cap = ProviderCapability()
        self.assertTrue(cap.supports_temperature)
        self.assertTrue(cap.supports_max_tokens)
        self.assertTrue(cap.supports_response_format)
        self.assertTrue(cap.supports_tool_calls)
        self.assertTrue(cap.supports_system_role)

    def test_from_env_defaults(self):
        # Ensure no env vars leak from the test runner.
        for name in (
            "LLM_SUPPORTS_TEMPERATURE",
            "LLM_SUPPORTS_MAX_TOKENS",
            "LLM_SUPPORTS_RESPONSE_FORMAT",
            "LLM_SUPPORTS_TOOL_CALLS",
            "LLM_SUPPORTS_SYSTEM_ROLE",
        ):
            os.environ.pop(name, None)
        cap = ProviderCapability.from_env()
        self.assertTrue(cap.supports_temperature)
        self.assertTrue(cap.supports_max_tokens)

    def test_from_env_disables_temperature(self):
        os.environ["LLM_SUPPORTS_TEMPERATURE"] = "false"
        try:
            cap = ProviderCapability.from_env()
            self.assertFalse(cap.supports_temperature)
        finally:
            os.environ.pop("LLM_SUPPORTS_TEMPERATURE", None)

    def test_from_env_enables_temperature(self):
        os.environ["LLM_SUPPORTS_TEMPERATURE"] = "1"
        try:
            cap = ProviderCapability.from_env()
            self.assertTrue(cap.supports_temperature)
        finally:
            os.environ.pop("LLM_SUPPORTS_TEMPERATURE", None)


class TestOpenAICompatibleClientCapability(unittest.TestCase):
    def _client(self, **cap_kwargs) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(
            api_key="test-key",
            base_url="https://example.com/v1/chat/completions",
            model="test-model",
            capabilities=ProviderCapability(**cap_kwargs),
        )

    def _request(self, **kwargs) -> AIRequest:
        defaults = {
            "prompt": "hi",
            "model": "test-model",
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        defaults.update(kwargs)
        return AIRequest(**defaults)

    def test_includes_temperature_by_default(self):
        client = self._client()
        payload = _capture_payload_from_call(client, self._request())
        self.assertIn("temperature", payload)
        self.assertEqual(payload["temperature"], 0.0)

    def test_omits_temperature_when_unsupported(self):
        client = self._client(supports_temperature=False)
        payload = _capture_payload_from_call(client, self._request())
        self.assertNotIn("temperature", payload)

    def test_includes_max_tokens_by_default(self):
        client = self._client()
        payload = _capture_payload_from_call(client, self._request())
        self.assertIn("max_tokens", payload)
        self.assertEqual(payload["max_tokens"], 1024)

    def test_omits_max_tokens_when_unsupported(self):
        client = self._client(supports_max_tokens=False)
        payload = _capture_payload_from_call(client, self._request())
        self.assertNotIn("max_tokens", payload)

    def test_omits_response_format_when_unsupported(self):
        client = self._client(supports_response_format=False)
        payload = _capture_payload_from_call(client, self._request())
        self.assertNotIn("response_format", payload)

    def test_k3_compatible_payload(self):
        """K3 on the tested relay rejects temperature but accepts everything else."""
        client = self._client(
            supports_temperature=False,
            supports_max_tokens=True,
            supports_response_format=True,
        )
        payload = _capture_payload_from_call(client, self._request())
        self.assertNotIn("temperature", payload)
        self.assertIn("max_tokens", payload)
        self.assertIn("response_format", payload)
        self.assertIn("model", payload)
        self.assertIn("messages", payload)

    def test_k2_k7_compatibility_payload(self):
        """Default capabilities produce the same payload shape as before."""
        client = self._client()  # all defaults True
        payload = _capture_payload_from_call(client, self._request())
        self.assertIn("temperature", payload)
        self.assertEqual(payload["temperature"], 0.0)
        self.assertIn("max_tokens", payload)
        self.assertIn("response_format", payload)

    def test_extra_body_always_sent(self):
        client = self._client(supports_temperature=False)
        request = self._request(extra_body={"enable_thinking": False})
        payload = _capture_payload_from_call(client, request)
        self.assertIn("enable_thinking", payload)
        self.assertFalse(payload["enable_thinking"])


class TestProviderCapabilityFromEnvIntegration(unittest.TestCase):
    def test_client_from_env_reads_capability_flags(self):
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_SUPPORTS_TEMPERATURE"] = "false"
        try:
            client = OpenAICompatibleClient.from_env()
            self.assertFalse(client.capabilities.supports_temperature)
        finally:
            os.environ.pop("LLM_SUPPORTS_TEMPERATURE", None)
            os.environ.pop("LLM_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
