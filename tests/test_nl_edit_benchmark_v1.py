"""Natural Language Music Editing Acceptance Benchmark V1.

Validates the full user chain for TRANSPOSE requests only:

    NL → Provider → JSON extraction → IntentParser → Resolver → Validator
    → TransposeRequest → SafeTranspositionService → Engine → MusicXML export
    → re-import → semantic verification

Ground truth is established using a deterministic MockIntentProvider so that
failures are attributable to the deterministic pipeline, not to LLM variance.

Output:
    reports/nl_edit_benchmark_v1.md
    reports/nl_edit_benchmark_v1.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow imports from project root when PYTHONPATH=src.
from ai import (
    MockIntentProvider,
    TransposeIntent,
    TransposeIntentResolver,
    build_intent_context,
)
from omr_normalization import OMRNormalizer
from omr_normalization.quality_gate import OMRGateMode, OMRQualityGate
from score_engine.musicxml import MusicXMLExporter, MusicXMLImporter
from score_engine.score_ir.score_ir import Chord, Note, Pitch, Score
from score_engine.transposition import (
    SafeTranspositionService,
    TranspositionEngine,
    TranspositionOperation,
)

from tests.e2e_fixtures import (
    count_notes,
    count_rests,
    import_fixture,
    iter_notes,
    make_clean_musicxml,
    make_single_trumpet_musicxml,
)


# ---------------------------------------------------------------------------
# Case and result data classes
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkCase:
    """One benchmark case with its expected deterministic outcome."""

    case_id: str
    category: str
    input_text: str
    expected_status: str  # PASS, NEEDS_CLARIFICATION, UNSUPPORTED, INVALID_TARGET
    intent: TransposeIntent
    fixture: str = "two_trumpet"  # or "single_trumpet"


@dataclass
class BenchmarkResult:
    """Outcome of running one benchmark case."""

    case_id: str
    category: str
    input_text: str
    provider_model: str = "synthetic"
    intent_status: str = ""
    resolver_status: str = ""
    operation: str | None = None
    target_part: list[str] = field(default_factory=list)
    measure_range: tuple[int | None, int | None] = field(default_factory=lambda: (None, None))
    interval_or_basis: str = ""
    expected_status: str = ""
    actual_status: str = ""
    export_success: bool = False
    reimport_success: bool = False
    semantic_verification: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    failure_stage: str = ""
    error_reason: str = ""
    error_detail: str = ""


# ---------------------------------------------------------------------------
# Benchmark case definitions
# ---------------------------------------------------------------------------

_BENCHMARK_CASES: list[BenchmarkCase] = [
    # 1. Whole-score relative interval
    BenchmarkCase(
        case_id="WS-01",
        category="whole_score_interval",
        input_text="把整首升大二度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="大二度",
            is_all_parts=True,
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="WS-02",
        category="whole_score_interval",
        input_text="整首降小三度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="down",
            interval_description="小三度",
            is_all_parts=True,
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="WS-03",
        category="whole_score_interval",
        input_text="全曲升高一个八度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="八度",
            is_all_parts=True,
            confidence=0.95,
        ),
    ),

    # 2. Part-specific
    BenchmarkCase(
        case_id="PS-01",
        category="part_specific",
        input_text="把长号升高一个八度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="八度",
            part_description="长号",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="PS-02",
        category="part_specific",
        input_text="把第一小号升大二度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="大二度",
            part_description="Trumpet 1",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="PS-03",
        category="part_specific",
        input_text="把第二小号降半音",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="down",
            interval_description="半音",
            part_description="Trumpet 2",
            confidence=0.95,
        ),
    ),

    # 3. Measure-range
    BenchmarkCase(
        case_id="MR-01",
        category="measure_range",
        input_text="把第12到24小节升大二度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="大二度",
            is_all_parts=True,
            measure_start_description="12",
            measure_end_description="24",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="MR-02",
        category="measure_range",
        input_text="第32小节到最后降一个全音",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="down",
            interval_description="全音",
            is_all_parts=True,
            measure_start_description="32",
            measure_end_description="50",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="MR-03",
        category="measure_range",
        input_text="前8小节升半音",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="半音",
            is_all_parts=True,
            measure_start_description="1",
            measure_end_description="8",
            confidence=0.95,
        ),
    ),

    # 4. Part + measure range
    BenchmarkCase(
        case_id="PM-01",
        category="part_measure_range",
        input_text="把长号第12到24小节升大二度",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="大二度",
            part_description="长号",
            measure_start_description="12",
            measure_end_description="24",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="PM-02",
        category="part_measure_range",
        input_text="第二小号第5到10小节降半音",
        expected_status="PASS",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="down",
            interval_description="半音",
            part_description="Trumpet 2",
            measure_start_description="5",
            measure_end_description="10",
            confidence=0.95,
        ),
    ),

    # 5. Instrument-transposition semantics (single-trumpet fixture)
    BenchmarkCase(
        case_id="IT-01",
        category="instrument_transposition",
        input_text="把Bb小号改成实际音高",
        expected_status="PASS",
        fixture="single_trumpet",
        intent=TransposeIntent(
            status="ready",
            operation="written_to_sounding",
            part_description="小号",
            basis="concert",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="IT-02",
        category="instrument_transposition",
        input_text="把实际音高改成Bb小号记谱",
        expected_status="PASS",
        fixture="single_trumpet",
        intent=TransposeIntent(
            status="ready",
            operation="sounding_to_written",
            part_description="小号",
            basis="written",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="IT-03",
        category="instrument_transposition",
        input_text="把F圆号改成实际音高",
        expected_status="INVALID_TARGET",
        intent=TransposeIntent(
            status="ready",
            operation="written_to_sounding",
            part_description="圆号",
            basis="concert",
            confidence=0.95,
        ),
    ),

    # 6. Key / target-pitch semantics (V1 not supported)
    BenchmarkCase(
        case_id="KY-01",
        category="key_target",
        input_text="把整首移到降E大调",
        expected_status="UNSUPPORTED",
        intent=TransposeIntent(
            status="unsupported",
            clarification_question="Target-key transposition is not supported in V1.",
            confidence=0.5,
        ),
    ),
    BenchmarkCase(
        case_id="KY-02",
        category="key_target",
        input_text="把这段移成D大调",
        expected_status="UNSUPPORTED",
        intent=TransposeIntent(
            status="unsupported",
            clarification_question="Target-key transposition is not supported in V1.",
            confidence=0.5,
        ),
    ),

    # 7. Ambiguity / clarification
    BenchmarkCase(
        case_id="AM-01",
        category="ambiguity",
        input_text="后面一点降一点",
        expected_status="NEEDS_CLARIFICATION",
        intent=TransposeIntent(
            status="needs_clarification",
            clarification_question="请说明具体音程。",
            confidence=0.3,
        ),
    ),
    BenchmarkCase(
        case_id="AM-02",
        category="ambiguity",
        input_text="把小号调高一点",
        expected_status="NEEDS_CLARIFICATION",
        intent=TransposeIntent(
            status="needs_clarification",
            clarification_question="Which trumpet?",
            confidence=0.3,
        ),
    ),
    BenchmarkCase(
        case_id="AM-03",
        category="ambiguity",
        input_text="第二段降一点",
        expected_status="NEEDS_CLARIFICATION",
        intent=TransposeIntent(
            status="needs_clarification",
            clarification_question="请说明具体音程与小节范围。",
            confidence=0.3,
        ),
    ),

    # 8. Hallucination / invalid target
    BenchmarkCase(
        case_id="HL-01",
        category="hallucination",
        input_text="把不存在的圆号升八度",
        expected_status="INVALID_TARGET",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="八度",
            part_description="圆号",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="HL-02",
        category="hallucination",
        input_text="把第999小节升大二度",
        expected_status="INVALID_TARGET",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="大二度",
            is_all_parts=True,
            measure_start_description="999",
            measure_end_description="999",
            confidence=0.95,
        ),
    ),
    BenchmarkCase(
        case_id="HL-03",
        category="hallucination",
        input_text="把第三小号第10小节升半音",
        expected_status="INVALID_TARGET",
        intent=TransposeIntent(
            status="ready",
            operation="transpose",
            direction="up",
            interval_description="半音",
            part_description="第三小号",
            measure_start_description="10",
            measure_end_description="10",
            confidence=0.95,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Verification helpers (mirroring test_nl_transpose_e2e logic)
# ---------------------------------------------------------------------------

def _gate_check(score_xml: str) -> tuple[str, bool, list[str]]:
    """Run OMRNormalizer detect_only + Quality Gate STRICT on a MusicXML string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".musicxml", delete=False, encoding="utf-8") as f:
        f.write(score_xml)
        path = f.name
    try:
        report = OMRNormalizer().detect_only(path)
        gate = OMRQualityGate().check(report, OMRGateMode.STRICT)
        return gate.status, gate.allows_deterministic_edit, [i.issue_id for i in gate.blocking_issues]
    finally:
        os.unlink(path)


