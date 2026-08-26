"""Optional private golden-fixture configuration for developer-only checks."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


PRIVATE_FIXTURE_ENV = "SCORE_REBUILD_PRIVATE_FIXTURE_MUSICXML"
PRIVATE_OUTPUT_ENV = "SCORE_REBUILD_PRIVATE_FIXTURE_OUTPUT_DIR"


@dataclass(frozen=True)
class PrivateFixtureStatus:
    available: bool
    path: Path | None
    detail: str


def private_fixture_status() -> PrivateFixtureStatus:
    """Resolve the optional private MusicXML fixture without assuming a local path."""

    configured = os.environ.get(PRIVATE_FIXTURE_ENV, "").strip()
    if not configured:
        return PrivateFixtureStatus(
            available=False,
            path=None,
            detail=f"Not configured. Set {PRIVATE_FIXTURE_ENV} to a private MusicXML file when authorized.",
        )

    path = Path(os.path.expandvars(configured)).expanduser()
    if not path.is_file():
        return PrivateFixtureStatus(
            available=False,
            path=path,
            detail=f"Configured private fixture does not exist: {path}",
        )
    return PrivateFixtureStatus(available=True, path=path.resolve(), detail="Configured private fixture is available.")


def private_fixture_output_dir() -> Path:
    """Return a configured private output directory or an isolated system-temp directory."""

    configured = os.environ.get(PRIVATE_OUTPUT_ENV, "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser().resolve()
    return Path(tempfile.gettempdir()).resolve() / "score-rebuild-private-fixture-output"


def print_private_fixture_status() -> PrivateFixtureStatus:
    status = private_fixture_status()
    print(f"PRIVATE_FIXTURE_AVAILABLE = {'YES' if status.available else 'NO'}")
    if status.available:
        print(f"  path: {status.path}")
        print(f"  detail: {status.detail}")
    else:
        print(f"[SKIPPED] {status.detail}")
    return status
