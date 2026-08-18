from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader


EXPECTED_PARTS = [
    "Flute.musicxml", "Oboe.musicxml", "Bb_Clarinet.musicxml", "Bassoon.musicxml",
    "Horn_in_F_1.musicxml", "Horn_in_F_2.musicxml", "Timpani.musicxml",
    "Cymbals.musicxml", "Triangle.musicxml", "Glockenspiel.musicxml",
    "Vibraphone.musicxml", "Harp.musicxml", "Solo_Voice.musicxml",
    "Violin_1.musicxml", "Violin_2.musicxml", "Viola.musicxml",
    "Violoncello.musicxml", "Double_Bass.musicxml",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: logic_validate_package.py LOGIC_PRO_DELIVERY")
    root = Path(sys.argv[1]).resolve()
    required = [
        root / "天使的脸_Eb_full_score.musicxml",
        root / "天使的脸_Eb_MASTER_with_linked_parts.mscz",
        root / "天使的脸_Eb_full_score.pdf",
        root / "天使的脸_Eb_all_parts.pdf",
        root / "LOGIC_IMPORT_NOTES.txt",
        root / "MUSICXML_VALIDATION.json",
        root / "FULL_SCORE_INVARIANTS.md",
        root / "EXPORT_MANIFEST.json",
    ]
    errors: list[str] = []
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing or empty: {path.name}")

    actual_parts = sorted(path.name for path in (root / "parts_musicxml").glob("*.musicxml"))
    if actual_parts != sorted(EXPECTED_PARTS):
        errors.append(f"Part filenames differ: {actual_parts}")
    for part_name in EXPECTED_PARTS:
        path = root / "parts_musicxml" / part_name
        if path.is_file():
            parsed = ET.parse(path).getroot()
            if len(parsed.findall("part")) != 1:
                errors.append(f"{part_name}: expected one MusicXML part")
            if len(parsed.findall("part/measure")) != 54:
                errors.append(f"{part_name}: expected 54 measures")

    validation = json.loads((root / "MUSICXML_VALIDATION.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or validation.get("files_checked") != 19:
        errors.append("MusicXML validation did not pass for all 19 files")
    invariants = (root / "FULL_SCORE_INVARIANTS.md").read_text(encoding="utf-8")
    if "**PASS**" not in invariants:
        errors.append("Full-score invariant report is not PASS")
    if len(PdfReader(root / "天使的脸_Eb_full_score.pdf").pages) != 8:
        errors.append("Full-score PDF is not 8 pages")
    if len(PdfReader(root / "天使的脸_Eb_all_parts.pdf").pages) != 19:
        errors.append("All-parts PDF is not 19 pages")

    final_files = [path for path in root.rglob("*") if path.is_file()]
    report = {
        "status": "PASS" if not errors else "FAIL",
        "required_musicxml": 19,
        "part_musicxml": len(actual_parts),
        "full_score_pdf_pages": len(PdfReader(root / "天使的脸_Eb_full_score.pdf").pages),
        "all_parts_pdf_pages": len(PdfReader(root / "天使的脸_Eb_all_parts.pdf").pages),
        "files": {
            str(path.relative_to(root)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(final_files)
            if "validation_reopen" not in path.parts
        },
        "errors": errors,
    }
    (root / "PACKAGE_VALIDATION.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(report["status"])
    print(
        f"19 MusicXML exports; {len(actual_parts)} part filenames; "
        f"8 score PDF pages; 19 parts PDF pages; errors={len(errors)}"
    )
    for error in errors:
        print(f"- {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