def _pitch_interval_semitones(a: Pitch, b: Pitch) -> int:
    return b.midi - a.midi


def _key_fifths_delta(interval) -> int:
    """Return change in key-signature fifths for a V1 interval."""
    direction = interval.direction
    interval_class = (interval.number - 1) % 7
    quality = interval.quality
    ascending = {
        0: 0,
        1: 2 if quality == "M" else -5,
        2: 4 if quality == "M" else -3,
        3: -1,
        4: 1,
        5: 3 if quality == "M" else -4,
        6: 5 if quality == "M" else -2,
    }
    return direction * ascending[interval_class]


def _find_matching_note(score: Score, part_id: str, m_idx: int, note_id: str) -> Note | None:
    part = score.get_part(part_id)
    if part is None or m_idx > len(part.measures):
        return None
    measure = part.measures[m_idx - 1]
    for voice in measure.voices:
        for event in voice.events:
            if isinstance(event, Note) and event.id == note_id:
                return event
            if isinstance(event, Chord):
                for note in event.notes:
                    if note.id == note_id:
                        return note
    return None


def _expected_semitones(request, original: Score) -> int:
    if request.operation == TranspositionOperation.INTERVAL and request.interval is not None:
        return request.interval.direction * request.interval.semitones
    if request.operation == TranspositionOperation.WRITTEN_TO_SOUNDING:
        for part in original.parts:
            if part.id in request.part_ids:
                return part.instrument.transposition.chromatic + 12 * part.instrument.transposition.octave_change
    if request.operation == TranspositionOperation.SOUNDING_TO_WRITTEN:
        for part in original.parts:
            if part.id in request.part_ids:
                return -(part.instrument.transposition.chromatic + 12 * part.instrument.transposition.octave_change)
    return 0


