"""Real provider reliability history persistence tests.

These tests verify that:
- every run is appended to a cumulative JSONL history (not overwritten)
- API keys never appear in the persisted history
- the history record contains the expected diagnostic fields
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from ai import OpenAICompatibleClient, ProviderCapability, TransposeIntent
from ai.provider_diagnostics import ProviderAttempt
from run_real_provider_reliability import (
    AttemptRecord,
    RunRecord,
    _build_history_record,
    _redact_sensitive,
    _write_history_record,
)


class _FakeClient:
    """Minimal stand-in for OpenAICompatibleClient in history tests."""

    def __init__(self, base_url: str = "https://example.com/v1") -> None:
        self.base_url = base_url
        self.capabilities = ProviderCapability()


class TestHistoryPersistence(unittest.TestCase):
    """Append-only JSONL history for real provider runs."""

    def _make_record(
        self,
        text: str = "把整首升大二度",
        iteration: int = 1,
        attempts: list[AttemptRecord] | None = None,
    ) -> RunRecord:
        return RunRecord(
            iteration=iteration,
            text=text,
            resolver_status="ready",
            error_reason="",
            malformed_json_subtype="",
            total_latency_ms=123.456,
            clarification_question="",
            intent_dict={
                "status": "ready",
                "operation": "transpose",
                "direction": "up",
                "interval_description": "大二度",
                "part_description": None,
                "measure_start_description": None,
                "measure_end_description": None,
                "is_all_parts": True,
                "basis": None,
                "clarification_question": "",
                "confidence": 0.95,
                "source_text": text,
                "error_reason": "",
            },
            attempts=attempts or [],
        )

    def test_history_appends_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.jsonl"
            with patch("run_real_provider_reliability.HISTORY_PATH", history_path):
                client = _FakeClient()
                record1 = self._make_record(text="case-a", iteration=1)
                record2 = self._make_record(text="case-b", iteration=2)

                _write_history_record(record1, client, "model-a")
                _write_history_record(record2, client, "model-b")

                lines = history_path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 2)

                parsed1 = json.loads(lines[0])
                parsed2 = json.loads(lines[1])
                self.assertEqual(parsed1["case_text"], "case-a")
                self.assertEqual(parsed1["model"], "model-a")
                self.assertEqual(parsed2["case_text"], "case-b")
                self.assertEqual(parsed2["model"], "model-b")

    def test_history_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.jsonl"
            with patch("run_real_provider_reliability.HISTORY_PATH", history_path):
                client = _FakeClient("https://relay.example.com/v1")
                attempt = AttemptRecord(
                    attempt=1,
                    http_status=200,
                    latency_ms=150.0,
                    finish_reason="stop",
                    model="moonshotai/Kimi-K3",
                    source_field="content",
                    extraction_action="none",
                    malformed_json_subtype="",
                    raw_content_head='{"status":"ready"}',
                    raw_content_tail='{"status":"ready"}',
                    reasoning_content_head="",
                    reasoning_content_tail="",
                    response_body_head='{"choices":[]}',
                    response_body_tail='"finish_reason":"stop"}',
                    extracted_json={"status": "ready"},
                    error_reason="",
                    error_detail="",
                )
                record = self._make_record(attempts=[attempt])

                _write_history_record(record, client, "kimi-k3")

                payload = json.loads(history_path.read_text(encoding="utf-8").strip())
                self.assertEqual(payload["provider"], "https://relay.example.com/v1")
                self.assertEqual(payload["model"], "kimi-k3")
                self.assertEqual(payload["iteration"], 1)
                self.assertEqual(payload["resolver_status"], "ready")
                self.assertIn("timestamp", payload)
                self.assertIn("intent", payload)
                self.assertIn("source_field", payload)
                self.assertIn("extraction_action", payload)
                self.assertIn("malformed_json_subtype", payload)
                self.assertIn("attempts", payload)

                attempt_payload = payload["attempts"][0]
                self.assertEqual(attempt_payload["attempt"], 1)
                self.assertEqual(attempt_payload["http_status"], 200)
                self.assertEqual(attempt_payload["latency_ms"], 150.0)
                self.assertEqual(attempt_payload["finish_reason"], "stop")
                self.assertEqual(attempt_payload["model"], "moonshotai/Kimi-K3")
                self.assertEqual(attempt_payload["source_field"], "content")
                self.assertEqual(attempt_payload["extraction_action"], "none")
                self.assertEqual(attempt_payload["raw_content_head"], '{"status":"ready"}')
                self.assertEqual(attempt_payload["response_body_head"], '{"choices":[]}')
                self.assertEqual(attempt_payload["extracted_json"], {"status": "ready"})

    def test_api_key_is_redacted_from_history(self):
        fake_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.jsonl"
            with patch("run_real_provider_reliability.HISTORY_PATH", history_path):
                client = _FakeClient()
                attempt = AttemptRecord(
                    attempt=1,
                    error_detail=f"Authorization failed for {fake_key} in header",
                    raw_content_head=f'{{"msg":"used {fake_key}"}}',
                )
                record = self._make_record(attempts=[attempt])

                _write_history_record(record, client, "kimi-k3")

                raw = history_path.read_text(encoding="utf-8")
                self.assertNotIn(fake_key, raw)
                self.assertIn("[REDACTED]", raw)

    def test_redact_sensitive_handles_nested_structures(self):
        key = "sk-1234567890abcdef1234567890abcdef"
        obj = {
            "level1": {
                "level2": [
                    {"detail": f"used {key} here"},
                    "plain string",
                ]
            },
            "list": [key, "safe"],
        }
        sanitized = _redact_sensitive(obj)
        self.assertNotIn(key, json.dumps(sanitized))
        self.assertIn("[REDACTED]", json.dumps(sanitized))
        self.assertEqual(sanitized["level1"]["level2"][1], "plain string")
        self.assertEqual(sanitized["list"][1], "safe")


if __name__ == "__main__":
    unittest.main()
