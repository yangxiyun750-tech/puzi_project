"""Explicit, provider-neutral capability readiness checks."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


AVAILABLE = "AVAILABLE"
UNKNOWN = "UNKNOWN"
NOT_CONFIGURED = "NOT_CONFIGURED"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "verified"}


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    status: str
    provider: str = ""
    evidence: str = ""
    fallback: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def run_capability_doctor(
    *,
    code_provider: str | None = None,
    code_verified: bool | None = None,
    visual_provider: str | None = None,
    visual_verified: bool | None = None,
    human_reviewer: str | None = None,
) -> list[CapabilityResult]:
    code_provider = (code_provider or os.environ.get("SCORE_REBUILD_CODE_REASONING_PROVIDER", "")).strip()
    visual_provider = (visual_provider or os.environ.get("SCORE_REBUILD_VISUAL_REVIEW_PROVIDER", "")).strip()
    human_reviewer = (human_reviewer or os.environ.get("SCORE_REBUILD_HUMAN_REVIEWER", "")).strip()

    if code_verified is None:
        code_verified = _truthy(os.environ.get("SCORE_REBUILD_CODE_REASONING_VERIFIED"))
    if visual_verified is None:
        visual_verified = _truthy(os.environ.get("SCORE_REBUILD_VISUAL_REVIEW_VERIFIED"))

    code_status = AVAILABLE if code_provider and code_verified else UNKNOWN
    code_evidence = (
        "Provider and operator verification were supplied for this run."
        if code_status == AVAILABLE
        else "No executable provider-neutral reasoning probe is configured; availability is not assumed."
    )

    if not visual_provider:
        visual_status = NOT_CONFIGURED
        visual_evidence = "No visual provider was declared. Image input is not inferred from the coding agent."
    elif visual_verified:
        visual_status = AVAILABLE
        visual_evidence = "Provider and explicit visual-input verification were supplied for this run."
    else:
        visual_status = UNKNOWN
        visual_evidence = "A provider name exists, but successful image-input review has not been evidenced."

    human_status = AVAILABLE if human_reviewer else NOT_CONFIGURED
    human_evidence = (
        f"Manual musical reviewer declared: {human_reviewer}."
        if human_reviewer
        else "Declare a musically qualified reviewer; unattended acceptance is not permitted."
    )

    return [
        CapabilityResult(
            capability="CODE_REASONING",
            status=code_status,
            provider=code_provider,
            evidence=code_evidence,
        ),
        CapabilityResult(
            capability="VISUAL_REVIEW",
            status=visual_status,
            provider=visual_provider,
            evidence=visual_evidence,
            fallback="Manual page-by-page visual review" if visual_status != AVAILABLE else "",
        ),
        CapabilityResult(
            capability="HUMAN_REVIEW_FALLBACK",
            status=human_status,
            provider=human_reviewer,
            evidence=human_evidence,
        ),
    ]


def print_capability_results(results: list[CapabilityResult]) -> None:
    for result in results:
        print(f"{result.capability}: {result.status}")
        if result.provider:
            print(f"  provider/reviewer: {result.provider}")
        print(f"  evidence: {result.evidence}")
        if result.fallback:
            print(f"  fallback: {result.fallback}")

    statuses = {result.capability: result.status for result in results}
    if statuses["VISUAL_REVIEW"] != AVAILABLE and statuses["HUMAN_REVIEW_FALLBACK"] == AVAILABLE:
        print("\nPIPELINE_MODE: MANUAL_VISUAL_REVIEW_REQUIRED")
    elif statuses["VISUAL_REVIEW"] == AVAILABLE:
        print("\nPIPELINE_MODE: PROVIDER_VISUAL_REVIEW_WITH_HUMAN_FALLBACK")
    else:
        print("\nPIPELINE_MODE: BLOCKED")


def capability_exit_code(results: list[CapabilityResult]) -> int:
    statuses = {result.capability: result.status for result in results}
    if statuses.get("CODE_REASONING") != AVAILABLE:
        return 1
    if statuses.get("HUMAN_REVIEW_FALLBACK") != AVAILABLE:
        return 1
    # Visual review may fall back to the declared human reviewer.
    return 0