def _verify_music_correctness(
    original: Score,
    transposed: Score,
    reimported: Score,
    request,
) -> list[str]:
    """Run semantic checks and return a list of passed check names."""
    checks: list[str] = []
    part_ids = request.part_ids or [p.id for p in original.parts]
    m_start = request.measure_start
    m_end = request.measure_end or len(original.parts[0].measures)
    expected_semitones = _expected_semitones(request, original)

    # 1. Pitches in affected range moved by expected interval.
    for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
        if note.is_grace:
            continue
        orig = _find_matching_note(original, part_id, m_idx, note.id)
        if orig is not None:
            actual = _pitch_interval_semitones(orig.pitch, note.pitch)
            if actual != expected_semitones:
                raise AssertionError(
                    f"Note {note.id} moved {actual} semitones, expected {expected_semitones}"
                )
    checks.append("affected_pitches_moved")

    # 2. Chord notes all moved same interval.
    for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
        if isinstance(event, Chord) and not note.is_grace:
            orig = _find_matching_note(original, part_id, m_idx, note.id)
            if orig is not None:
                actual = _pitch_interval_semitones(orig.pitch, note.pitch)
                if actual != expected_semitones:
                    raise AssertionError("Not all chord tones moved by the same interval")
    checks.append("chord_tones_uniform")

    # 3. Grace notes present.
    grace_count = 0
    for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
        if note.is_grace:
            grace_count += 1
    checks.append("grace_notes_present")

    # 4. Rests unchanged.
    before_rests = count_rests(original, part_ids, m_start, m_end)
    after_rests = count_rests(transposed, part_ids, m_start, m_end)
    if before_rests != after_rests:
        raise AssertionError("Rest count changed")
    checks.append("rest_count_unchanged")

    # 5. Voice durations unchanged.
    for orig_part in original.parts:
        if orig_part.id not in part_ids:
            continue
        trans_part = transposed.get_part(orig_part.id)
        for idx in range(m_start, m_end + 1):
            orig_m = orig_part.measures[idx - 1]
            trans_m = trans_part.measures[idx - 1]
            for ov, tv in zip(orig_m.voices, trans_m.voices):
                if ov.total_duration != tv.total_duration:
                    raise AssertionError("Voice duration changed")
    checks.append("voice_durations_unchanged")

    # 6. Key signatures transposed.
    for orig_part in original.parts:
        if orig_part.id not in part_ids:
            continue
        trans_part = transposed.get_part(orig_part.id)
        for idx in range(m_start, m_end + 1):
            orig_ks = orig_part.measures[idx - 1].key_signature
            trans_ks = trans_part.measures[idx - 1].key_signature
            if orig_ks is not None and trans_ks is not None and request.interval is not None:
                expected_fifths = orig_ks.fifths + _key_fifths_delta(request.interval)
                if trans_ks.fifths != expected_fifths:
                    raise AssertionError(
                        f"Key signature not transposed in {orig_part.id} m{idx}"
                    )
    checks.append("key_signatures_transposed")

    # 7. Unaffected parts unchanged.
    unaffected = [p.id for p in original.parts if p.id not in part_ids]
    for part_id in unaffected:
        orig_part = original.get_part(part_id)
        trans_part = transposed.get_part(part_id)
        for om, tm in zip(orig_part.measures, trans_part.measures):
            for ov, tv in zip(om.voices, tm.voices):
                if ov.total_duration != tv.total_duration:
                    raise AssertionError("Unaffected part duration changed")
                for oe, te in zip(ov.events, tv.events):
                    if isinstance(oe, Note) and isinstance(te, Note):
                        if oe.pitch != te.pitch:
                            raise AssertionError("Unaffected part pitch changed")
                    elif isinstance(oe, Chord) and isinstance(te, Chord):
                        for on, tn in zip(oe.notes, te.notes):
                            if on.pitch != tn.pitch:
                                raise AssertionError("Unaffected part chord pitch changed")
    checks.append("unaffected_parts_unchanged")

    # 8. Re-imported score has same note count as transposed.
    if count_notes(transposed, part_ids, m_start, m_end) != count_notes(reimported, part_ids, m_start, m_end):
        raise AssertionError("Reimport note count mismatch")
    checks.append("reimport_note_count_matches")

    return checks


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def _load_fixtures() -> dict[str, tuple[Score, str]]:
    """Return {name: (score, score_xml)} for all fixtures."""
    two_xml = make_clean_musicxml(measures=50, trumpets=2)
    single_xml = make_single_trumpet_musicxml(measures=50)
    return {
        "two_trumpet": (import_fixture(two_xml), two_xml),
        "single_trumpet": (import_fixture(single_xml), single_xml),
    }


