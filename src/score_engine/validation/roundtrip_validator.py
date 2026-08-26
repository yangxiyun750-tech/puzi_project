"""Round-trip validation: MusicXML → ScoreIR → MusicXML.

Compares musical semantics (not XML text) before and after the round trip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from score_engine.score_ir.score_ir import (
    Articulation,
    Dynamic,
    Lyric,
    Note,
    Part,
    Rest,
    Score,
    Slur,
    Tie,
)


@dataclass
class Finding:
    """A single validation finding."""
    severity: str  # ERROR | WARNING | INFO
    part_id: str
    measure_number: str
    voice_id: str
    note_id: str
    category: str  # pitch, rhythm, tie, slur, dynamic, articulation, lyric, ...
    expected: str
    actual: str
    description: str


@dataclass
class ValidationReport:
    """Complete round-trip validation report."""
    status: str  # PASS | FAIL
    score_title: str
    total_parts: int
    total_measures: int
    total_notes: int
    findings: list[Finding] = field(default_factory=list)

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "WARNING"]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "score_title": self.score_title,
            "total_parts": self.total_parts,
            "total_measures": self.total_measures,
            "total_notes": self.total_notes,
            "errors": len(self.errors()),
            "warnings": len(self.warnings()),
            "findings": [
                {
                    "severity": f.severity,
                    "part_id": f.part_id,
                    "measure_number": f.measure_number,
                    "voice_id": f.voice_id,
                    "note_id": f.note_id,
                    "category": f.category,
                    "expected": f.expected,
                    "actual": f.actual,
                    "description": f.description,
                }
                for f in self.findings
            ],
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def save_markdown(self, path: str | Path) -> None:
        lines = [
            "# Round-trip Validation Report",
            "",
            f"- Score: {self.score_title}",
            f"- Status: **{self.status}**",
            f"- Parts: {self.total_parts}",
            f"- Measures: {self.total_measures}",
            f"- Notes: {self.total_notes}",
            f"- Errors: {len(self.errors())}",
            f"- Warnings: {len(self.warnings())}",
            "",
            "## Findings",
            "",
            "| Severity | Part | Measure | Voice | Note ID | Category | Expected | Actual | Description |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for f in self.findings:
            lines.append(
                f"| {f.severity} | {f.part_id} | {f.measure_number} | {f.voice_id} | {f.note_id} | "
                f"{f.category} | {f.expected} | {f.actual} | {f.description} |"
            )
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class RoundtripValidator:
    """Validate that ScoreIR preserves musical semantics through MusicXML round-trip."""

    def validate(self, original: Score, roundtrip: Score) -> ValidationReport:
        report = ValidationReport(
            status="PASS",
            score_title=original.title,
            total_parts=len(original.parts),
            total_measures=sum(len(p.measures) for p in original.parts),
            total_notes=sum(
                sum(len(v.events) for v in m.voices)
                for p in original.parts
                for m in p.measures
                for v in m.voices
            ),
        )

        # Part count
        if len(original.parts) != len(roundtrip.parts):
            report.findings.append(Finding(
                "ERROR", "", "", "", "",
                "part_count",
                str(len(original.parts)),
                str(len(roundtrip.parts)),
                "Part count mismatch",
            ))

        for orig_part, rt_part in zip(original.parts, roundtrip.parts):
            self._validate_part(orig_part, rt_part, report)

        if report.errors():
            report.status = "FAIL"
        return report

    def _validate_part(self, orig: Part, rt: Part, report: ValidationReport) -> None:
        if orig.name != rt.name:
            report.findings.append(Finding(
                "ERROR", orig.id, "", "", "",
                "part_name", orig.name, rt.name,
                "Part name changed",
            ))

        if len(orig.measures) != len(rt.measures):
            report.findings.append(Finding(
                "ERROR", orig.id, "", "", "",
                "measure_count",
                str(len(orig.measures)),
                str(len(rt.measures)),
                "Measure count mismatch",
            ))

        for orig_m, rt_m in zip(orig.measures, rt.measures):
            self._validate_measure(orig.id, orig_m, rt_m, report)

    def _validate_measure(self, part_id: str, orig: Measure, rt: Measure,
                          report: ValidationReport) -> None:
        if orig.number != rt.number:
            report.findings.append(Finding(
                "ERROR", part_id, orig.number, "", "",
                "measure_number", orig.number, rt.number,
                "Measure number changed",
            ))

        if orig.key_signature != rt.key_signature:
            report.findings.append(Finding(
                "ERROR", part_id, orig.number, "", "",
                "key_signature",
                str(orig.key_signature),
                str(rt.key_signature),
                "Key signature changed",
            ))

        if orig.time_signature != rt.time_signature:
            report.findings.append(Finding(
                "ERROR", part_id, orig.number, "", "",
                "time_signature",
                str(orig.time_signature),
                str(rt.time_signature),
                "Time signature changed",
            ))

        if orig.tempo != rt.tempo:
            report.findings.append(Finding(
                "WARNING", part_id, orig.number, "", "",
                "tempo", str(orig.tempo), str(rt.tempo),
                "Tempo marking changed",
            ))

        # Voice count
        if len(orig.voices) != len(rt.voices):
            report.findings.append(Finding(
                "ERROR", part_id, orig.number, "", "",
                "voice_count",
                str(len(orig.voices)),
                str(len(rt.voices)),
                "Voice count mismatch",
            ))

        for orig_v, rt_v in zip(orig.voices, rt.voices):
            self._validate_voice(part_id, orig.number, orig_v, rt_v, report)

    def _validate_voice(self, part_id: str, measure_num: str,
                        orig, rt, report: ValidationReport) -> None:
        if len(orig.events) != len(rt.events):
            report.findings.append(Finding(
                "ERROR", part_id, measure_num, orig.id, "",
                "event_count",
                str(len(orig.events)),
                str(len(rt.events)),
                "Event count mismatch in voice",
            ))

        for orig_e, rt_e in zip(orig.events, rt.events):
            self._validate_event(part_id, measure_num, orig.id, orig_e, rt_e, report)

    def _validate_event(self, part_id: str, measure_num: str, voice_id: str,
                        orig, rt, report: ValidationReport) -> None:
        # Pitch comparison
        if isinstance(orig, Note) and isinstance(rt, Note):
            if orig.pitch != rt.pitch:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "pitch",
                    str(orig.pitch),
                    str(rt.pitch),
                    "Pitch changed",
                ))
            if orig.duration.value != rt.duration.value:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "duration",
                    str(orig.duration.value),
                    str(rt.duration.value),
                    "Duration changed",
                ))
            if orig.type != rt.type:
                report.findings.append(Finding(
                    "WARNING", part_id, measure_num, voice_id, orig.id,
                    "note_type", orig.type, rt.type,
                    "Note type changed",
                ))
            # Ties
            orig_ties = {(t.type, t.number) for t in orig.ties}
            rt_ties = {(t.type, t.number) for t in rt.ties}
            if orig_ties != rt_ties:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "tie", str(orig_ties), str(rt_ties),
                    "Tie set changed",
                ))
            # Slurs
            orig_slurs = {(s.type, s.number) for s in orig.slurs}
            rt_slurs = {(s.type, s.number) for s in rt.slurs}
            if orig_slurs != rt_slurs:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "slur", str(orig_slurs), str(rt_slurs),
                    "Slur set changed",
                ))
            # Articulations
            orig_arts = {a.mark for a in orig.articulations}
            rt_arts = {a.mark for a in rt.articulations}
            if orig_arts != rt_arts:
                report.findings.append(Finding(
                    "WARNING", part_id, measure_num, voice_id, orig.id,
                    "articulation", str(orig_arts), str(rt_arts),
                    "Articulation set changed",
                ))
            # Lyrics
            orig_lyrics = {(l.number, l.text) for l in orig.lyrics}
            rt_lyrics = {(l.number, l.text) for l in rt.lyrics}
            if orig_lyrics != rt_lyrics:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "lyric", str(orig_lyrics), str(rt_lyrics),
                    "Lyric set changed",
                ))

        elif isinstance(orig, Rest) and isinstance(rt, Rest):
            if orig.duration.value != rt.duration.value:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id, orig.id,
                    "rest_duration",
                    str(orig.duration.value),
                    str(rt.duration.value),
                    "Rest duration changed",
                ))

        elif isinstance(orig, Note) and isinstance(rt, Rest):
            # Note with pitch=None is semantically a rest
            if orig.pitch is not None:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id,
                    getattr(orig, "id", "?"),
                    "event_type",
                    type(orig).__name__,
                    type(rt).__name__,
                    "Event type changed (Note ↔ Rest ↔ Chord)",
                ))

        elif isinstance(orig, Rest) and isinstance(rt, Note):
            # Rest imported as Note(pitch=None) is semantically equivalent
            if rt.pitch is not None:
                report.findings.append(Finding(
                    "ERROR", part_id, measure_num, voice_id,
                    getattr(orig, "id", "?"),
                    "event_type",
                    type(orig).__name__,
                    type(rt).__name__,
                    "Event type changed (Note ↔ Rest ↔ Chord)",
                ))

        elif isinstance(orig, Note) != isinstance(rt, Note):
            report.findings.append(Finding(
                "ERROR", part_id, measure_num, voice_id,
                getattr(orig, "id", "?"),
                "event_type",
                type(orig).__name__,
                type(rt).__name__,
                "Event type changed (Note ↔ Rest ↔ Chord)",
            ))


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------


def test_roundtrip() -> None:
    from score_rebuild.private_fixture import private_fixture_output_dir, print_private_fixture_status

    fixture = print_private_fixture_status()
    if not fixture.available or fixture.path is None:
        return

    from src.musicxml.musicxml_to_score_ir import MusicXMLImporter
    from src.musicxml.score_ir_to_musicxml import MusicXMLExporter
    path = fixture.path
    output_dir = private_fixture_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Import
    importer = MusicXMLImporter()
    original = importer.import_file(path)

    # Export
    exporter = MusicXMLExporter()
    tree = exporter.export(original)
    rt_path = output_dir / "score_ir_roundtrip.musicxml"
    tree.write(rt_path, encoding="utf-8", xml_declaration=True)

    # Re-import
    roundtrip = importer.import_file(rt_path)

    # Validate
    validator = RoundtripValidator()
    report = validator.validate(original, roundtrip)
    report.save_json(output_dir / "ROUNDTRIP_SCORE_IR.json")
    report.save_markdown(output_dir / "ROUNDTRIP_SCORE_IR.md")

    print(f"Status: {report.status}")
    print(f"Errors: {len(report.errors())}")
    print(f"Warnings: {len(report.warnings())}")
    print(f"Report: {output_dir / 'ROUNDTRIP_SCORE_IR.md'}")


if __name__ == "__main__":
    test_roundtrip()
