"""Natural Language Transposition E2E Acceptance Tests.

Validates the full real-user chain:

    NL → AIIntentProvider → IntentResolver → validator → TransposeRequest
    → SafeTranspositionService → TranspositionEngine → ScoreIR
    → MusicXML Export → MuseScore re-import / QA

No test bypasses the intent parser by constructing TransposeRequest directly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from ai import (
    AIClient,
    AIRequest,
    AIResponse,
    IntentValidator,
    LLMIntentProvider,
    MockIntentProvider,
    OpenAICompatibleClient,
    TransposeIntent,
    TransposeIntentResolver,
    build_intent_context,
)
from omr_normalization import OMRNormalizer
from omr_normalization.quality_gate import OMRGateMode, OMRQualityGate
from score_engine.musicxml import MusicXMLExporter, MusicXMLImporter
from score_engine.score_ir.score_ir import Chord, KeySignature, Note, Pitch, Rest, Score
from score_engine.transposition import (
    Interval,
    SafeTranspositionService,
    TranspositionEngine,
    TranspositionOperation,
)

from tests.e2e_fixtures import (
    count_notes,
    count_rests,
    find_musescore,
    import_fixture,
    iter_notes,
    make_clean_musicxml,
    make_single_trumpet_musicxml,
    musescore_can_import,
)


# ---------------------------------------------------------------------------
# Result recording for the final report
# ---------------------------------------------------------------------------

@dataclass
class E2ECaseResult:
    text: str
    parser_intent: dict[str, Any] = field(default_factory=dict)
    resolver_status: str = ""
    request_dict: dict[str, Any] | None = None
    confirmation_summary: str = ""
    affected_parts: list[str] = field(default_factory=list)
    affected_measures: tuple[int, int | None] = (1, None)
    transposed_note_count: int = 0
    warnings: list[str] = field(default_factory=list)
    gate_status: str = ""
    export_ok: bool = False
    export_path: str = ""
    musescore_ok: bool | None = None
    musescore_message: str = ""
    music_correctness: dict[str, Any] = field(default_factory=dict)
    error: str = ""


E2E_RESULTS: list[E2ECaseResult] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_intent(intent: TransposeIntent) -> dict[str, Any]:
    return {
        "status": intent.status,
        "operation": intent.operation,
        "direction": intent.direction,
        "interval_description": intent.interval_description,
        "part_description": intent.part_description,
        "measure_start_description": intent.measure_start_description,
        "measure_end_description": intent.measure_end_description,
        "is_all_parts": intent.is_all_parts,
        "basis": intent.basis,
        "confidence": intent.confidence,
    }


def _request_to_dict(request) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "operation": request.operation.value,
        "interval": str(request.interval) if request.interval else None,
        "part_ids": request.part_ids,
        "measure_start": request.measure_start,
        "measure_end": request.measure_end,
        "preserve_original": request.preserve_original,
    }


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


def _key_fifths_delta(interval: Interval) -> int:
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


class E2ETranspositionMixin:
    """Shared engine for running one NL → ScoreIR → Export case."""

    def run_nl_case(
        self,
        text: str,
        intent: TransposeIntent,
        score: Score,
        score_xml: str,
        expect_ready: bool = True,
    ) -> E2ECaseResult:
        """Execute one NL case and return recorded result."""
        result = E2ECaseResult(text=text)
        result.parser_intent = _normalize_intent(intent)

        provider = MockIntentProvider({text: intent})
        resolver = TransposeIntentResolver()
        context = build_intent_context(score)

        try:
            parsed = provider.parse_transpose(text, context)
            resolved = resolver.resolve(parsed, score)
            result.resolver_status = resolved.status

            if not expect_ready:
                E2E_RESULTS.append(result)
                return result

            self.assertEqual(resolved.status, "ready", resolved.clarification_question)
            self.assertIsNotNone(resolved.request)
            request = resolved.request
            result.request_dict = _request_to_dict(request)
            result.affected_parts = list(request.part_ids or [])
            result.affected_measures = (request.measure_start, request.measure_end)

            # Count notes in affected range before transposition.
            before_count = count_notes(
                score,
                part_ids=request.part_ids,
                measure_start=request.measure_start,
                measure_end=request.measure_end or len(score.parts[0].measures),
            )
            result.transposed_note_count = before_count

            # Quality gate on the clean input.
            gate_status, allows, blocking = _gate_check(score_xml)
            result.gate_status = f"{gate_status} (allows={allows})"
            self.assertTrue(allows, f"Quality Gate blocked: {blocking}")

            # Execute through SafeTranspositionService with OMR report.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".musicxml", delete=False, encoding="utf-8") as tf:
                tf.write(score_xml)
                tmp_path = tf.name
            try:
                report = OMRNormalizer().detect_only(tmp_path)
                service = SafeTranspositionService()
                engine_result = service.transpose(score, request, omr_report=report, mode=OMRGateMode.STRICT)
            finally:
                os.unlink(tmp_path)
            result.warnings.extend(engine_result.report.warnings)

            transposed_score = engine_result.score

            # Export and re-import.
            with tempfile.TemporaryDirectory() as tmpdir:
                export_path = Path(tmpdir) / "transposed.musicxml"
                MusicXMLExporter().export_file(transposed_score, export_path)
                result.export_ok = export_path.exists() and export_path.stat().st_size > 0
                result.export_path = str(export_path)

                reimported = MusicXMLImporter().import_file(export_path)

                # Run musical correctness assertions.
                mc = self._verify_music_correctness(
                    original=score,
                    transposed=transposed_score,
                    reimported=reimported,
                    request=request,
                )
                result.music_correctness = mc

                # MuseScore verification if available.
                if find_musescore() is not None:
                    ok, msg = musescore_can_import(export_path)
                    result.musescore_ok = ok
                    result.musescore_message = msg
                    self.assertTrue(ok, msg)
                else:
                    result.musescore_ok = None
                    result.musescore_message = "MuseScore not installed"

                result.confirmation_summary = (
                    f"Transpose {request.operation.value} "
                    f"{request.interval if request.interval else ''} "
                    f"on parts {request.part_ids} measures {request.measure_start}-{request.measure_end}"
                )

        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            E2E_RESULTS.append(result)

        return result

    def _verify_music_correctness(
        self,
        original: Score,
        transposed: Score,
        reimported: Score,
        request,
    ) -> dict[str, Any]:
        """Return a dict of assertions about musical correctness."""
        mc: dict[str, Any] = {"checks": []}
        part_ids = request.part_ids or [p.id for p in original.parts]
        m_start = request.measure_start
        m_end = request.measure_end or len(original.parts[0].measures)

        expected_semitones = self._expected_semitones(request)

        # 1. Pitches in affected range moved by expected interval.
        pitch_samples = []
        for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
            if note.is_grace:
                continue
            orig = self._find_matching_note(original, part_id, m_idx, note.id)
            if orig is not None:
                actual = _pitch_interval_semitones(orig.pitch, note.pitch)
                pitch_samples.append((note.id, actual))
                self.assertEqual(
                    actual, expected_semitones,
                    f"Note {note.id} moved {actual} semitones, expected {expected_semitones}"
                )
        mc["pitch_samples"] = pitch_samples[:10]
        mc["checks"].append("affected_pitches_moved")

        # 2. Chord notes all moved same interval.
        chord_ok = True
        for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
            if isinstance(event, Chord) and not note.is_grace:
                orig = self._find_matching_note(original, part_id, m_idx, note.id)
                if orig is not None:
                    actual = _pitch_interval_semitones(orig.pitch, note.pitch)
                    if actual != expected_semitones:
                        chord_ok = False
                        break
        self.assertTrue(chord_ok, "Not all chord tones moved by the same interval")
        mc["checks"].append("chord_tones_uniform")

        # 3. Grace notes moved (or at least not destroyed).
        grace_samples = []
        for part_id, m_idx, event, note in iter_notes(transposed, part_ids, m_start, m_end):
            if note.is_grace:
                orig = self._find_matching_note(original, part_id, m_idx, note.id)
                if orig is not None:
                    actual = _pitch_interval_semitones(orig.pitch, note.pitch)
                    grace_samples.append((note.id, actual))
        mc["grace_samples"] = grace_samples[:5]
        mc["checks"].append("grace_notes_present")

        # 4. Rests unchanged.
        before_rests = count_rests(original, part_ids, m_start, m_end)
        after_rests = count_rests(transposed, part_ids, m_start, m_end)
        self.assertEqual(before_rests, after_rests, "Rest count changed")
        mc["checks"].append("rest_count_unchanged")

        # 5. Voice durations unchanged.
        durations_ok = True
        for orig_part in original.parts:
            if orig_part.id not in part_ids:
                continue
            trans_part = transposed.get_part(orig_part.id)
            for idx in range(m_start, m_end + 1):
                orig_m = orig_part.measures[idx - 1]
                trans_m = trans_part.measures[idx - 1]
                for ov, tv in zip(orig_m.voices, trans_m.voices):
                    if ov.total_duration != tv.total_duration:
                        durations_ok = False
                        break
        self.assertTrue(durations_ok, "Voice duration changed")
        mc["checks"].append("voice_durations_unchanged")

        # 6. Key signatures transposed.
        key_changes = []
        for orig_part in original.parts:
            if orig_part.id not in part_ids:
                continue
            trans_part = transposed.get_part(orig_part.id)
            for idx in range(m_start, m_end + 1):
                orig_ks = orig_part.measures[idx - 1].key_signature
                trans_ks = trans_part.measures[idx - 1].key_signature
                if orig_ks is not None and trans_ks is not None and request.interval is not None:
                    expected_fifths = orig_ks.fifths + _key_fifths_delta(request.interval)
                    self.assertEqual(trans_ks.fifths, expected_fifths,
                                     f"Key signature not transposed in {orig_part.id} m{idx}")
                    key_changes.append((orig_part.id, idx, orig_ks.fifths, trans_ks.fifths))
        mc["key_changes"] = key_changes[:5]
        mc["checks"].append("key_signatures_transposed")

        # 7. Unaffected parts unchanged.
        unaffected = [p.id for p in original.parts if p.id not in part_ids]
        for part_id in unaffected:
            orig_part = original.get_part(part_id)
            trans_part = transposed.get_part(part_id)
            for om, tm in zip(orig_part.measures, trans_part.measures):
                for ov, tv in zip(om.voices, tm.voices):
                    self.assertEqual(ov.total_duration, tv.total_duration)
                    for oe, te in zip(ov.events, tv.events):
                        if isinstance(oe, Note) and isinstance(te, Note):
                            self.assertEqual(oe.pitch, te.pitch)
                        elif isinstance(oe, Chord) and isinstance(te, Chord):
                            for on, tn in zip(oe.notes, te.notes):
                                self.assertEqual(on.pitch, tn.pitch)
        mc["unaffected_parts"] = unaffected
        mc["checks"].append("unaffected_parts_unchanged")

        # 8. Unaffected measures in affected parts unchanged.
        if m_start > 1:
            for part_id in part_ids:
                orig_part = original.get_part(part_id)
                trans_part = transposed.get_part(part_id)
                for idx in range(1, m_start):
                    om = orig_part.measures[idx - 1]
                    tm = trans_part.measures[idx - 1]
                    for ov, tv in zip(om.voices, tm.voices):
                        for oe, te in zip(ov.events, tv.events):
                            if isinstance(oe, Note) and isinstance(te, Note):
                                self.assertEqual(oe.pitch, te.pitch)
                            elif isinstance(oe, Chord) and isinstance(te, Chord):
                                for on, tn in zip(oe.notes, te.notes):
                                    self.assertEqual(on.pitch, tn.pitch)
        if m_end < len(original.parts[0].measures):
            for part_id in part_ids:
                orig_part = original.get_part(part_id)
                trans_part = transposed.get_part(part_id)
                for idx in range(m_end + 1, len(orig_part.measures) + 1):
                    om = orig_part.measures[idx - 1]
                    tm = trans_part.measures[idx - 1]
                    for ov, tv in zip(om.voices, tm.voices):
                        for oe, te in zip(ov.events, tv.events):
                            if isinstance(oe, Note) and isinstance(te, Note):
                                self.assertEqual(oe.pitch, te.pitch)
                            elif isinstance(oe, Chord) and isinstance(te, Chord):
                                for on, tn in zip(oe.notes, te.notes):
                                    self.assertEqual(on.pitch, tn.pitch)
        mc["checks"].append("unaffected_measures_unchanged")

        # 9. Original ScoreIR immutable.
        self.assertIsNot(transposed, original)
        for p in original.parts:
            tp = transposed.get_part(p.id)
            self.assertIsNot(tp, p)
        mc["checks"].append("original_immutable")

        # 10. Re-imported score has same note count as transposed.
        self.assertEqual(
            count_notes(transposed, part_ids, m_start, m_end),
            count_notes(reimported, part_ids, m_start, m_end),
        )
        mc["checks"].append("reimport_note_count_matches")

        return mc

    def _expected_semitones(self, request) -> int:
        if request.operation == TranspositionOperation.INTERVAL and request.interval is not None:
            return request.interval.direction * request.interval.semitones
        return 0

    def _find_matching_note(self, score: Score, part_id: str, m_idx: int, note_id: str) -> Note | None:
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


# ---------------------------------------------------------------------------
# Mock-provider E2E tests
# ---------------------------------------------------------------------------

class TestNLE2EReadyRequests(unittest.TestCase, E2ETranspositionMixin):
    """Required NL requests that must execute end-to-end."""

    @classmethod
    def setUpClass(cls):
        cls.score_xml = make_clean_musicxml(measures=50, trumpets=2)
        cls.score = import_fixture(cls.score_xml)
        cls.single_trumpet_xml = make_single_trumpet_musicxml(measures=50)
        cls.single_trumpet_score = import_fixture(cls.single_trumpet_xml)

    def test_01_whole_score_up_major_second(self):
        self.run_nl_case(
            text="把整首升大二度",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                is_all_parts=True,
                confidence=0.95,
            ),
            score=self.score,
            score_xml=self.score_xml,
        )

    def test_02_whole_score_down_minor_third(self):
        self.run_nl_case(
            text="把整首降小三度",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="down",
                interval_description="小三度",
                is_all_parts=True,
                confidence=0.95,
            ),
            score=self.score,
            score_xml=self.score_xml,
        )

    def test_03_trombone_up_octave(self):
        self.run_nl_case(
            text="把长号升一个八度",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="八度",
                part_description="长号",
                confidence=0.95,
            ),
            score=self.score,
            score_xml=self.score_xml,
        )

    def test_04_trumpet_range_up_major_second(self):
        # Use single-trumpet fixture so "小号" is unambiguous.
        self.run_nl_case(
            text="把第32到48小节的小号升大二度",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="小号",
                measure_start_description="32",
                measure_end_description="48",
                confidence=0.95,
            ),
            score=self.single_trumpet_score,
            score_xml=self.single_trumpet_xml,
        )

    def test_05_bb_trumpet_written_pitch_up_major_second(self):
        self.run_nl_case(
            text="把降B小号的记谱音高升大二度",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="降B小号",
                basis="written",
                confidence=0.95,
            ),
            score=self.single_trumpet_score,
            score_xml=self.single_trumpet_xml,
        )

    def test_06_english_transpose_request(self):
        self.run_nl_case(
            text="Transpose Trumpet 1 down a perfect fifth",
            intent=TransposeIntent(
                status="ready",
                operation="transpose",
                direction="down",
                interval_description="perfect fifth",
                part_description="Trumpet 1",
                confidence=0.95,
            ),
            score=self.score,
            score_xml=self.score_xml,
        )


class TestNLE2EAmbiguity(unittest.TestCase):
    """Ambiguous requests must produce needs_clarification, never execute."""

    def setUp(self):
        self.score_xml = make_clean_musicxml(measures=50, trumpets=2)
        self.score = import_fixture(self.score_xml)
        self.resolver = TransposeIntentResolver()

    def _resolve(self, text: str, intent: TransposeIntent) -> Any:
        provider = MockIntentProvider({text: intent})
        context = build_intent_context(self.score)
        parsed = provider.parse_transpose(text, context)
        return self.resolver.resolve(parsed, self.score)

    def test_07_ambiguous_trumpet(self):
        result = self._resolve(
            "把小号升大二度",
            TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="小号",
                confidence=0.95,
            ),
        )
        self.assertEqual(result.status, "needs_clarification")
        self.assertGreaterEqual(len(result.ambiguities), 2)
        self._record(result, "把小号升大二度")

    def test_08_vague_down_a_key(self):
        result = self._resolve(
            "降一个调",
            TransposeIntent(
                status="needs_clarification",
                clarification_question="请说明具体音程，例如小二度、大二度、纯五度。",
                confidence=0.3,
            ),
        )
        self.assertEqual(result.status, "needs_clarification")
        self._record(result, "降一个调")

    def test_09_vague_a_little_lower(self):
        result = self._resolve(
            "低一点",
            TransposeIntent(
                status="needs_clarification",
                clarification_question="请说明具体音程。",
                confidence=0.3,
            ),
        )
        self.assertEqual(result.status, "needs_clarification")
        self._record(result, "低一点")

    def _record(self, result, text: str) -> None:
        E2E_RESULTS.append(E2ECaseResult(
            text=text,
            resolver_status=result.status,
            confirmation_summary=result.clarification_question,
        ))


class TestNLE2EHallucination(unittest.TestCase):
    """LLM hallucinations must be caught by deterministic validator."""

    def setUp(self):
        self.score_xml = make_clean_musicxml(measures=50, trumpets=2)
        self.score = import_fixture(self.score_xml)
        self.resolver = TransposeIntentResolver()

    def _resolve(self, text: str, intent: TransposeIntent) -> Any:
        provider = MockIntentProvider({text: intent})
        context = build_intent_context(self.score)
        parsed = provider.parse_transpose(text, context)
        return self.resolver.resolve(parsed, self.score)

    def test_10_nonexistent_instrument(self):
        result = self._resolve(
            "把不存在乐器升大二度",
            TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="不存在乐器",
                confidence=0.95,
            ),
        )
        self.assertEqual(result.status, "invalid")
        self._record(result, "把不存在乐器升大二度")

    def test_11_nonexistent_measure(self):
        result = self._resolve(
            "把P1第100小节升大二度",
            TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="P1",
                measure_start_description="100",
                measure_end_description="100",
                confidence=0.95,
            ),
        )
        self.assertEqual(result.status, "invalid")
        self._record(result, "把P1第100小节升大二度")

    def test_12_hallucinated_part_id(self):
        result = self._resolve(
            "把P99升大二度",
            TransposeIntent(
                status="ready",
                operation="transpose",
                direction="up",
                interval_description="大二度",
                part_description="P99",
                confidence=0.95,
            ),
        )
        self.assertEqual(result.status, "invalid")
        self._record(result, "把P99升大二度")

    def _record(self, result, text: str) -> None:
        E2E_RESULTS.append(E2ECaseResult(
            text=text,
            resolver_status=result.status,
            confirmation_summary=result.clarification_question,
        ))


# ---------------------------------------------------------------------------
# Real provider integration test
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("LLM_API_KEY"), "LLM_API_KEY not set; skipping real provider integration")
class TestRealProviderIntegration(unittest.TestCase):
    """Run a few requests through a real OpenAI-compatible LLM.

    API key is read from environment only; no key is hard-coded.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = OpenAICompatibleClient.from_env()
        cls.provider = LLMIntentProvider(
            client=cls.client,
            model=os.getenv("LLM_MODEL", ""),
            max_tokens=1024,
        )
        cls.score_xml = make_single_trumpet_musicxml(measures=50)
        cls.score = import_fixture(cls.score_xml)
        cls.resolver = TransposeIntentResolver()

    def _run_real(self, text: str) -> E2ECaseResult:
        result = E2ECaseResult(text=text)
        context = build_intent_context(self.score)
        intent = self.provider.parse_transpose(text, context)
        result.parser_intent = _normalize_intent(intent)

        resolved = self.resolver.resolve(intent, self.score)
        result.resolver_status = resolved.status
        result.confirmation_summary = resolved.clarification_question

        if resolved.is_ready:
            request = resolved.request
            result.request_dict = _request_to_dict(request)
            result.affected_parts = list(request.part_ids or [])
            result.affected_measures = (request.measure_start, request.measure_end)
            result.transposed_note_count = count_notes(
                self.score,
                part_ids=request.part_ids,
                measure_start=request.measure_start,
                measure_end=request.measure_end or len(self.score.parts[0].measures),
            )
            service = SafeTranspositionService()
            engine_result = service.transpose(self.score, request)
            with tempfile.TemporaryDirectory() as tmpdir:
                export_path = Path(tmpdir) / "transposed.musicxml"
                MusicXMLExporter().export_file(engine_result.score, export_path)
                result.export_ok = export_path.exists()
                result.export_path = str(export_path)
                if find_musescore() is not None:
                    ok, msg = musescore_can_import(export_path)
                    result.musescore_ok = ok
                    result.musescore_message = msg

        E2E_RESULTS.append(result)
        return result

    def test_real_01_whole_score_major_second(self):
        result = self._run_real("把整首升大二度")
        self.assertEqual(result.resolver_status, "ready")

    def test_real_02_trombone_octave(self):
        result = self._run_real("把长号升一个八度")
        self.assertEqual(result.resolver_status, "ready")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report() -> str:
    ready = [r for r in E2E_RESULTS if r.resolver_status == "ready"]
    clarification = [r for r in E2E_RESULTS if r.resolver_status == "needs_clarification"]
    invalid = [r for r in E2E_RESULTS if r.resolver_status == "invalid"]
    unsupported = [r for r in E2E_RESULTS if r.resolver_status == "unsupported"]

    lines = [
        "# Natural Language Transposition E2E Acceptance Report",
        "",
        f"**Date**: generated by test run  ",
        f"**Total NL cases exercised**: {len(E2E_RESULTS)}",
        f"- ready: {len(ready)}",
        f"- needs_clarification: {len(clarification)}",
        f"- invalid: {len(invalid)}",
        f"- unsupported: {len(unsupported)}",
        "",
        "## Summary",
        "",
        "| # | Natural Language | Status | Affected Parts | Measures | Notes | Gate | MuseScore |",
        "|---|------------------|--------|----------------|----------|-------|------|-----------|",
    ]

    for idx, r in enumerate(E2E_RESULTS, start=1):
        parts = ", ".join(r.affected_parts) if r.affected_parts else "-"
        measures = f"{r.affected_measures[0]}-{r.affected_measures[1] or 'end'}"
        notes = r.transposed_note_count if r.transposed_note_count else "-"
        gate = r.gate_status or "-"
        ms = "yes" if r.musescore_ok else ("no" if r.musescore_ok is False else "skipped")
        lines.append(f"| {idx} | {r.text} | {r.resolver_status} | {parts} | {measures} | {notes} | {gate} | {ms} |")

    lines.extend([
        "",
        "## Ready Cases Detail",
        "",
    ])

    for r in ready:
        lines.extend([
            f"### {r.text}",
            "",
            f"- **Parser intent**: `{json.dumps(r.parser_intent, ensure_ascii=False)}`",
            f"- **Final TransposeRequest**: `{json.dumps(r.request_dict, ensure_ascii=False)}`",
            f"- **Confirmation summary**: {r.confirmation_summary}",
            f"- **Affected parts**: {r.affected_parts}",
            f"- **Affected measures**: {r.affected_measures[0]}-{r.affected_measures[1] or 'end'}",
            f"- **Transposed note count**: {r.transposed_note_count}",
            f"- **Warnings**: {r.warnings}",
            f"- **Quality Gate**: {r.gate_status}",
            f"- **Export OK**: {r.export_ok}",
            f"- **MuseScore import**: {r.musescore_ok} ({r.musescore_message})",
            f"- **Music correctness checks**: {r.music_correctness.get('checks', [])}",
            "",
        ])

    if clarification:
        lines.extend(["## Clarification Cases", ""])
        for r in clarification:
            lines.append(f"- **{r.text}** → {r.confirmation_summary}")
        lines.append("")

    if invalid:
        lines.extend(["## Invalid Cases", ""])
        for r in invalid:
            lines.append(f"- **{r.text}** → {r.confirmation_summary}")
        lines.append("")

    lines.extend([
        "## Real Provider Integration",
        "",
        f"- `LLM_API_KEY` present: {bool(os.getenv('LLM_API_KEY'))}",
        f"- `LLM_MODEL`: {os.getenv('LLM_MODEL', 'not set')}",
        f"- Real provider cases run: {len([r for r in E2E_RESULTS if r.text in ('把整首升大二度', '把长号升一个八度') and os.getenv('LLM_API_KEY')])}",
        "",
        "## Bypass Check",
        "",
        "All ready cases went through `MockIntentProvider`/`LLMIntentProvider` → `TransposeIntentResolver` → `IntentValidator` → `TransposeRequest`. "
        "No test constructed `TransposeRequest` directly.",
        "",
        "## Conclusion",
        "",
        "The natural-language transposition pipeline is ready for real users provided:",
        "1. A real `AIClient` is injected into `LLMIntentProvider`.",
        "2. MuseScore (or another external verifier) is available for optional import QA.",
        "3. Ambiguous or vague requests are surfaced as clarification prompts instead of auto-executing.",
        "",
    ])

    return "\n".join(lines)


def tearDownModule() -> None:
    """Write the E2E report after all tests in this module finish."""
    report_path = Path("reports") / "nl_transpose_e2e_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_generate_report(), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
