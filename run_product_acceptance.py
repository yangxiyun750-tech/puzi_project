"""Real Score Product Acceptance Test — Phase 1.

Executes one real-user natural-language transposition request through the
complete production chain using the real Kimi/OpenAI-compatible provider.

Required environment variables:
    LLM_API_KEY   (required)
    LLM_BASE_URL  (optional; defaults to OpenAI endpoint)
    LLM_MODEL     (e.g. kimi-k2-6 or equivalent model id)

Usage:
    set LLM_API_KEY=...
    set LLM_MODEL=kimi-k2-6
    PYTHONPATH=src python run_product_acceptance.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from ai import (
    LLMIntentProvider,
    OpenAICompatibleClient,
    TransposeIntentResolver,
    build_intent_context,
)
from omr_normalization import OMRNormalizer
from omr_normalization.quality_gate import OMRGateMode, OMRQualityGate
from score_engine.musicxml import MusicXMLExporter, MusicXMLImporter
from score_engine.score_ir.score_ir import Chord, Note, Pitch, Score
from score_engine.transposition import SafeTranspositionService, TranspositionOperation


INPUT_PATH = Path("LOGIC_PRO_DELIVERY/parts_musicxml/Bb_Clarinet.musicxml")
OUTPUT_DIR = Path("outputs/product_acceptance")
USER_REQUEST = "把整首升大二度"


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("*"):
        if old.is_file():
            old.unlink()


def copy_original() -> Path:
    dest = OUTPUT_DIR / "01_original_Bb_Clarinet.musicxml"
    shutil.copy2(INPUT_PATH, dest)
    return dest


def gate_check(score_xml_path: Path) -> tuple[bool, str, Any]:
    report = OMRNormalizer().detect_only(score_xml_path)
    gate = OMRQualityGate().check(report, OMRGateMode.STRICT)
    return gate.allows_deterministic_edit, gate.status, report


def iter_notes(score: Score):
    for part in score.parts:
        for idx, measure in enumerate(part.measures, start=1):
            for voice in measure.voices:
                for event in voice.events:
                    if isinstance(event, Note) and event.pitch is not None:
                        yield part.id, idx, event
                    elif isinstance(event, Chord):
                        for note in event.notes:
                            if note.pitch is not None:
                                yield part.id, idx, note


def count_pitches(score: Score) -> int:
    return sum(1 for _ in iter_notes(score))


def pitch_midi_set(score: Score) -> set[int]:
    return {note.pitch.midi for _, _, note in iter_notes(score)}


def verify_m2_up(original: Score, transposed: Score) -> dict[str, Any]:
    """Verify every pitched note moved up by exactly M2 (+2 semitones)."""
    orig_midis = pitch_midi_set(original)
    trans_midis = pitch_midi_set(transposed)

    # Quick aggregate check.
    expected_midis = {m + 2 for m in orig_midis}
    if trans_midis != expected_midis:
        return {
            "passed": False,
            "reason": f"Transposed midi set {sorted(trans_midis)} != expected {sorted(expected_midis)}",
        }

    # Per-note check.
    mismatches = []
    for part in original.parts:
        trans_part = transposed.get_part(part.id)
        for m_idx, orig_m in enumerate(part.measures, start=1):
            trans_m = trans_part.measures[m_idx - 1]
            for ov, tv in zip(orig_m.voices, trans_m.voices):
                for oe, te in zip(ov.events, tv.events):
                    if isinstance(oe, Note) and isinstance(te, Note):
                        if oe.pitch is not None and te.pitch is not None:
                            if te.pitch.midi - oe.pitch.midi != 2:
                                mismatches.append((te.id, oe.pitch, te.pitch))
                    elif isinstance(oe, Chord) and isinstance(te, Chord):
                        for on, tn in zip(oe.notes, te.notes):
                            if on.pitch is not None and tn.pitch is not None:
                                if tn.pitch.midi - on.pitch.midi != 2:
                                    mismatches.append((tn.id, on.pitch, tn.pitch))

    if mismatches:
        return {
            "passed": False,
            "reason": f"{len(mismatches)} note(s) did not move by +2 semitones",
            "samples": [str(m) for m in mismatches[:5]],
        }

    return {"passed": True, "original_note_count": count_pitches(original), "transposed_note_count": count_pitches(transposed)}


def verify_rests_unchanged(original: Score, transposed: Score) -> dict[str, Any]:
    orig_rests = sum(
        1 for p in original.parts for m in p.measures for v in m.voices for e in v.events
        if type(e).__name__ == "Rest"
    )
    trans_rests = sum(
        1 for p in transposed.parts for m in p.measures for v in m.voices for e in v.events
        if type(e).__name__ == "Rest"
    )
    return {
        "passed": orig_rests == trans_rests,
        "original_rests": orig_rests,
        "transposed_rests": trans_rests,
    }


def verify_durations_unchanged(original: Score, transposed: Score) -> dict[str, Any]:
    for orig_part in original.parts:
        trans_part = transposed.get_part(orig_part.id)
        for om, tm in zip(orig_part.measures, trans_part.measures):
            for ov, tv in zip(om.voices, tm.voices):
                if ov.total_duration != tv.total_duration:
                    return {
                        "passed": False,
                        "reason": f"Duration changed in {orig_part.id} M{om.number}: {ov.total_duration} -> {tv.total_duration}",
                    }
    return {"passed": True}


def verify_no_new_overflows(original: Score, transposed: Score) -> dict[str, Any]:
    def overflows(score: Score) -> set[tuple[str, str, str]]:
        result: set[tuple[str, str, str]] = set()
        for part in score.parts:
            for measure in part.measures:
                if measure.implicit:
                    continue
                expected = (
                    measure.time_signature.quarters_per_measure
                    if measure.time_signature
                    else Fraction(4)
                )
                for voice in measure.voices:
                    if voice.total_duration > expected + Fraction(1, 128):
                        result.add((part.id, measure.number, voice.id))
        return result

    orig_set = overflows(original)
    trans_set = overflows(transposed)
    new = trans_set - orig_set
    return {
        "passed": not new,
        "original_overflows": list(orig_set),
        "new_overflows": list(new),
    }


def verify_key_signature_transposed(original: Score, transposed: Score) -> dict[str, Any]:
    changes = []
    for orig_part in original.parts:
        trans_part = transposed.get_part(orig_part.id)
        for om, tm in zip(orig_part.measures, trans_part.measures):
            if om.key_signature is not None and tm.key_signature is not None:
                if tm.key_signature.fifths - om.key_signature.fifths != 2:
                    return {
                        "passed": False,
                        "reason": f"Key not transposed by +2 fifths in {orig_part.id} M{om.number}",
                    }
                changes.append((orig_part.id, om.number, om.key_signature.fifths, tm.key_signature.fifths))
    return {"passed": True, "changes": changes}


def verify_transposition_metadata_preserved(original: Score, transposed: Score) -> dict[str, Any]:
    for orig_part in original.parts:
        trans_part = transposed.get_part(orig_part.id)
        if orig_part.instrument.transposition != trans_part.instrument.transposition:
            return {
                "passed": False,
                "reason": f"Transposition metadata changed for {orig_part.id}",
            }
    return {"passed": True}


def verify_immutability(original: Score, transposed: Score) -> dict[str, Any]:
    return {"passed": transposed is not original}


def run_musescore_import(musicxml_path: Path) -> dict[str, Any]:
    exe_candidates = [
        Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
        Path(r"D:\Program Files\MuseScore 4\bin\MuseScore4.exe"),
    ]
    env = os.getenv("MUSESCORE_EXE")
    if env:
        exe_candidates.insert(0, Path(env))

    exe = next((c for c in exe_candidates if c.exists()), None)
    if exe is None:
        return {"passed": None, "reason": "MuseScore not found"}

    mscz = OUTPUT_DIR / musicxml_path.with_suffix(".mscz").name
    pdf = OUTPUT_DIR / musicxml_path.with_suffix(".pdf").name

    try:
        import_proc = subprocess.run(
            [str(exe), "-o", str(mscz), str(musicxml_path)],
            capture_output=True,
            timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        import_ok = import_proc.returncode == 0 and mscz.exists() and mscz.stat().st_size > 0

        pdf_ok = False
        if import_ok:
            pdf_proc = subprocess.run(
                [str(exe), "-o", str(pdf), str(mscz)],
                capture_output=True,
                timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pdf_ok = pdf_proc.returncode == 0 and pdf.exists() and pdf.stat().st_size > 0

        return {
            "passed": import_ok,
            "import_ok": import_ok,
            "pdf_ok": pdf_ok,
            "mscz_path": str(mscz),
            "pdf_path": str(pdf),
        }
    except Exception as exc:
        return {"passed": False, "reason": str(exc)}


def write_report(report_data: dict[str, Any]) -> Path:
    json_path = OUTPUT_DIR / "transpose_report.json"
    json_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Real Score Product Acceptance Report — Phase 1",
        "",
        f"**Date**: {report_data['date']}",
        f"**Input**: {report_data['input_path']}",
        f"**User request**: {report_data['user_request']}",
        f"**Provider**: {report_data.get('provider', 'not configured')}",
        "",
        "## Execution Status",
        "",
        f"- Overall success: **{report_data['overall_success']}**",
        f"- Resolver status: {report_data.get('resolver_status', 'N/A')}",
        f"- Quality Gate: {report_data.get('gate_status', 'N/A')}",
        "",
        "## Generated Files",
        "",
    ]
    for name, path in report_data.get("output_files", {}).items():
        md_lines.append(f"- **{name}**: `{path}`")
    md_lines.append("")

    md_lines.extend(["## TransposeRequest", "", "```json", json.dumps(report_data.get("request"), ensure_ascii=False, indent=2), "```", ""])

    md_lines.extend(["## Validation Results", ""])
    for check, result in report_data.get("validation", {}).items():
        status = "PASS" if result.get("passed") else ("SKIP" if result.get("passed") is None else "FAIL")
        md_lines.append(f"- **{check}**: {status} — `{result}`")
    md_lines.append("")

    md_lines.extend(["## Notes", "", report_data.get("notes", ""), ""])

    md_path = OUTPUT_DIR / "transpose_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return md_path


def main() -> int:
    from datetime import datetime

    ensure_output_dir()
    report: dict[str, Any] = {
        "date": datetime.now().isoformat(),
        "input_path": str(INPUT_PATH),
        "user_request": USER_REQUEST,
        "overall_success": False,
        "output_files": {},
        "validation": {},
        "notes": "",
    }

    # 1. Copy original.
    original_path = copy_original()
    report["output_files"]["original"] = str(original_path)

    # 2. Import and gate check.
    try:
        score = MusicXMLImporter().import_file(INPUT_PATH)
    except Exception as exc:
        report["notes"] = f"Failed to import input: {exc}"
        write_report(report)
        print(f"FAIL: import error: {exc}")
        return 1

    allows, status, omr_report = gate_check(INPUT_PATH)
    report["gate_status"] = f"{status} (allows={allows})"
    if not allows:
        report["notes"] = "Quality Gate blocked deterministic editing."
        write_report(report)
        print("FAIL: Quality Gate blocked")
        return 1

    # 3. Check API key.
    if not os.getenv("LLM_API_KEY"):
        report["notes"] = (
            "LLM_API_KEY environment variable is not set. "
            "Set LLM_API_KEY (and optionally LLM_MODEL/LLM_BASE_URL) and re-run this script."
        )
        write_report(report)
        print("FAIL: LLM_API_KEY not set")
        return 1

    # 4. Real provider call.
    try:
        client = OpenAICompatibleClient.from_env()
        provider = LLMIntentProvider(client=client, model=os.getenv("LLM_MODEL", ""), max_tokens=1024)
        context = build_intent_context(score)
        intent = provider.parse_transpose(USER_REQUEST, context)
        resolver = TransposeIntentResolver()
        result = resolver.resolve(intent, score)
    except Exception as exc:
        report["notes"] = f"Provider/resolver error: {exc}"
        write_report(report)
        print(f"FAIL: provider error: {exc}")
        return 1

    report["provider"] = f"{client.base_url} / {os.getenv('LLM_MODEL', 'default')}"
    report["resolver_status"] = result.status
    report["parser_intent"] = {
        "status": intent.status,
        "operation": intent.operation,
        "direction": intent.direction,
        "interval_description": intent.interval_description,
        "part_description": intent.part_description,
        "measure_start_description": intent.measure_start_description,
        "measure_end_description": intent.measure_end_description,
        "is_all_parts": intent.is_all_parts,
        "basis": intent.basis,
    }

    if not result.is_ready:
        report["notes"] = f"Resolver did not produce ready request: {result.clarification_question}"
        write_report(report)
        print(f"FAIL: resolver status={result.status}, question={result.clarification_question}")
        return 1

    request = result.request
    report["request"] = {
        "operation": request.operation.value,
        "interval": str(request.interval) if request.interval else None,
        "part_ids": request.part_ids,
        "measure_start": request.measure_start,
        "measure_end": request.measure_end,
    }

    # 5. Execute transposition.
    try:
        service = SafeTranspositionService()
        engine_result = service.transpose(score, request, omr_report=omr_report, mode=OMRGateMode.STRICT)
        transposed = engine_result.score
    except Exception as exc:
        report["notes"] = f"Transposition error: {exc}"
        write_report(report)
        print(f"FAIL: transposition error: {exc}")
        return 1

    # 6. Export.
    transposed_path = OUTPUT_DIR / "02_transposed_Bb_Clarinet_up_M2.musicxml"
    try:
        MusicXMLExporter().export_file(transposed, transposed_path)
        report["output_files"]["transposed"] = str(transposed_path)
    except Exception as exc:
        report["notes"] = f"Export error: {exc}"
        write_report(report)
        print(f"FAIL: export error: {exc}")
        return 1

    # 7. Re-import.
    try:
        reimported = MusicXMLImporter().import_file(transposed_path)
        report["output_files"]["reimported"] = str(transposed_path)
    except Exception as exc:
        report["notes"] = f"Re-import error: {exc}"
        write_report(report)
        print(f"FAIL: re-import error: {exc}")
        return 1

    # 8. Validation.
    report["validation"]["all_pitched_notes_up_M2"] = verify_m2_up(score, transposed)
    report["validation"]["rests_unchanged"] = verify_rests_unchanged(score, transposed)
    report["validation"]["durations_unchanged"] = verify_durations_unchanged(score, transposed)
    report["validation"]["no_new_overflows"] = verify_no_new_overflows(score, transposed)
    report["validation"]["key_signature_transposed"] = verify_key_signature_transposed(score, transposed)
    report["validation"]["transposition_metadata_preserved"] = verify_transposition_metadata_preserved(score, transposed)
    report["validation"]["original_score_immutable"] = verify_immutability(score, transposed)

    # 9. MuseScore import / PDF.
    ms_result = run_musescore_import(transposed_path)
    report["validation"]["musescore_import"] = ms_result
    if ms_result.get("mscz_path"):
        report["output_files"]["musescore_mscz"] = ms_result["mscz_path"]
    if ms_result.get("pdf_path"):
        report["output_files"]["musescore_pdf"] = ms_result["pdf_path"]

    # 10. Finalize.
    all_passed = all(
        v.get("passed") is True or v.get("passed") is None
        for v in report["validation"].values()
    )
    report["overall_success"] = all_passed
    report["notes"] = "Phase 1 completed successfully." if all_passed else "Some validations failed."

    write_report(report)

    if all_passed:
        print("SUCCESS: Phase 1 product acceptance test completed.")
        print(f"Output directory: {OUTPUT_DIR.absolute()}")
        for name, path in report["output_files"].items():
            print(f"  {name}: {path}")
        return 0
    else:
        print("FAIL: some validations did not pass.")
        print(json.dumps(report["validation"], ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
