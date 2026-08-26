# AI Score Toolkit — Project Instructions

## V0.1 Scope

The V0.1 candidate preserves the validated printed-orchestral-score workflow. Do not implement V0.2 automatic review/repair, change musical reconstruction behavior, or process private scores while working on reproducibility infrastructure.

## Canonical user-facing Skill

The canonical default is the single project-local Skill:

```text
.agents/skills/orchestral-score-rebuild/SKILL.md
```

Users invoke one ScoreRebuild workflow. The Skill owns stage ordering and directly references its QA/procedure resources. Do not require users to manually chain internal Skills.

The core repository is coding-agent-neutral. ZCode configuration is an optional compatibility layer, not a runtime dependency. In ZCode, the default `SCORE_REBUILD` profile enables only `orchestral-score-rebuild`. All other profiles are explicit development, benchmark, legacy-comparison, or future-pipeline choices and remain disabled by default.

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

## Credential Policy

- No API keys, tokens, or secrets are committed to the repository.
- Use environment variables or the selected agent's secret configuration.
- If a credential is missing, mark the capability as `WAITING_FOR_CREDENTIAL` and stop.
- A model/provider name is not evidence of image-input support. Run the capability doctor and use manual visual review when vision is unproven.

## Toolchain Constraints

- Run `python -m score_rebuild doctor` before any source score is processed.
- Resolve executables from environment overrides, `PATH`, or documented common locations. Do not hard-code developer-machine absolute paths.
- Audiveris and MuseScore remain external applications/CLIs.
- The proven baseline uses Poppler 400-DPI rendering and Audiveris OMR as directed by the canonical Skill.
- Experimental OMR providers and current V0.2 modules are not the V0.1 default.
- MusicXML XSD validation uses a locally acquired, SHA-256-verified official v4.0 schema and performs no runtime network access.

## License Review

Before adopting any new third-party capability, check:

1. Owner/source
2. License
3. Install scripts
4. Network access
5. File access
6. Shell commands

AGPL/GPL tools must remain external processes. Do not bundle unknown third-party schema or binary files.

## Scope Rules

- Do not start product UI development unless explicitly requested.
- Do not run OMR provider benchmarks unless explicitly requested.
- Do not modify frozen components.
- Do not commit copyrighted score scans, MuseScore projects, rendered pages, OMR projects, or private golden fixtures.
- Do not declare V0.1 frozen until the clean-machine checklist and reproduction report pass.
