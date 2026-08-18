"""K3 API Compatibility Probe.

Diagnoses why a specific OpenAI-compatible relay returns HTTP 400 for the
kimi-k3 model. Builds requests incrementally from a minimal (model + messages)
payload up to the full production payload used by LLMIntentProvider.

Environment variables (same as the rest of the project):
    LLM_API_KEY   (required)
    LLM_BASE_URL  (optional; defaults to OpenAI endpoint)
    LLM_MODEL     (optional; defaults to "kimi-k3")

Usage:
    $env:LLM_API_KEY="..."
    $env:LLM_BASE_URL="..."   # optional
    $env:LLM_MODEL="kimi-k3"  # optional
    $env:PYTHONPATH="src"
    python k3_api_compatibility_probe.py

Output:
    reports/k3_api_compatibility_probe.md

Safety:
    - The API key is read from environment variables only.
    - The API key is never written to stdout, stderr, or the report.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "kimi-k3"
REPORT_DIR = Path("reports")
REPORT_PATH = REPORT_DIR / "k3_api_compatibility_probe.md"


@dataclass
class ProbeResult:
    """Result of a single compatibility probe."""

    name: str
    description: str
    endpoint: str
    model: str
    fields_used: list[str] = field(default_factory=list)
    http_status: int | None = None
    exception_type: str | None = None
    is_timeout: bool = False
    response_body_empty: bool = True
    response_body: str = ""
    error_body: str = ""
    latency_ms: float = 0.0
    success: bool = False


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the payload safe for logging (no secrets)."""
    # The payload itself never contains the API key, but keep the helper for
    # future-proofing in case extra_body ever grows sensitive fields.
    return {k: v for k, v in payload.items()}


def _send_probe(
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
) -> tuple[int | None, str, str, str | None, bool, float]:
    """Send one probe request and return raw telemetry.

    Returns:
        (http_status, response_body, error_body, exception_type, is_timeout, latency_ms)
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )

    start = time.perf_counter()
    http_status: int | None = None
    response_body = ""
    error_body = ""
    exception_type: str | None = None
    is_timeout = False

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            latency_ms = (time.perf_counter() - start) * 1000
            raw = resp.read()
            http_status = resp.getcode()
            response_body = raw.decode("utf-8", errors="replace")
            return http_status, response_body, error_body, exception_type, is_timeout, latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        http_status = exc.code
        exception_type = type(exc).__name__
        try:
            error_raw = exc.read()
            error_body = error_raw.decode("utf-8", errors="replace") if error_raw else ""
        except Exception:
            error_body = ""
        return http_status, response_body, error_body, exception_type, is_timeout, latency_ms
    except TimeoutError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        exception_type = type(exc).__name__
        is_timeout = True
        return http_status, response_body, error_body, exception_type, is_timeout, latency_ms
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        exception_type = type(exc).__name__
        return http_status, response_body, error_body, exception_type, is_timeout, latency_ms


def _probe_a_minimal(endpoint: str, api_key: str, model: str) -> ProbeResult:
    """A. model + messages only."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Return the JSON object {\"status\": \"ok\"}."}],
    }
    status, resp_body, err_body, exc_type, timeout, latency = _send_probe(endpoint, api_key, payload)
    return ProbeResult(
        name="A",
        description="model + messages only",
        endpoint=endpoint,
        model=model,
        fields_used=sorted(payload.keys()),
        http_status=status,
        exception_type=exc_type,
        is_timeout=timeout,
        response_body_empty=not resp_body,
        response_body=resp_body,
        error_body=err_body,
        latency_ms=latency,
        success=status == 200,
    )


