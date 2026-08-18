#!/usr/bin/env python3
"""Audit structural invariants between pre/post-transposition MusicXML."""

from __future__ import annotations

import argparse
import copy
import sys
import zipfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def direct(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if local(child.tag) == name]


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if local(node.tag) == name]


def text(element: ET.Element, name: str, default: str = "") -> str:
    for child in element:
        if local(child.tag) == name:
            return (child.text or "").strip()
    return default


def duration(element: ET.Element, divisions: int) -> Fraction:
    try:
        return Fraction(int(text(element, "duration", "0")), divisions)
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def read_root(path: Path) -> ET.Element:
    if path.suffix.casefold() != ".mxl":
        return ET.parse(path).getroot()
    with zipfile.ZipFile(path) as archive:
        rootfile = ""
        try:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            for node in container.iter():
                if local(node.tag) == "rootfile":
                    rootfile = node.attrib.get("full-path", "")
                    if rootfile:
                        break
        except KeyError:
            pass
        if not rootfile:
            candidates = [
                name for name in archive.namelist()
                if name.casefold().endswith((".xml", ".musicxml"))
                and name.casefold() != "meta-inf/container.xml"
            ]
            if not candidates:
                raise ValueError(f"No MusicXML document found in {path}")
            rootfile = candidates[0]
        return ET.fromstring(archive.read(rootfile))


def mark_values(measure: ET.Element) -> dict[str, tuple[str, ...]]:
    dynamics: list[str] = []
    for group in descendants(measure, "dynamics"):
        dynamics.extend(local(child.tag) for child in group)
    articulations: list[str] = []
    for group in descendants(measure, "articulations"):
        articulations.extend(local(child.tag) for child in group)
    tempo = [
        f"sound:{node.attrib['tempo']}"
        for node in descendants(measure, "sound") if "tempo" in node.attrib
    ]
    tempo.extend(
        "metronome:"
        + "+".join((node.text or "").strip() for node in descendants(mark, "beat-unit"))
        + "="
        + "+".join((node.text or "").strip() for node in descendants(mark, "per-minute"))
        for mark in descendants(measure, "metronome")
    )

    def typed(name: str) -> tuple[str, ...]:
        return tuple(node.attrib.get("type", "") for node in descendants(measure, name))

    beam_values = tuple(
        f"{node.attrib.get('number', '1')}:{(node.text or '').strip()}"
        for node in descendants(measure, "beam")
    )
    time_modifications = tuple(
        f"{text(node, 'actual-notes')}:{text(node, 'normal-notes')}:{text(node, 'normal-type')}"
        for node in descendants(measure, "time-modification")
    )

    return {
        "dynamics": tuple(dynamics),
        "articulations": tuple(articulations),
        "tempo": tuple(tempo),
        "lyrics": tuple(
            " ".join((node.text or "").strip() for node in descendants(lyric, "text"))
            for lyric in descendants(measure, "lyric")
        ),
        "repeats": tuple(
            f"{node.attrib.get('direction', '')}:{node.attrib.get('times', '')}"
            for node in descendants(measure, "repeat")
        ),
        "endings": tuple(
            f"{node.attrib.get('type', '')}:{node.attrib.get('number', '')}"
            for node in descendants(measure, "ending")
        ),
        "rehearsal": tuple(
            " ".join("".join(node.itertext()).split())
            for node in descendants(measure, "rehearsal")
        ),
        "wedges": typed("wedge"),
        "ties": typed("tie") + typed("tied"),
        "slurs": typed("slur"),
        "tuplets": typed("tuplet"),
        "time_modifications": time_modifications,
        "beams": beam_values,
        "noteheads": tuple((node.text or "").strip() for node in descendants(measure, "notehead")),
        "tremolos": tuple(
            f"{node.attrib.get('type', '')}:{(node.text or '').strip()}"
            for node in descendants(measure, "tremolo")
        ),
        "clefs": tuple(
            f"{text(node, 'sign')}:{text(node, 'line')}:{node.attrib.get('number', '')}"
            for node in descendants(measure, "clef")
        ),
        "key_events": tuple("key" for _ in descendants(measure, "key")),
    }


