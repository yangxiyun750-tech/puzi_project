from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


FEATURE_PATHS = {
    "lyrics": ".//lyric",
    "repeats": ".//repeat",
    "endings": ".//ending",
    "dynamics": ".//dynamics/*",
    "tuplets": ".//tuplet",
    "time_modifications": ".//time-modification",
    "arpeggios": ".//arpeggiate",
    "glissando_slides": ".//slide",
    "glissandos": ".//glissando",
}


def part_names(root: ET.Element) -> dict[str, str]:
    return {
        node.get("id", ""): node.findtext("part-name", "")
        for node in root.findall("./part-list/score-part")
    }


def note_signature(note: ET.Element) -> tuple:
    pitch = note.find("pitch")
    unpitched = note.find("unpitched")
    if pitch is not None:
        sound = (
            "pitch",
            pitch.findtext("step", ""),
            pitch.findtext("alter", "0"),
            pitch.findtext("octave", ""),
        )
    elif unpitched is not None:
        sound = (
            "unpitched",
            unpitched.findtext("display-step", ""),
            unpitched.findtext("display-octave", ""),
        )
    elif note.find("rest") is not None:
        sound = ("rest",)
    else:
        sound = ("unknown",)
    return (
        sound,
        note.find("chord") is not None,
        note.find("grace") is not None,
        note.findtext("duration", ""),
        note.findtext("voice", ""),
        note.findtext("type", ""),
        len(note.findall("dot")),
        note.findtext("staff", ""),
        tuple((node.get("type", ""), node.get("number", "")) for node in note.findall("tie")),
        tuple(node.text or "" for node in note.findall("time-modification/actual-notes")),
        tuple(node.text or "" for node in note.findall("time-modification/normal-notes")),
    )


def measure_signature(measure: ET.Element) -> dict:
    return {
        "number": measure.get("number", ""),
        "implicit": measure.get("implicit", ""),
        "keys": tuple(node.text or "" for node in measure.findall("./attributes/key/fifths")),
        "times": tuple(
            (node.findtext("beats", ""), node.findtext("beat-type", ""))
            for node in measure.findall("./attributes/time")
        ),
        "notes": tuple(note_signature(note) for note in measure.findall("note")),
        "backups": tuple(node.findtext("duration", "") for node in measure.findall("backup")),
        "forwards": tuple(node.findtext("duration", "") for node in measure.findall("forward")),
        "lyrics": tuple(
            (
                lyric.get("number", ""),
                lyric.findtext("syllabic", ""),
                lyric.findtext("text", ""),
                tuple(node.get("type", "") for node in lyric.findall("extend")),
            )
            for lyric in measure.findall("note/lyric")
        ),
        "repeats": tuple(
            (node.get("direction", ""), node.get("times", ""))
            for node in measure.findall("barline/repeat")
        ),
        "endings": tuple(
            (node.get("number", ""), node.get("type", ""))
            for node in measure.findall("barline/ending")
        ),
        "dynamics": tuple(node.tag for node in measure.findall(".//dynamics/*")),
        "tuplets": tuple(
            (node.get("type", ""), node.get("number", ""), node.get("bracket", ""))
            for node in measure.findall(".//tuplet")
        ),
        "time_modifications": tuple(
            (
                node.findtext("actual-notes", ""),
                node.findtext("normal-notes", ""),
            )
            for node in measure.findall(".//time-modification")
        ),
        "arpeggios": tuple(
            (node.get("number", ""), node.get("direction", ""))
            for node in measure.findall(".//arpeggiate")
        ),
        "slides": tuple(
            (node.get("type", ""), node.get("number", ""), node.text or "")
            for node in measure.findall(".//slide")
        ),
        "glissandos": tuple(
            (node.get("type", ""), node.get("number", ""), node.text or "")
            for node in measure.findall(".//glissando")
        ),
    }


def summarize(root: ET.Element) -> dict:
    names = part_names(root)
    data = {
        "part_names": [names.get(part.get("id", ""), "") for part in root.findall("part")],
        "measure_counts": [len(part.findall("measure")) for part in root.findall("part")],
        "keys_by_part": {},
        "transpose_by_part": {},
        "features": {name: len(root.findall(path)) for name, path in FEATURE_PATHS.items()},
    }
    for part in root.findall("part"):
        name = names.get(part.get("id", ""), "")
        data["keys_by_part"][name] = [
            int(node.text or "0") for node in part.findall("./measure/attributes/key/fifths")
        ]
        chromatic = part.findtext("./measure/attributes/transpose/chromatic")
        octave = part.findtext("./measure/attributes/transpose/octave-change")
        data["transpose_by_part"][name] = [int(chromatic or "0"), int(octave or "0")]
    return data


