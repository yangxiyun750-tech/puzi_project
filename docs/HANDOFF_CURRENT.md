# Project Handoff — Current State

**Project**: `D:\puzi_project`  
**Date**: 2026-08-17  
**Status**: Development paused. Diagnostics infrastructure ready; next implementation step not yet executed.

---

## 1. Project Architecture and Completed Modules

The project is a deterministic music-score transposition pipeline with an optional natural-language (NL) front end backed by an OpenAI-compatible LLM.

```
D:\puzi_project
├── src/
│   ├── ai/                          # NL intent parsing + provider diagnostics
│   │   ├── __init__.py              # AIClient, AIRequest, AIResponse, AIProviderError
│   │   ├── intent_parser.py         # LLMIntentProvider, MockIntentProvider
│   │   ├── intent_resolver.py       # TransposeIntentResolver, part/measure/interval resolvers
│   │   ├── intent_schema.py         # IntentContext, TransposeIntent, TransposeIntentResult
│   │   ├── intent_validator.py      # Deterministic validation
│   │   ├── openai_compatible_client.py  # OpenAI-compatible client with diagnostics
│   │   └── provider_diagnostics.py  # ProviderAttempt + error/subtype classification
│   ├── omr_normalization/           # OMR normalization + quality gate
│   ├── qa/                          # QA pipeline
│   ├── reconstruction/              # Reconstruction pipeline
│   ├── score_engine/
│   │   ├── musicxml/                # MusicXMLImporter / MusicXMLExporter
│   │   ├── score_ir/                # ScoreIR dataclasses
│   │   └── transposition/           # Deterministic transposition engine
│   └── ...
├── tests/                           # 214 tests (212 run + 2 skipped)
├── run_product_acceptance.py        # Phase-1 product acceptance
└── run_real_provider_reliability.py # Real-provider reliability smoke runner
```

Completed major modules:
- OMR Normalization / Quality Gate
- MusicXMLImporter (forward/backup/multi-voice fixes)
- Deterministic Transposition Engine V1
- Natural Language → TransposeRequest V1
- Real Provider E2E integration
- Provider reliability diagnostics (current focus)

---

## 2. OMR Normalization / Quality Gate Current State

- Module: `src/omr_normalization/`
- Detects notation/rhythm/structure issues in imported MusicXML.
- `OMRQualityGate` supports `STRICT`, `PERMISSIVE`, and `DETECT_ONLY` modes.
- The transposition service (`SafeTranspositionService`) consults the gate before editing.
- All existing gate tests pass; no changes expected here for the current track.

---

## 3. ScoreIR / MusicXML Importer / Exporter Current State

- `src/score_engine/score_ir/score_ir.py` — immutable-style ScoreIR with `Score`, `Part`, `Measure`, `Voice`, `Note`, `Chord`, `Rest`, `Pitch`, `KeySignature`, etc.
- `src/score_engine/musicxml/` — `MusicXMLImporter` and `MusicXMLExporter`.
- Known prior fixes: forward/backup cursor handling, multi-voice measure reconstruction.
- Exporter round-trips are covered by E2E tests.

---

## 4. Deterministic Transposition Engine Current State

- Module: `src/score_engine/transposition/`
- Components:
  - `engine.py` — `TranspositionEngine`
  - `request.py` — `TransposeRequest`, `TranspositionOperation`
  - `interval.py` — `Interval` with strict quality/number validation
  - `pitch_spelling.py` — enharmonic spelling logic
  - `key_signature.py` — key signature transposition
  - `service.py` — `SafeTranspositionService`
- Supports `INTERVAL`, `WRITTEN_TO_SOUNDING`, `SOUNDING_TO_WRITTEN`.
- Does not guess; rejects unsupported intervals/qualities.

---

## 5. Natural Language → TransposeRequest Current State

- `ai.intent_parser.LLMIntentProvider` calls an OpenAI-compatible endpoint.
- Prompt requests a single JSON object; response format defaults to `json_object`.
- `TransposeIntentResolver` maps NL fields to concrete `TransposeRequest`.
- `IntentValidator` performs deterministic validation against the actual score.
- Retry policy: **bounded 1 retry** in `LLMIntentProvider`.
- Status taxonomy: `ready`, `needs_clarification`, `unsupported`, `invalid`, `provider_error`.

---

## 6. Real Provider Compatibility / Diagnostics Current State

- `OpenAICompatibleClient` now extracts content from multiple sources:
  - `message.content`
  - `message.reasoning_content`
  - `message.tool_calls[].function.arguments`
  - `choices[0].text`
- Each call records a `ProviderAttempt` with:
  - `latency_ms`, `http_status`, `exception_type`, `is_timeout`
  - `response_body_empty`, `content_empty`
  - `has_reasoning_content`, `has_tool_calls`, `source_field`
  - `raw_content_head`/`tail`, `response_body_head`/`tail` (privacy-limited previews)
  - `finish_reason`, `model`, `usage`
  - `error_reason`, `error_detail`, `malformed_json_subtype`