@dataclass
class Measure:
    number: str
    implicit: bool
    meter: tuple[int, int] | None
    events: tuple[tuple[str, ...], ...]
    marks: dict[str, tuple[str, ...]]
    issues: list[str] = field(default_factory=list)


@dataclass
class Part:
    name: str
    measures: list[Measure]


def audit(root: ET.Element) -> list[Part]:
    if local(root.tag) != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is supported")
    names = {
        node.attrib.get("id", ""): text(node, "part-name", node.attrib.get("id", ""))
        for node in descendants(root, "score-part")
    }
    parts: list[Part] = []
    for part_node in direct(root, "part"):
        divisions = 1
        meter: tuple[int, int] | None = None
        measures: list[Measure] = []
        for measure_node in direct(part_node, "measure"):
            cursor = Fraction(0)
            max_end = Fraction(0)
            previous_start = Fraction(0)
            events: list[tuple[str, ...]] = []
            issues: list[str] = []
            for child in measure_node:
                kind = local(child.tag)
                if kind == "attributes":
                    raw = text(child, "divisions")
                    if raw:
                        try:
                            divisions = max(1, int(raw))
                        except ValueError:
                            issues.append(f"invalid divisions {raw!r}")
                    time_nodes = direct(child, "time")
                    if time_nodes:
                        try:
                            meter = (int(text(time_nodes[0], "beats")), int(text(time_nodes[0], "beat-type")))
                        except ValueError:
                            issues.append("invalid time signature")
                elif kind == "backup":
                    cursor -= duration(child, divisions)
                    if cursor < 0:
                        issues.append("timeline cursor moved before measure start")
                elif kind == "forward":
                    cursor += duration(child, divisions)
                    max_end = max(max_end, cursor)
                elif kind == "note":
                    chord = bool(direct(child, "chord"))
                    grace = bool(direct(child, "grace"))
                    rest = bool(direct(child, "rest"))
                    note_duration = Fraction(0) if grace else duration(child, divisions)
                    start = previous_start if chord else cursor
                    if not chord:
                        previous_start = start
                        cursor += note_duration
                    max_end = max(max_end, start + note_duration)
                    events.append((
                        fraction_text(start), fraction_text(note_duration),
                        text(child, "voice", "1"), text(child, "staff", "1"),
                        "rest" if rest else "note", "grace" if grace else "timed",
                        "chord" if chord else "onset",
                    ))
            implicit = measure_node.attrib.get("implicit", "no").casefold() == "yes"
            expected = Fraction(meter[0] * 4, meter[1]) if meter else None
            if expected is not None and max_end != expected and not implicit:
                issues.append(
                    f"duration {fraction_text(max_end)} quarters; expected {fraction_text(expected)}"
                )
            measures.append(Measure(
                measure_node.attrib.get("number", str(len(measures) + 1)),
                implicit, meter, tuple(sorted(events)), mark_values(measure_node), issues,
            ))
        part_id = part_node.attrib.get("id", "")
        parts.append(Part(names.get(part_id, part_id), measures))
    return parts