def compare(original: Path, roundtrip: Path) -> tuple[list[str], dict]:
    original_root = ET.parse(original).getroot()
    roundtrip_root = ET.parse(roundtrip).getroot()
    errors: list[str] = []
    original_names = part_names(original_root)
    roundtrip_names = part_names(roundtrip_root)
    original_parts = original_root.findall("part")
    roundtrip_parts = roundtrip_root.findall("part")
    if len(original_parts) != len(roundtrip_parts):
        errors.append(f"part count {len(original_parts)} -> {len(roundtrip_parts)}")
    for part_index, (left_part, right_part) in enumerate(zip(original_parts, roundtrip_parts), start=1):
        left_name = original_names.get(left_part.get("id", ""), f"part {part_index}")
        right_name = roundtrip_names.get(right_part.get("id", ""), f"part {part_index}")
        if left_name != right_name:
            errors.append(f"part {part_index} name {left_name!r} -> {right_name!r}")
        left_measures = left_part.findall("measure")
        right_measures = right_part.findall("measure")
        if len(left_measures) != len(right_measures):
            errors.append(f"{left_name}: measure count {len(left_measures)} -> {len(right_measures)}")
        for measure_index, (left, right) in enumerate(zip(left_measures, right_measures), start=1):
            left_sig = measure_signature(left)
            right_sig = measure_signature(right)
            for field in left_sig:
                if left_sig[field] != right_sig[field]:
                    errors.append(f"{left_name} m{measure_index}: {field} changed")

    original_summary = summarize(original_root)
    roundtrip_summary = summarize(roundtrip_root)
    for field in ("part_names", "measure_counts", "keys_by_part", "transpose_by_part", "features"):
        if original_summary[field] != roundtrip_summary[field]:
            errors.append(f"global {field} changed")
    return errors, original_summary


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: logic_validate_musicxml.py LOGIC_PRO_DELIVERY")
    delivery = Path(sys.argv[1]).resolve()
    manifest = json.loads((delivery / "EXPORT_MANIFEST.json").read_text(encoding="utf-8"))
    results = []
    all_errors: list[str] = []

    for record in manifest["musicxml_exports"]:
        original = delivery / record["musicxml"]
        roundtrip = delivery / record["roundtrip_musicxml"]
        errors, summary = compare(original, roundtrip)
        results.append({"name": record["name"], "status": "PASS" if not errors else "FAIL", "errors": errors, "summary": summary})
        all_errors.extend(f"{record['name']}: {error}" for error in errors)

    full = results[0]["summary"]
    expected_keys = {
        "B-flat Clarinet": {-1},
        "Horn in F 1": {-2},
        "Horn in F 2": {-2},
    }
    for name, expected in expected_keys.items():
        actual = set(full["keys_by_part"].get(name, []))
        if actual != expected:
            all_errors.append(f"Full Score: {name} written key {sorted(actual)}, expected {sorted(expected)}")
    for name, expected in {
        "B-flat Clarinet": [-2, 0],
        "Horn in F 1": [-7, 0],
        "Horn in F 2": [-7, 0],
    }.items():
        actual = full["transpose_by_part"].get(name)
        if actual != expected:
            all_errors.append(f"Full Score: {name} transpose {actual}, expected {expected}")
    for name in full["part_names"]:
        if name not in {"B-flat Clarinet", "Horn in F 1", "Horn in F 2", "Cymbals", "Triangle"}:
            keys = set(full["keys_by_part"].get(name, []))
            if keys and keys != {-3}:
                all_errors.append(f"Full Score: {name} written key {sorted(keys)}, expected [-3]")

    required_features = {
        "lyrics": 199,
        "repeats": 36,
        "endings": 12,
        "tuplets": 24,
        "time_modifications": 90,
        "arpeggios": 42,
        "glissando_slides": 2,
    }
    for feature, expected in required_features.items():
        actual = full["features"].get(feature, 0)
        if actual != expected:
            all_errors.append(f"Full Score: {feature} count {actual}, expected {expected}")

    report = {
        "status": "PASS" if not all_errors else "FAIL",
        "files_checked": len(results),
        "results": results,
        "errors": all_errors,
    }
    (delivery / "MUSICXML_VALIDATION.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(report["status"])
    print(f"Validated {len(results)} MusicXML exports; findings={len(all_errors)}")
    for error in all_errors[:200]:
        print(f"- {error}")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
