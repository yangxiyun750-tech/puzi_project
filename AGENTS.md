# AI Score Toolkit — Project Instructions

## Frozen Components

The following components are **frozen** as of 2026-08-18 and must not be modified without explicit approval:

- `src/ai/intent_parser.py`
- `src/ai/intent_resolver.py`
- `src/ai/intent_validator.py`
- `src/ai/intent_schema.py`
- `src/ai/json_extraction.py`
- `src/ai/openai_compatible_client.py`
- `src/ai/provider_capability.py`
- `src/ai/provider_diagnostics.py`
- `src/score_engine/transposition/engine.py`
- `src/score_engine/transposition/interval.py`
- `src/score_engine/transposition/request.py`
- `src/score_engine/transposition/pitch_spelling.py`
- `src/score_engine/score_ir/score_ir.py`
- `src/score_engine/musicxml/`

These represent **Intent Parser V1.1** and the **core deterministic transposition engine**.

## Default Skill Profile

This project uses the `OMR` skill profile by default:

- `score-reconstruction-v2` — enabled
- All other skills — disabled until explicitly requested

Do not enable all skills simultaneously.

## Credential Policy

- No API keys, tokens, or secrets are committed to the repository.
- Use environment variables or ZCode secret configuration only.
- If a credential is missing, mark the capability as `WAITING_FOR_CREDENTIAL` and stop.

## Toolchain Constraints

- **MuseScore CLI** is available at `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`.
- **Audiveris** is available at `C:\Program Files\Audiveris\Audiveris.exe` (AGPL-3.0 — review required for commercial use).
- **Melogen** is not active without `MELOGEN_API_KEY`.
- Do not set any OMR provider as the new default in this phase.

## License Review

Before adopting any new third-party capability, check:

1. Owner / source
2. License
3. Install scripts
4. Network access
5. File access
6. Shell commands

AGPL/GPL tools must remain external processes.

## Scope Rules

- Do not start new product UI development unless explicitly requested.
- Do not run benchmarks comparing OMR providers unless explicitly requested.
- Do not modify frozen components.