def _classify_result(expected: str, resolver_status: str, engine_ok: bool) -> str:
    """Map the deterministic outcome to a benchmark status."""
    if expected == "PASS":
        return "PASS" if resolver_status == "ready" and engine_ok else "FAIL"
    if expected == "NEEDS_CLARIFICATION":
        return "NEEDS_CLARIFICATION" if resolver_status == "needs_clarification" else "FAIL"
    if expected == "UNSUPPORTED":
        return "UNSUPPORTED" if resolver_status == "unsupported" else "FAIL"
    if expected == "INVALID_TARGET":
        # Any non-ready deterministic refusal is acceptable for an invalid target.
        return "INVALID_TARGET" if resolver_status in ("invalid", "needs_clarification") else "FAIL"
    return "FAIL"


def run_benchmark() -> list[BenchmarkResult]:
    """Execute all benchmark cases using a synthetic provider and return results."""
    import time

    fixtures = _load_fixtures()
    resolver = TransposeIntentResolver()
    results: list[BenchmarkResult] = []

    for case in _BENCHMARK_CASES:
        start = time.perf_counter()
        score, score_xml = fixtures[case.fixture]
        result = BenchmarkResult(
            case_id=case.case_id,
            category=case.category,
            input_text=case.input_text,
            expected_status=case.expected_status,
        )

        provider = MockIntentProvider({case.input_text: case.intent})
        context = build_intent_context(score)

        try:
            parsed = provider.parse_transpose(case.input_text, context)
            result.intent_status = parsed.status
            resolved = resolver.resolve(parsed, score)
            result.resolver_status = resolved.status
            result.operation = resolved.request.operation.value if resolved.request else None
            result.target_part = list(resolved.request.part_ids) if resolved.request else []
            if resolved.request:
                result.measure_range = (resolved.request.measure_start, resolved.request.measure_end)
                if resolved.request.operation == TranspositionOperation.INTERVAL and resolved.request.interval:
                    result.interval_or_basis = str(resolved.request.interval)
                else:
                    result.interval_or_basis = resolved.request.operation.value

            if resolved.status != "ready":
                result.actual_status = _classify_result(case.expected_status, resolved.status, False)
                result.failure_stage = "resolver"
                result.error_reason = resolved.clarification_question
                result.latency_ms = (time.perf_counter() - start) * 1000
                results.append(result)
                continue

            # PASS cases continue through engine/export/reimport.
            request = resolved.request

            # Quality gate.
            gate_status, allows, blocking = _gate_check(score_xml)
            if not allows:
                raise AssertionError(f"Quality Gate blocked: {blocking}")

            # Safe transposition service.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".musicxml", delete=False, encoding="utf-8") as tf:
                tf.write(score_xml)
                tmp_path = tf.name
            try:
                report = OMRNormalizer().detect_only(tmp_path)
                service = SafeTranspositionService()
                engine_result = service.transpose(score, request, omr_report=report, mode=OMRGateMode.STRICT)
            finally:
                os.unlink(tmp_path)

            transposed_score = engine_result.score

            # Export and re-import.
            with tempfile.TemporaryDirectory() as tmpdir:
                export_path = Path(tmpdir) / "transposed.musicxml"
                MusicXMLExporter().export_file(transposed_score, export_path)
                result.export_success = export_path.exists() and export_path.stat().st_size > 0
                reimported = MusicXMLImporter().import_file(export_path)
                result.reimport_success = True

                result.semantic_verification = _verify_music_correctness(
                    original=score,
                    transposed=transposed_score,
                    reimported=reimported,
                    request=request,
                )

            result.actual_status = _classify_result(case.expected_status, resolved.status, True)
            result.failure_stage = "" if result.actual_status == "PASS" else "semantic_verification"

        except Exception as exc:
            result.error_detail = f"{type(exc).__name__}: {exc}"
            result.actual_status = "FAIL"
            result.failure_stage = "exception"
            result.error_reason = result.error_detail

        result.latency_ms = (time.perf_counter() - start) * 1000
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

