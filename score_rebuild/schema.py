"""Acquire and verify the pinned MusicXML 4.0 schema without bundling it."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .manifest import load_manifest, project_root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def target_schema_directory() -> Path:
    manifest = load_manifest()
    spec = manifest["musicxml_schema"]
    override = os.environ.get(spec["override_env"], "").strip()
    return Path(override).expanduser().resolve() if override else (project_root() / spec["default_path"]).resolve()


def verify_schema(directory: Path | None = None) -> tuple[bool, list[str]]:
    manifest = load_manifest()
    spec = manifest["musicxml_schema"]
    directory = directory or target_schema_directory()
    errors: list[str] = []
    for name, expected in spec["files"].items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing: {name}")
        else:
            actual = _sha256(path)
            if actual.lower() != expected.lower():
                errors.append(f"hash mismatch: {name} expected={expected} actual={actual}")
    return not errors, errors


def install_schema(*, force: bool = False) -> int:
    manifest = load_manifest()
    spec = manifest["musicxml_schema"]
    target = target_schema_directory()
    valid, errors = verify_schema(target)
    if valid:
        source_record = {
            "version": spec["version"],
            "source_repository": spec["source_repository"],
            "source_tag": spec["source_tag"],
            "source_commit": spec["source_commit"],
            "files": spec["files"],
        }
        (target / "SOURCE.json").write_text(
            json.dumps(source_record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[PASS] MusicXML {spec['version']} schema already verified at {target}")
        return 0

    existing_files = [target / name for name in spec["files"] if (target / name).exists()]
    if existing_files and not force:
        print(f"[FAIL] Existing schema files are incomplete or do not match the pinned source at {target}")
        for error in errors:
            print(f"  {error}")
        print("  Move/backup the unknown files, then rerun; or pass --force after reviewing docs/MUSICXML_SCHEMA_SETUP.md.")
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="musicxml_schema_", dir=target.parent) as temp_name:
            temp_dir = Path(temp_name)
            for name, expected in spec["files"].items():
                url = f"{spec['raw_base_url']}/{name}"
                request = urllib.request.Request(url, headers={"User-Agent": "ScoreRebuild-schema-installer/0.1"})
                try:
                    with urllib.request.urlopen(request, timeout=45) as response:
                        data = response.read()
                except (OSError, urllib.error.URLError) as exc:
                    print(f"[FAIL] Could not download {url}: {exc}")
                    return 1
                path = temp_dir / name
                path.write_bytes(data)
                actual = _sha256(path)
                if actual.lower() != expected.lower():
                    print(f"[FAIL] SHA-256 mismatch for {name}: expected={expected} actual={actual}")
                    return 1

            source_record = {
                "version": spec["version"],
                "source_repository": spec["source_repository"],
                "source_tag": spec["source_tag"],
                "source_commit": spec["source_commit"],
                "files": spec["files"],
            }
            (temp_dir / "SOURCE.json").write_text(
                json.dumps(source_record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            target.mkdir(parents=True, exist_ok=True)
            for path in temp_dir.iterdir():
                shutil.copy2(path, target / path.name)
    except OSError as exc:
        print(f"[FAIL] Could not install schema into {target}: {exc}")
        return 1

    valid, errors = verify_schema(target)
    if not valid:
        print("[FAIL] Installed schema did not pass final verification:")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"[PASS] Installed verified MusicXML {spec['version']} schema at {target}")
    print(f"  source commit: {spec['source_commit']}")
    return 0
