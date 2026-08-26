# Next Task — Provider Compatibility Structured JSON Deterministic Extraction

**Status**: Not started. Do not execute yet.

## Goal

Make the real OpenAI-compatible provider layer robust against common response-format wrapping issues without lowering deterministic validator standards or adding unlimited retry.

Confirmed issues from recent real Kimi runs:
- `json_in_reasoning_content`
- `truncated`

Other known OpenAI-compatible wrapping patterns to prepare for:
- ` ```json ... ``` ` code fences
- natural-language prefix/suffix around a JSON object
- multiple JSON objects in one response
- JSON inside `tool_calls[].function.arguments`
- empty `content` with usable text in `reasoning_content`

## Scope

1. Implement deterministic pre-parse normalization inside the provider/client layer.
2. Preserve full diagnostics so future failures remain classifiable.
3. Add regression tests for each supported normalization path.
4. Run the same real-provider 10-iteration reliability test for `把整首升大二度` to verify improvement.

## Out of Scope

- Changing transposition rules, pitch spelling, key signature logic.
- Changing OMR Normalization or Quality Gate behavior.
- Adding more than 1 bounded retry.
- Returning `ready` for semantically invalid user requests.

## Suggested Files to Modify

- `src/ai/openai_compatible_client.py`
  - Decide whether normalization belongs in the client or the provider.
  - If in the client, ensure `_extract_content` returns normalized JSON when possible.
- `src/ai/intent_parser.py`
  - Add a `_normalize_model_output(text: str) -> str` helper.
  - Apply normalization before `json.loads`.
  - Keep `classify_malformed_json` as a fallback classifier when normalization fails.
- `src/ai/provider_diagnostics.py`
  - Update subtype classification if new failure modes appear.
- `tests/test_transpose_intent.py`
  - Add tests for each normalization case.
- `tests/test_provider_reliability_runner.py`
  - Add runner-level regression tests if reporting changes.
- `run_real_provider_reliability.py`
  - Optionally expose a `--normalize` flag or keep normalization always-on after validation.

## Definition of Done

- [ ] All 214 baseline tests still pass.
- [ ] New regression tests cover: reasoning_content extraction, fence stripping, prefix/suffix stripping, multiple-object rejection, truncation handling.
- [ ] Real-provider 10-iteration run for `把整首升大二度` completes without `AttributeError`.
- [ ] `malformed_json` count is measured and reported; if it still occurs, subtype is recorded.
- [ ] No API Key or full prompt appears in logs or reports.
- [ ] Deterministic validator standards unchanged.

## Command to Validate After Implementation

```powershell
$env:LLM_API_KEY="your_key"
$env:LLM_MODEL="kimi-k2-6"
$env:LLM_BASE_URL="your_relay_url"   # optional
$env:PYTHONPATH="src"
cd <REPOSITORY_ROOT>
python -m unittest discover tests -v
python run_real_provider_reliability.py --case "把整首升大二度" --iterations 10
```

Do not paste the API key into chat.