def compare(before: list[Part] | None, after: list[Part]) -> tuple[list[str], list[tuple[str, str, str]]]:
    global_findings: list[str] = []
    measure_findings = [
        (part.name, measure.number, issue)
        for part in after for measure in part.measures for issue in measure.issues
    ]
    if before is None:
        return global_findings, measure_findings
    if len(before) != len(after):
        global_findings.append(f"part count changed: {len(before)} → {len(after)}")
    for index, (old_part, new_part) in enumerate(zip(before, after), start=1):
        label = new_part.name or old_part.name or f"part {index}"
        if old_part.name != new_part.name:
            global_findings.append(f"part {index} name changed: {old_part.name!r} → {new_part.name!r}")
        if len(old_part.measures) != len(new_part.measures):
            global_findings.append(
                f"{label}: measure count changed: {len(old_part.measures)} → {len(new_part.measures)}"
            )
        for old, new in zip(old_part.measures, new_part.measures):
            number = new.number or old.number
            if old.number != new.number:
                measure_findings.append((label, number, f"measure label changed from {old.number!r}"))
            if old.meter != new.meter:
                measure_findings.append((label, number, f"meter changed: {old.meter} → {new.meter}"))
            if old.implicit != new.implicit:
                measure_findings.append((label, number, "implicit/pickup status changed"))
            if old.events != new.events:
                measure_findings.append((label, number, "rhythmic event or note/rest count changed"))
            for category, values in old.marks.items():
                if values != new.marks.get(category, ()):
                    measure_findings.append((label, number, f"{category} changed"))
    return global_findings, measure_findings


def escaped(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_report(
    output: Path,
    baseline_path: Path | None,
    candidate_path: Path,
    before: list[Part] | None,
    after: list[Part],
    global_findings: list[str],
    measure_findings: list[tuple[str, str, str]],
) -> None:
    lines = [
        "# MusicXML Structural Audit", "",
        f"- Baseline: `{baseline_path}`" if baseline_path else "- Baseline: not supplied",
        f"- Candidate: `{candidate_path}`",
        f"- Result: **{'REVIEW REQUIRED' if global_findings or measure_findings else 'PASS'}**", "",
        "Pitch values and key-signature fifths are intentionally excluded because transposition is expected.", "",
        "## Part inventory", "",
        "| # | Baseline part | Candidate part | Baseline measures | Candidate measures |",
        "|---:|---|---|---:|---:|",
    ]
    max_parts = max(len(before) if before else 0, len(after))
    for index in range(max_parts):
        old = before[index] if before and index < len(before) else None
        new = after[index] if index < len(after) else None
        lines.append(
            f"| {index + 1} | {escaped(old.name if old else '—')} | {escaped(new.name if new else '—')} | "
            f"{len(old.measures) if old else '—'} | {len(new.measures) if new else '—'} |"
        )
    lines.extend(["", "## Global findings", ""])
    lines.extend((f"- {item}" for item in global_findings) if global_findings else ["- None."])
    lines.extend(["", "## Suspicious measures", "", "| Part | Measure | Reason |", "|---|---:|---|"])
    if measure_findings:
        lines.extend(f"| {escaped(p)} | {escaped(m)} | {escaped(r)} |" for p, m, r in measure_findings)
    else:
        lines.append("| — | — | None detected by this structural audit. |")
    lines.extend([
        "", "This audit does not validate printed-source pitch accuracy, graphical attachments, collisions, or engraving.", ""
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def self_test() -> int:
    source = """<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Flute</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>5</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><direction><direction-type><dynamics><mf/></dynamics></direction-type></direction><note><pitch><step>B</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>whole</type></note></measure></part></score-partwise>"""
    root = ET.fromstring(source)
    baseline = audit(root)
    assert compare(baseline, audit(copy.deepcopy(root))) == ([], [])
    changed = copy.deepcopy(root)
    descendants(changed, "duration")[0].text = "3"
    _, findings = compare(baseline, audit(changed))
    assert any("rhythmic event" in finding[2] for finding in findings)
    assert any("duration" in finding[2] for finding in findings)
    print("musicxml_invariants.py self-test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare MusicXML structure while ignoring expected pitch transposition."
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-findings", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and (not args.candidate or not args.output):
        parser.error("--candidate and --output are required unless --self-test is used")
    return args


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()
    try:
        before = audit(read_root(args.baseline)) if args.baseline else None
        after = audit(read_root(args.candidate))
        global_findings, measure_findings = compare(before, after)
        write_report(args.output, args.baseline, args.candidate, before, after, global_findings, measure_findings)
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output} with {len(global_findings)} global and {len(measure_findings)} measure findings")
    return 1 if args.fail_on_findings and (global_findings or measure_findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
