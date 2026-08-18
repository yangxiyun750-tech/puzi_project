from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pypdf import PdfReader


PARTS = [
    ("01_Flute.mscz", "Flute.musicxml", "Flute"),
    ("02_Oboe.mscz", "Oboe.musicxml", "Oboe"),
    ("03_Bb_Clarinet.mscz", "Bb_Clarinet.musicxml", "B-flat Clarinet"),
    ("04_Bassoon.mscz", "Bassoon.musicxml", "Bassoon"),
    ("05_Horn_in_F_1.mscz", "Horn_in_F_1.musicxml", "Horn in F 1"),
    ("06_Horn_in_F_2.mscz", "Horn_in_F_2.musicxml", "Horn in F 2"),
    ("07_Timpani.mscz", "Timpani.musicxml", "Timpani"),
    ("08_Cymbals.mscz", "Cymbals.musicxml", "Cymbals"),
    ("09_Triangle.mscz", "Triangle.musicxml", "Triangle"),
    ("10_Glockenspiel.mscz", "Glockenspiel.musicxml", "Glockenspiel"),
    ("11_Vibraphone.mscz", "Vibraphone.musicxml", "Vibraphone"),
    ("12_Harp.mscz", "Harp.musicxml", "Harp"),
    ("13_Solo_Voice.mscz", "Solo_Voice.musicxml", "Solo Voice"),
    ("14_Violin_1.mscz", "Violin_1.musicxml", "Violin 1"),
    ("15_Violin_2.mscz", "Violin_2.musicxml", "Violin 2"),
    ("16_Viola.mscz", "Viola.musicxml", "Viola"),
    ("17_Violoncello.mscz", "Violoncello.musicxml", "Violoncello"),
    ("18_Double_Bass.mscz", "Double_Bass.musicxml", "Double Bass"),
]


def run_musescore(exe: Path, source: Path, destination: Path) -> None:
    completed = subprocess.run(
        [str(exe), "-o", str(destination), str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if completed.returncode or not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(
            f"MuseScore export failed: {source.name} -> {destination.name}; "
            f"exit={completed.returncode}; stderr={completed.stderr[-2000:]}"
        )


def mscx_root(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".mscx")]
        if len(names) != 1:
            raise RuntimeError(f"{path}: expected one .mscx member, got {names}")
        return ET.fromstring(archive.read(names[0]))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: logic_delivery_export.py MUSESCORE.exe MASTER.mscz PARTS_DIR "
            "ALL_PARTS.pdf OUTPUT_DIR"
        )
    exe, master, source_parts, source_parts_pdf, output = map(Path, sys.argv[1:])
    exe, master, source_parts, source_parts_pdf, output = [path.resolve() for path in (exe, master, source_parts, source_parts_pdf, output)]
    parts_xml = output / "parts_musicxml"
    validation = output / "validation_reopen"
    parts_xml.mkdir(parents=True, exist_ok=True)
    validation.mkdir(parents=True, exist_ok=True)

    master_copy = output / "天使的脸_Eb_MASTER_with_linked_parts.mscz"
    shutil.copy2(master, master_copy)
    full_xml = output / "天使的脸_Eb_full_score.musicxml"
    full_pdf = output / "天使的脸_Eb_full_score.pdf"
    all_parts_pdf = output / "天使的脸_Eb_all_parts.pdf"
    run_musescore(exe, master, full_xml)
    run_musescore(exe, master, full_pdf)
    shutil.copy2(source_parts_pdf, all_parts_pdf)

    records = []
    to_validate = [("Full Score", full_xml)]
    for mscz_name, xml_name, display_name in PARTS:
        source = source_parts / mscz_name
        if not source.is_file():
            raise RuntimeError(f"Missing linked-part artifact: {source}")
        target = parts_xml / xml_name
        run_musescore(exe, source, target)
        to_validate.append((display_name, target))

    for index, (display_name, xml_path) in enumerate(to_validate):
        reopened = validation / f"{index:02d}_{xml_path.stem}_reopened.mscz"
        roundtrip = validation / f"{index:02d}_{xml_path.stem}_roundtrip.musicxml"
        run_musescore(exe, xml_path, reopened)
        run_musescore(exe, reopened, roundtrip)
        root = ET.parse(xml_path).getroot()
        reopened_root = mscx_root(reopened)
        records.append(
            {
                "name": display_name,
                "musicxml": str(xml_path.relative_to(output)),
                "musicxml_bytes": xml_path.stat().st_size,
                "musicxml_sha256": sha256(xml_path),
                "reopened_mscz": str(reopened.relative_to(output)),
                "reopened_bytes": reopened.stat().st_size,
                "roundtrip_musicxml": str(roundtrip.relative_to(output)),
                "roundtrip_bytes": roundtrip.stat().st_size,
                "part_count": len(root.findall("part")),
                "measure_counts": [len(part.findall("measure")) for part in root.findall("part")],
                "reopened_score_count": len(reopened_root.findall("Score")),
            }
        )

    package = {
        "source_master": str(master),
        "source_master_sha256": sha256(master),
        "delivered_master_sha256": sha256(master_copy),
        "master_copy_identical": sha256(master) == sha256(master_copy),
        "full_score_pdf_pages": len(PdfReader(full_pdf).pages),
        "all_parts_pdf_pages": len(PdfReader(all_parts_pdf).pages),
        "musicxml_exports": records,
    }
    (output / "EXPORT_MANIFEST.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Exported and reopened {len(records)} MusicXML files; "
        f"full score PDF={package['full_score_pdf_pages']} pages; "
        f"all parts PDF={package['all_parts_pdf_pages']} pages."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