- `AIProviderError` carries the failed `ProviderAttempt`.
- `run_real_provider_reliability.py` supports `--case` and `--iterations`.

---

## 7. Latest Complete Test Count and Result

```text
Ran 214 tests in 8.937s
OK (skipped=2)
```

The 2 skipped tests are `TestRealProviderIntegration` in `tests/test_nl_transpose_e2e.py`, skipped when `LLM_API_KEY` is unset.

---

## 8. Recent Real Kimi Provider Test Result

Last observed real-provider reliability run:

| Case | Result |
|------|--------|
| `把整首升大二度` | 17/20 success, 3 provider_error, 6 recovered_by_retry |
| `把长号升一个八度` | Noticeably more stable |

All 3 final `provider_error` instances for `把整首升大二度` were classified as `malformed_json`.

---

## 9. Confirmed malformed_json Types

From recent diagnostics:

- `json_in_reasoning_content`
- `truncated`

Subtype constants defined in `src/ai/provider_diagnostics.py`:
- `completely_invalid`
- `code_fence_wrapped`
- `natural_language_wrapped`
- `multiple_objects`
- `truncated`
- `json_in_reasoning_content`
- `json_in_tool_calls`
- `empty_content_other_field`
- `schema_mismatch`
- `other`

---

## 10. Current Unexecuted Next Step

**Provider Compatibility structured JSON deterministic extraction**

Implement deterministic normalization so that common OpenAI-compatible response wrapping issues do not cause `provider_error`:

- Extract JSON from `reasoning_content` when `content` is empty.
- Strip ` ```json ... ``` ` fences before JSON parsing.
- Remove small amounts of natural-language prefix/suffix around a JSON object.
- Handle truncated JSON only if a safe, bounded recovery is possible.
- Keep the validator standards strict; do not loosen interval/music-rule validation.

**Important**: This step has been identified but not implemented. Do not start it without a plan.

---

## 11. Files to Modify Next / Never Modify

### Should be modified for next task
- `src/ai/openai_compatible_client.py` — content extraction normalization
- `src/ai/intent_parser.py` — pre-parse response normalization, retry logic if needed
- `src/ai/provider_diagnostics.py` — classification updates if new subtypes emerge
- `tests/test_transpose_intent.py` — add normalization regression tests
- `tests/test_provider_reliability_runner.py` — runner safety tests if behavior changes
- `run_real_provider_reliability.py` — report fields if needed

### Do NOT modify
- `src/score_engine/transposition/engine.py`
- `src/score_engine/transposition/interval.py`
- `src/score_engine/transposition/pitch_spelling.py`
- `src/score_engine/transposition/key_signature.py`
- `src/score_engine/score_ir/*.py`
- `src/score_engine/musicxml/*.py`
- `src/omr_normalization/*.py`
- `src/qa/*.py`
- `IntentValidator` validator standards (do not loosen allowed statuses/intervals/measures)

---

## 12. Current Environment Variables

Only names; never commit or paste values:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `PYTHONPATH`

---

## 13. PowerShell Command Template for Real Provider Reliability Test

```powershell
$env:LLM_API_KEY="your_key"
$env:LLM_MODEL="kimi-k2-6"
$env:LLM_BASE_URL="your_relay_url"   # optional
$env:PYTHONPATH="src"
cd D:\puzi_project
python run_real_provider_reliability.py --case "把整首升大二度" --iterations 10
```

Replace `your_key`, `kimi-k2-6`, and `your_relay_url` with real values locally. Do not paste the API key into chat.

---

## 14. Key Design Principles and Prohibitions

1. **Deterministic validator standards are non-negotiable.** Do not widen allowed intervals, statuses, or measure ranges to make tests pass.
2. **No infinite retry.** Maximum bounded retry is 1 in `LLMIntentProvider`.
3. **No API Key or full prompt in logs/diagnostics.** Only privacy-safe previews (≤300 chars head/tail) are allowed.
4. **Do not loosen music semantics.** Transposition rules, pitch spelling, and OMR gate behavior must remain strict.
5. **Diagnostic fields belong in `ProviderAttempt`**, not in core `TransposeIntent` / `TransposeIntentResult`.
6. **Look at real failures first.** Do not implement broad speculative normalization before seeing actual malformed responses.
7. **Do not modify prohibited modules** listed in section 11.

---

## 15. Baseline Tests to Run Before Starting Next Work

From project root (`D:\puzi_project`):

```powershell
$env:PYTHONPATH="src"
python -m unittest discover tests -v
```

Expected result:

```text
Ran 214 tests in ~9s
OK (skipped=2)
```

If the count or result differs, stop and investigate before proceeding.