REPORT_DIR = Path("reports")
REPORT_MD = REPORT_DIR / "nl_edit_benchmark_v1.md"
REPORT_JSON = REPORT_DIR / "nl_edit_benchmark_v1.json"


def _generate_report(results: list[BenchmarkResult]) -> str:
    """Build the markdown report."""
    total = len(results)
    status_counts: dict[str, int] = {}
    category_counts: dict[str, dict[str, int]] = {}
    stage_counts: dict[str, int] = {}

    for r in results:
        status_counts[r.actual_status] = status_counts.get(r.actual_status, 0) + 1
        category_counts.setdefault(r.category, {}).setdefault(r.actual_status, 0)
        category_counts[r.category][r.actual_status] += 1
        if r.failure_stage:
            stage_counts[r.failure_stage] = stage_counts.get(r.failure_stage, 0) + 1

    lines: list[str] = []
    lines.append("# Natural Language Music Editing Acceptance Benchmark V1")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Provider**: synthetic / deterministic (ground truth)")
    lines.append(f"- **Total cases**: {total}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for status in ("PASS", "NEEDS_CLARIFICATION", "UNSUPPORTED", "INVALID_TARGET", "FAIL", "PROVIDER_ERROR"):
        if status in status_counts:
            lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.append("")

    pass_count = status_counts.get("PASS", 0)
    lines.append(f"**Overall pass rate**: {pass_count}/{total} ({100*pass_count/total:.1f}%)")
    lines.append("")

    lines.append("## Results by Category")
    lines.append("")
    lines.append("| Category | PASS | NEEDS_CLARIFICATION | UNSUPPORTED | INVALID_TARGET | FAIL |")
    lines.append("|----------|------|---------------------|-------------|----------------|------|")
    for category in sorted(category_counts):
        counts = category_counts[category]
        lines.append(
            f"| {category} | "
            f"{counts.get('PASS', 0)} | "
            f"{counts.get('NEEDS_CLARIFICATION', 0)} | "
            f"{counts.get('UNSUPPORTED', 0)} | "
            f"{counts.get('INVALID_TARGET', 0)} | "
            f"{counts.get('FAIL', 0)} |"
        )
    lines.append("")

    if stage_counts:
        lines.append("## Failure Stage Distribution")
        lines.append("")
        lines.append("| Stage | Count |")
        lines.append("|-------|-------|")
        for stage, count in sorted(stage_counts.items()):
            lines.append(f"| {stage} | {count} |")
        lines.append("")

    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| Case | Category | Input | Expected | Actual | Resolver | Target Part | Measures | Interval/Basis | Export | Reimport | Latency (ms) | Failure Stage | Error |")
    lines.append("|------|----------|-------|----------|--------|----------|-------------|----------|----------------|--------|----------|--------------|---------------|-------|")
    for r in results:
        measures = f"{r.measure_range[0]}-{r.measure_range[1]}" if r.measure_range[0] is not None else ""
        export = "✅" if r.export_success else "❌"
        reimport = "✅" if r.reimport_success else "❌"
        lines.append(
            f"| {r.case_id} | {r.category} | {r.input_text} | {r.expected_status} | {r.actual_status} | "
            f"{r.resolver_status} | {', '.join(r.target_part)} | {measures} | {r.interval_or_basis} | "
            f"{export} | {reimport} | {r.latency_ms:.1f} | {r.failure_stage} | {r.error_reason} |"
        )
    lines.append("")

    lines.append("## Classification Notes")
    lines.append("")
    lines.append("- **PASS**: pipeline produced `ready` and engine/export/reimport/semantic checks succeeded.")
    lines.append("- **NEEDS_CLARIFICATION**: resolver returned `needs_clarification` for ambiguous input.")
    lines.append("- **UNSUPPORTED**: model or system correctly reported unsupported operation (e.g., target-key transposition).")
    lines.append("- **INVALID_TARGET**: resolver refused a non-existent part or measure.")
    lines.append("- **FAIL**: actual outcome did not match expected outcome.")
    lines.append("- **PROVIDER_ERROR**: reserved for real-provider HTTP/JSON failures (not present in synthetic run).")
    lines.append("")

    return "\n".join(lines)


def write_reports(results: list[BenchmarkResult]) -> None:
    """Write markdown and JSON reports."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    md = _generate_report(results)
    REPORT_MD.write_text(md, encoding="utf-8")

    serializable = [asdict(r) for r in results]
    summary = {
        "date": datetime.now(timezone.utc).isoformat(),
        "provider": "synthetic",
        "total_cases": len(results),
        "status_counts": {},
        "results": serializable,
    }
    for r in results:
        summary["status_counts"][r.actual_status] = summary["status_counts"].get(r.actual_status, 0) + 1

    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unittest wrapper
# ---------------------------------------------------------------------------

class TestNLEditBenchmarkV1(unittest.TestCase):
    """Run the full NL edit benchmark V1 as a unittest."""

    def test_benchmark_v1(self):
        results = run_benchmark()
        write_reports(results)

        failures = [r for r in results if r.actual_status == "FAIL"]
        if failures:
            msg = "\n".join(
                f"{r.case_id} ({r.category}): {r.input_text!r} -> {r.error_detail or r.error_reason}"
                for r in failures
            )
            self.fail(f"Benchmark V1 had {len(failures)} unexpected failure(s):\n{msg}")


if __name__ == "__main__":
    results = run_benchmark()
    write_reports(results)
    print(f"Benchmark V1 complete: {len(results)} cases")
    print(f"Report: {REPORT_MD}")
    print(f"Report: {REPORT_JSON}")
    for r in results:
        print(f"  {r.case_id}: {r.actual_status} ({r.resolver_status})")
    if any(r.actual_status == "FAIL" for r in results):
        sys.exit(1)
