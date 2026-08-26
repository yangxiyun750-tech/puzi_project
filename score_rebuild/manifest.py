"""Load the machine-readable ScoreRebuild installation manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "score-rebuild-manifest.json"


class ManifestError(RuntimeError):
    """Raised when the installation manifest is missing or invalid."""


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path else MANIFEST_PATH
    if not manifest_path.is_file():
        raise ManifestError(
            f"ScoreRebuild manifest is missing: {manifest_path}. "
            "Re-download the repository; do not reconstruct this file manually."
        )
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read ScoreRebuild manifest {manifest_path}: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ManifestError(
            f"Unsupported manifest schema_version={data.get('schema_version')!r}; expected 1."
        )
    return data


def project_root() -> Path:
    return PROJECT_ROOT
