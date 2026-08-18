"""Real Provider Reliability Smoke Runner.

Runs the same two natural-language transpose requests repeatedly against the
real OpenAI-compatible provider and collects structured diagnostics.

Required environment variables:
    LLM_API_KEY   (required)
    LLM_BASE_URL  (optional; defaults to OpenAI endpoint)
    LLM_MODEL     (e.g. kimi-k2-6 or equivalent model id)

Usage:
    set LLM_API_KEY=...
    set LLM_MODEL=kimi-k2-6
    PYTHONPATH=src python run_real_provider_reliability.py
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ai import (
    LLMIntentProvider,
    OpenAICompatibleClient,
    ProviderAttempt,
    TransposeIntentResolver,
    build_intent_context,
)
from score_engine.score_ir.score_ir import Score
from tests.e2e_fixtures import import_fixture, make_single_trumpet_musicxml


REPORT_DIR = Path("reports")
REPORT_PATH = REPORT_DIR / "real_provider_reliability.json"
HISTORY_PATH = REPORT_DIR / "real_provider_history.jsonl"

CASES = [
    "把整首升大二度",
    "把长号升一个八度",
]
ITERATIONS = 20


@dataclass
class AttemptRecord:
    """Sanitized, serializable view of a provider attempt."""

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
    source_field: str = ""
    extraction_action: str = ""
    raw_content_head: str = ""
    raw_content_tail: str = ""
    reasoning_content_head: str = ""
    reasoning_content_tail: str = ""
    response_body_head: str = ""
    response_body_tail: str = ""
    finish_reason: str | None = None
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    extracted_json: dict[str, Any] = field(default_factory=dict)
    error_reason: str = ""
    error_detail: str = ""
    malformed_json_subtype: str = ""


@dataclass
class RunRecord:
    """Result of one provider call."""

    iteration: int
    text: str
    resolver_status: str
    error_reason: str
    malformed_json_subtype: str
    total_latency_ms: float
    clarification_question: str = ""
    intent_dict: dict[str, Any] = field(default_factory=dict)
    attempts: list[AttemptRecord] = field(default_factory=list)
    recovered_by_retry: bool = False


@dataclass
class CaseSummary:
    """Aggregated statistics for one NL case."""

    text: str
    iterations: int
    success: int
    provider_error: int
    needs_clarification: int
    invalid: int
    unsupported: int
    recovered_by_retry: int
    error_reason_counts: dict[str, int] = field(default_factory=dict)
    malformed_json_subtype_counts: dict[str, int] = field(default_factory=dict)
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0


def _sanitize_attempt(attempt: ProviderAttempt) -> AttemptRecord:
    """Convert a ProviderAttempt into a serializable record without prompts."""
    return AttemptRecord(
        attempt=attempt.attempt,
        latency_ms=round(attempt.latency_ms, 3),
        http_status=attempt.http_status,
        exception_type=attempt.exception_type,
        is_timeout=attempt.is_timeout,
        response_body_empty=attempt.response_body_empty,
        content_empty=attempt.content_empty,
        has_reasoning_content=attempt.has_reasoning_content,
        has_tool_calls=attempt.has_tool_calls,
        json_parse_failed=attempt.json_parse_failed,
        source_field=attempt.source_field,
        extraction_action=attempt.extraction_action,
        raw_content_head=attempt.raw_content_head,
        raw_content_tail=attempt.raw_content_tail,
        reasoning_content_head=attempt.reasoning_content_head,
        reasoning_content_tail=attempt.reasoning_content_tail,
        response_body_head=attempt.response_body_head,
        response_body_tail=attempt.response_body_tail,
        finish_reason=attempt.finish_reason,
        model=attempt.model,
        usage=attempt.usage,
        extracted_json=attempt.extracted_json,
        error_reason=attempt.error_reason,
        error_detail=attempt.error_detail[:500],
        malformed_json_subtype=attempt.malformed_json_subtype,
    )


def _compute_latency_stats(latencies: list[float]) -> tuple[float, float, float, float]:
    if not latencies:
        return 0.0, 0.0, 0.0, 0.0
    sorted_ms = sorted(latencies)
    n = len(sorted_ms)
    p95_idx = int(n * 0.95)
    p95_idx = min(p95_idx, n - 1)
    return (
        sum(sorted_ms) / n,
        sorted_ms[p95_idx],
        sorted_ms[0],
        sorted_ms[-1],
    )


def _safe_error_reason(obj: Any) -> str:
    """Return error_reason if present, else ''."""
    return getattr(obj, "error_reason", "") or ""


def _extract_malformed_subtype(diagnostics: tuple[Any, ...]) -> str:
    """Return malformed_json_subtype from the last ProviderAttempt, or ''."""
    for attempt in reversed(diagnostics):
        if isinstance(attempt, ProviderAttempt):
            subtype = getattr(attempt, "malformed_json_subtype", "") or ""
            if subtype:
                return subtype
    return ""


def _summarize_case(text: str, records: list[RunRecord]) -> CaseSummary:
    statuses = Counter(r.resolver_status for r in records)
    error_reasons = Counter(r.error_reason for r in records if r.error_reason)
    subtypes = Counter(
        r.malformed_json_subtype for r in records if r.malformed_json_subtype
    )
    recovered = sum(1 for r in records if r.recovered_by_retry)
    latencies = [r.total_latency_ms for r in records]
    avg, p95, min_ms, max_ms = _compute_latency_stats(latencies)
    return CaseSummary(
        text=text,
        iterations=len(records),
        success=statuses.get("ready", 0),
        provider_error=statuses.get("provider_error", 0),
        needs_clarification=statuses.get("needs_clarification", 0),
        invalid=statuses.get("invalid", 0),
        unsupported=statuses.get("unsupported", 0),
        recovered_by_retry=recovered,
        error_reason_counts=dict(error_reasons),
        malformed_json_subtype_counts=dict(subtypes),
        avg_latency_ms=round(avg, 3),
        p95_latency_ms=round(p95, 3),
        min_latency_ms=round(min_ms, 3),
        max_latency_ms=round(max_ms, 3),
    )


def _run_case(text: str, provider: LLMIntentProvider, score: Score) -> RunRecord:
    """Execute one iteration and return a sanitized record."""
    start = time.perf_counter()
    context = build_intent_context(score)
    intent = provider.parse_transpose(text, context)
    resolver = TransposeIntentResolver()
    result = resolver.resolve(intent, score)
    total_latency_ms = (time.perf_counter() - start) * 1000

    attempts = [
        _sanitize_attempt(a) for a in intent.diagnostics if isinstance(a, ProviderAttempt)
    ]
    recovered_by_retry = (
        result.status == "ready"
        and len(attempts) > 1
        and any(
            a.http_status is not None or a.content_empty or a.json_parse_failed
            for a in attempts[:-1]
        )
    )

    # Subtype lives only in ProviderAttempt diagnostics, not in core intent schema.
    combined_diagnostics = getattr(result, "diagnostics", ()) or getattr(intent, "diagnostics", ())
    subtype = _extract_malformed_subtype(combined_diagnostics)

    return RunRecord(
        iteration=0,  # filled in by caller
        text=text,
        resolver_status=getattr(result, "status", ""),
        error_reason=_safe_error_reason(result) or _safe_error_reason(intent),
        malformed_json_subtype=subtype,
        total_latency_ms=round(total_latency_ms, 3),
        clarification_question=result.clarification_question or intent.clarification_question,
        intent_dict=_intent_to_dict(intent),
        attempts=attempts,
        recovered_by_retry=recovered_by_retry,
    )


def _intent_to_dict(intent: TransposeIntent) -> dict[str, Any]:
    """Return a serializable view of a TransposeIntent (no diagnostics)."""
    return {
        "status": intent.status,
        "operation": intent.operation,
        "direction": intent.direction,
        "interval_description": intent.interval_description,
        "part_description": intent.part_description,
        "measure_start_description": intent.measure_start_description,
        "measure_end_description": intent.measure_end_description,
        "is_all_parts": intent.is_all_parts,
        "basis": intent.basis,
        "clarification_question": intent.clarification_question,
        "confidence": intent.confidence,
        "source_text": intent.source_text,
        "error_reason": intent.error_reason,
    }


def _build_history_record(
    record: RunRecord,
    client: OpenAICompatibleClient,
    model: str,
) -> dict[str, Any]:
    """Build a long-term append-only history record for one run."""
    last_attempt = record.attempts[-1] if record.attempts else AttemptRecord(attempt=0)
    return {
        "timestamp": datetime.now().isoformat(),
        "provider": client.base_url,
        "model": model,
        "case_text": record.text,
        "iteration": record.iteration,
        "resolver_status": record.resolver_status,
        "clarification_question": record.clarification_question,
        "intent": record.intent_dict,
        "source_field": last_attempt.source_field,
        "extraction_action": last_attempt.extraction_action,
        "malformed_json_subtype": last_attempt.malformed_json_subtype,
        "attempts": [asdict(a) for a in record.attempts],
    }


def _redact_sensitive(obj: Any) -> Any:
    """Recursively redact strings that look like API keys."""
    if isinstance(obj, dict):
        return {k: _redact_sensitive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_sensitive(v) for v in obj]
    if isinstance(obj, str):
        import re as _re

        return _re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED]", obj)
    return obj


def _write_history_record(
    record: RunRecord,
    client: OpenAICompatibleClient,
    model: str,
) -> None:
    """Append one run record to the cumulative JSONL history."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _redact_sensitive(_build_history_record(record, client, model))
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Real provider reliability smoke runner")
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Run only this NL case (default: both predefined cases).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=ITERATIONS,
        help=f"Iterations per case (default: {ITERATIONS}).",
    )
    args = parser.parse_args()

    if not os.getenv("LLM_API_KEY"):
        print("FAIL: LLM_API_KEY not set")
        return 1

    client = OpenAICompatibleClient.from_env()
    provider = LLMIntentProvider(
        client=client,
        model=os.getenv("LLM_MODEL", ""),
        max_tokens=1024,
    )
    score_xml = make_single_trumpet_musicxml(measures=50)
    score = import_fixture(score_xml)

    cases = [args.case] if args.case else CASES
    iterations = max(1, args.iterations)

    print(f"Provider: {client.base_url}")
    print(f"Model: {os.getenv('LLM_MODEL', 'default')}")
    print(f"Iterations per case: {iterations}")
    print("=" * 60)

    all_records: list[RunRecord] = []
    summaries: list[CaseSummary] = []

    for text in cases:
        print(f"\nCase: {text}")
        case_records: list[RunRecord] = []
        for i in range(1, iterations + 1):
            record = _run_case(text, provider, score)
            record.iteration = i
            case_records.append(record)
            all_records.append(record)
            status_marker = "OK" if record.resolver_status == "ready" else record.resolver_status
            subtype = f"[{record.malformed_json_subtype}]" if record.malformed_json_subtype else ""
            print(f"  [{i:02d}/{iterations}] {status_marker} {subtype} ({record.total_latency_ms:.0f}ms)")

        summary = _summarize_case(text, case_records)
        summaries.append(summary)
        print(f"  -> success={summary.success}/{summary.iterations}, "
              f"provider_error={summary.provider_error}, "
              f"recovered_by_retry={summary.recovered_by_retry}, "
              f"avg={summary.avg_latency_ms}ms, p95={summary.p95_latency_ms}ms")
        if summary.error_reason_counts:
            print(f"     error_reasons: {summary.error_reason_counts}")
        if summary.malformed_json_subtype_counts:
            print(f"     malformed_subtypes: {summary.malformed_json_subtype_counts}")

        # Persist every run to the cumulative JSONL history.
        for record in case_records:
            _write_history_record(record, client, os.getenv("LLM_MODEL", "default"))

        # Print details for malformed_json failures so they can be inspected
        # immediately without opening the JSON report.
        malformed_records = [
            r for r in case_records
            if r.error_reason == "malformed_json"
        ]
        for r in malformed_records:
            print(f"\n  -- malformed_json detail (iteration {r.iteration}) --")
            for a in r.attempts:
                print(f"     attempt={a.attempt}, source_field={a.source_field}, "
                      f"finish_reason={a.finish_reason}, model={a.model}")
                if a.raw_content_head:
                    print(f"     raw_content_head: {a.raw_content_head[:300]!r}")
                if a.response_body_head:
                    print(f"     response_body_head: {a.response_body_head[:300]!r}")
                print(f"     error_detail: {a.error_detail[:300]!r}")

    report = {
        "date": datetime.now().isoformat(),
        "provider": client.base_url,
        "model": os.getenv("LLM_MODEL", "default"),
        "capabilities": client.capabilities.summary(),
        "iterations_per_case": iterations,
        "summaries": [asdict(s) for s in summaries],
        "runs": [asdict(r) for r in all_records],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
