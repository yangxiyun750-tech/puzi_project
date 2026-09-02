#!/usr/bin/env python3
"""Build generic Skill and ZCode marketplace ZIPs from the canonical Skill."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_ID = "focused-score-rebuild"
CANONICAL = ROOT / ".agents" / "skills" / SKILL_ID
VERSION = "0.1.0"
ZIP_TIME = (2020, 1, 1, 0, 0, 0)
LICENSE_ID = "AGPL-3.0-only"
LICENSE_FILE = ROOT / "LICENSE"


def zip_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output_dir: Path) -> dict[str, str]:
    if not (CANONICAL / "SKILL.md").is_file():
        raise FileNotFoundError(f"Canonical Skill is missing: {CANONICAL}")
    if not LICENSE_FILE.is_file():
        raise FileNotFoundError(f"Repository license is missing: {LICENSE_FILE}")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    skill_zip = output_dir / f"{SKILL_ID}-skill-{VERSION}.zip"
    zcode_zip = output_dir / f"{SKILL_ID}-zcode-marketplace-{VERSION}.zip"

    with tempfile.TemporaryDirectory(prefix="score_rebuild_packages_") as temp_name:
        temp = Path(temp_name)
        generic_root = temp / "generic"
        shutil.copytree(CANONICAL, generic_root / SKILL_ID)
        shutil.copy2(LICENSE_FILE, generic_root / "LICENSE")
        zip_tree(generic_root, skill_zip)

        market_root = temp / "zcode-marketplace"
        plugin_root = market_root / "plugins" / SKILL_ID
        shutil.copytree(CANONICAL, plugin_root / "skills" / SKILL_ID)
        (plugin_root / ".zcode-plugin").mkdir(parents=True)
        plugin_manifest = {
            "name": SKILL_ID,
            "version": VERSION,
            "description": "Human-guided reconstruction of clear melody, voice-piano, and basic concert-band scores.",
            "license": LICENSE_ID,
            "keywords": ["musicxml", "musescore", "audiveris", "omr", "sheet-music"],
            "skills": "skills",
        }
        (plugin_root / ".zcode-plugin" / "plugin.json").write_text(
            json.dumps(plugin_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(LICENSE_FILE, plugin_root / "LICENSE")
        marketplace = {
            "name": "score-rebuild-mainland",
            "description": "Local marketplace for the focused score rebuild Skill.",
            "pluginRoot": "plugins",
            "plugins": [{
                "name": SKILL_ID,
                "source": f"./{SKILL_ID}",
                "description": plugin_manifest["description"],
                "version": VERSION,
                "category": "Music",
                "tags": ["MusicXML", "OMR", "MuseScore"],
                "strict": True,
            }],
        }
        (market_root / "marketplace.json").write_text(
            json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        zip_tree(market_root, zcode_zip)

    checksums = {skill_zip.name: sha256(skill_zip), zcode_zip.name: sha256(zcode_zip)}
    checksum_path = output_dir / "SHA256SUMS.json"
    checksum_path.write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    return {"skill_zip": str(skill_zip), "zcode_zip": str(zcode_zip), "checksums": str(checksum_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