def _probe_b_response_format(endpoint: str, api_key: str, model: str) -> ProbeResult:
    """B. A + response_format."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Return the JSON object {\"status\": \"ok\"}."}],
        "response_format": {"type": "json_object"},
    }
    status, resp_body, err_body, exc_type, timeout, latency = _send_probe(endpoint, api_key, payload)
    return ProbeResult(
        name="B",
        description="A + response_format={type: json_object}",
        endpoint=endpoint,
        model=model,
        fields_used=sorted(payload.keys()),
        http_status=status,
        exception_type=exc_type,
        is_timeout=timeout,
        response_body_empty=not resp_body,
        response_body=resp_body,
        error_body=err_body,
        latency_ms=latency,
        success=status == 200,
    )


def _probe_c_temperature_max_tokens(endpoint: str, api_key: str, model: str) -> ProbeResult:
    """C. A + temperature + max_tokens."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Return the JSON object {\"status\": \"ok\"}."}],
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    status, resp_body, err_body, exc_type, timeout, latency = _send_probe(endpoint, api_key, payload)
    return ProbeResult(
        name="C",
        description="A + temperature=0.0 + max_tokens=1024",
        endpoint=endpoint,
        model=model,
        fields_used=sorted(payload.keys()),
        http_status=status,
        exception_type=exc_type,
        is_timeout=timeout,
        response_body_empty=not resp_body,
        response_body=resp_body,
        error_body=err_body,
        latency_ms=latency,
        success=status == 200,
    )


def _probe_d_extra_body(endpoint: str, api_key: str, model: str) -> ProbeResult:
    """D. A + enable_thinking extra_body (what LLMIntentProvider injects for kimi)."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Return the JSON object {\"status\": \"ok\"}."}],
        "enable_thinking": False,
    }
    status, resp_body, err_body, exc_type, timeout, latency = _send_probe(endpoint, api_key, payload)
    return ProbeResult(
        name="D",
        description="A + enable_thinking=false (current extra_body for kimi)",
        endpoint=endpoint,
        model=model,
        fields_used=sorted(payload.keys()),
        http_status=status,
        exception_type=exc_type,
        is_timeout=timeout,
        response_body_empty=not resp_body,
        response_body=resp_body,
        error_body=err_body,
        latency_ms=latency,
        success=status == 200,
    )


def _probe_e_full_production(endpoint: str, api_key: str, model: str) -> ProbeResult:
    """E. Full production request used by LLMIntentProvider."""
    system_prompt = (
        "You are a music-score intent parser. Extract the user's transpose "
        "request into JSON. Return ONLY a single JSON object."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "把整首升大二度"},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    status, resp_body, err_body, exc_type, timeout, latency = _send_probe(endpoint, api_key, payload)
    return ProbeResult(
        name="E",
        description="Full production request (system prompt + user text + temperature + max_tokens + response_format + enable_thinking)",
        endpoint=endpoint,
        model=model,
        fields_used=sorted(payload.keys()),
        http_status=status,
        exception_type=exc_type,
        is_timeout=timeout,
        response_body_empty=not resp_body,
        response_body=resp_body,
        error_body=err_body,
        latency_ms=latency,
        success=status == 200,
    )


def _format_body(body: str, limit: int = 1200) -> str:
    """Format a response/error body for the markdown report."""
    if not body:
        return "*(empty)*"
    if len(body) > limit:
        body = body[:limit] + "\n... [truncated]"
    return "```json\n" + body + "\n```"


def _build_report(results: list[ProbeResult], model: str, endpoint: str) -> str:
    """Build the markdown report from probe results."""
    lines: list[str] = []
    lines.append("# K3 API Compatibility Probe Report")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Endpoint**: `{endpoint}`")
    lines.append(f"- **Model ID tested**: `{model}`")
    lines.append("- **API Key**: present in environment (not logged)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Probe | Description | HTTP Status | Latency (ms) | Success |")
    lines.append("|-------|-------------|-------------|--------------|---------|")
    for r in results:
        status = r.http_status if r.http_status is not None else "N/A"
        latency = f"{r.latency_ms:.1f}"
        success = "✅" if r.success else "❌"
        lines.append(f"| {r.name} | {r.description} | {status} | {latency} | {success} |")
    lines.append("")

    # Determine the first field that breaks compatibility.
    first_failure: ProbeResult | None = None
    previous_success: ProbeResult | None = None
    for i, r in enumerate(results):
        if not r.success and first_failure is None:
            first_failure = r
            if i > 0:
                previous_success = results[i - 1]
            break

    if first_failure is None:
        lines.append("**Conclusion**: All probes succeeded. The model works with the current relay using the tested model id.")
    elif results[0].success:
        added = set(first_failure.fields_used) - set(previous_success.fields_used if previous_success else [])
        added_desc = ", ".join(f"`{f}`" for f in sorted(added)) or "(same fields)"
        lines.append(f"**Conclusion**: Probe {first_failure.name} is the first failing probe. "
                     f"Fields added versus the previous successful probe ({previous_success.name if previous_success else 'N/A'}): {added_desc}.")
    else:
        lines.append("**Conclusion**: Even the minimal `model + messages` probe failed. "
                     "This is a relay/model-id/endpoint compatibility issue, not a request-schema issue.")
    lines.append("")

    lines.append("## Detailed Probe Results")
    lines.append("")
    for r in results:
        lines.append(f"### Probe {r.name}: {r.description}")
        lines.append("")
        lines.append(f"- **HTTP Status**: {r.http_status if r.http_status is not None else 'N/A'}")
        lines.append(f"- **Exception Type**: `{r.exception_type or 'None'}`")
        lines.append(f"- **Is Timeout**: {r.is_timeout}")
        lines.append(f"- **Response Body Empty**: {r.response_body_empty}")
        lines.append(f"- **Latency**: {r.latency_ms:.1f} ms")
        lines.append(f"- **Fields Used**: {', '.join(f'`{f}`' for f in r.fields_used)}")
        lines.append("")
        lines.append("**Response body**:")
        lines.append(_format_body(r.response_body))
        lines.append("")
        lines.append("**Error body**:")
        lines.append(_format_body(r.error_body))
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    if first_failure is None:
        lines.append("- K3 works with the current relay and model id.")
        lines.append("- No changes to `OpenAICompatibleClient` are required for basic connectivity.")
        lines.append("- Validate the full `run_real_provider_reliability.py` run to confirm end-to-end behavior.")
    elif not results[0].success:
        lines.append("- **Do not modify `OpenAICompatibleClient` request schema.**")
        lines.append("- Verify the correct model id with the relay operator or documentation.")
        lines.append("- Verify that the relay supports K3 on the `/v1/chat/completions` endpoint.")
        lines.append("- If K3 requires a different endpoint or model id, configure it via `LLM_BASE_URL` / `LLM_MODEL` rather than adding model-specific code.")
        lines.append("- Product recommendation: continue using `kimi-k2.7-code` until the relay K3 configuration is resolved.")
    else:
        lines.append(f"- The first failing field set is from probe {first_failure.name}.")
        lines.append("- A provider capability adapter should be designed to omit or transform the offending field for this relay/model combination.")
        lines.append("- Avoid hard-coding model names; detect capability via a small probe or explicit configuration.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="K3 API Compatibility Probe")
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("LLM_MODEL", DEFAULT_MODEL),
        help=f"Model id to test (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        help=f"Endpoint base URL (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        print("FAIL: LLM_API_KEY not set")
        return 1

    endpoint = args.base_url
    model = args.model

    print(f"Endpoint: {endpoint}")
    print(f"Model ID: {model}")
    print("Probing...")

    results: list[ProbeResult] = []
    results.append(_probe_a_minimal(endpoint, api_key, model))
    results.append(_probe_b_response_format(endpoint, api_key, model))
    results.append(_probe_c_temperature_max_tokens(endpoint, api_key, model))
    results.append(_probe_d_extra_body(endpoint, api_key, model))
    results.append(_probe_e_full_production(endpoint, api_key, model))

    for r in results:
        status = r.http_status if r.http_status is not None else "N/A"
        print(f"  Probe {r.name}: HTTP {status} in {r.latency_ms:.1f} ms ({'success' if r.success else 'fail'})")

    report = _build_report(results, model, endpoint)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
