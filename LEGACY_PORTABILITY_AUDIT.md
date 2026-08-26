# Legacy Portability Audit

Date: 2026-08-27

Scope: every file in the Git index after checkpoint `30e85082438d93706260ca76f42585422552ffa8`, including the staged Phase 0.6 report. Searches were case-insensitive where appropriate and covered Windows drive paths, user directories, Desktop/Documents, tool locations, temporary paths, ZCode/Codex caches, private fixture names/directories, and credential-like assignments.

## Classification definitions

- `RUNTIME_REQUIRED`: exercised or referenced by the public ScoreRebuild runtime and must use portable discovery.
- `TEST_ONLY`: executable only for tests, smoke checks, or developer validation.
- `PRIVATE_FIXTURE`: dedicated to an authorized private regression input/output and never required publicly.
- `DOCUMENTATION_ONLY`: historical result, install example, report, ignore rule, or workflow description; not executable.
- `OBSOLETE`: retained legacy entry point or helper outside the canonical V0.1 baseline.

## RUNTIME_REQUIRED

| Finding | Files | Decision/action |
| --- | --- | --- |
| Canonical executable discovery | `score_rebuild/doctor.py`, `score-rebuild-manifest.json`, `score_rebuild/smoke.py` | Portable and retained: explicit environment override, then PATH, then generic Windows candidates. |
| Legacy reconstruction standalone entry point hardcoded Audiveris, MuseScore, and a user-local Poppler cache | `src/reconstruction/reconstruction_pipeline.py` | Portability blocker. Replace all three literals with the canonical manifest/doctor resolver. The pipeline class and music operations remain unchanged. |
| Program Files entries in manifest | `score-rebuild-manifest.json` | Retained as generic auto-discovery templates using `{PROGRAMFILES}`; they are not personal paths. |
| CLI arguments already portable | `src/qa/qa_pipeline.py` | Retained: `--pdftoppm` and `--musescore` accept caller configuration/PATH. |

## TEST_ONLY

| Finding | Files | Decision/action |
| --- | --- | --- |
| Private MusicXML standalone import test | `src/score_engine/musicxml/musicxml_to_score_ir.py` | Replace repository/private path with `SCORE_REBUILD_PRIVATE_FIXTURE_MUSICXML`; missing configuration prints `PRIVATE_FIXTURE_AVAILABLE = NO` and `SKIPPED`. |
| Private MusicXML round-trip test/output paths | `src/score_engine/validation/roundtrip_validator.py` | Use the same optional input variable and `SCORE_REBUILD_PRIVATE_FIXTURE_OUTPUT_DIR`; default output is system temp. |
| Standard MuseScore common-location candidates | `run_product_acceptance.py`, `src/qa/render_qa.py`, `tests/e2e_fixtures.py`, `tests/smoke_test_toolchain.py` | Retained. These are generic Windows candidates or test helpers, not user-specific paths; environment/constructor overrides remain available where applicable. |
| Generated NL test report contains user TEMP paths | `reports/nl_transpose_e2e_report.md` | Documentation artifact, but sanitize to `<SYSTEM_TEMP>/...` so it exposes no user profile or random machine directory. |
| Synthetic fixture | `tests/fixtures/smoke/minimal_score.musicxml` | Retained; repository-authored and non-copyrighted. |

## PRIVATE_FIXTURE

| Finding | Files | Decision/action |
| --- | --- | --- |
| Generated private full-score QA report | `QA_REPORT.md` | Remove from Git tracking and add a root ignore rule; preserve the local file. The tracked template remains the public replacement. |
| Generated private visual/triage/root-cause reports | `EVIDENCE_TRIAGE_REPORT.md`, `MEASURE_LOCALIZATION_REPORT.md`, `ROOT_CAUSE_REPORT.md`, `VISUAL_RECOVERY_REPORT.md` | Remove from Git tracking and ignore by exact root names; preserve local files. They are outputs, not runtime inputs. |
| Dedicated private production/inspection helpers with relative private names | `extract_pdf_text.py`, `final_production_prepare.py`, `final_validate_pretranspose.py`, `inspect_harp_musicxml.py`, `inspect_part_pages.py`, `inspect_pdf_lyrics.py`, `inspect_pdf_voice_band.py`, `inspect_voice_musicxml.py`, `logic_delivery_export.py`, `logic_validate_musicxml.py`, `logic_validate_package.py`, `map_pdf_lyrics_to_voice.py` | Retain as explicitly private-only historical utilities. They are not imported by the public doctor/smoke/runtime and their source/output directories are ignored. No private artifact is committed. |
| Canonical successful-baseline contract names | `.agents/skills/orchestral-score-rebuild/SKILL.md`, its QA template/protocol, and `.gitignore` | Retain intentionally. These describe the validated workflow and protection patterns; they do not bundle or require the private fixture for public smoke/install. |

## DOCUMENTATION_ONLY

| Finding | Files | Decision/action |
| --- | --- | --- |
| Old repository drive path | `docs/HANDOFF_CURRENT.md`, `docs/NEXT_TASK.md`, `reports/github_preflight_audit.md`, `reports/zcode_capability_inventory.md` | Replace with `<REPOSITORY_ROOT>` or repo-relative commands. |
| Old local GitHub MCP binary path | `reports/github_preflight_audit.md`, `reports/zcode_capability_inventory.md` | Replace with `github-mcp-server` resolved by PATH/client configuration. |
| Standard installed tool result paths | `CURRENT_MACHINE_REPRODUCTION_CHECK.md`, `EXECUTION_DEPENDENCY_AUDIT.md`, `reports/zcode_capability_inventory.md` | Retain or describe as `{PROGRAMFILES}`/standard installation results; no username or machine ID. |
| Previous fresh-clone location | `FRESH_CLONE_REPRODUCTION_CHECK.md` | Retain as required historical test evidence; `C:\tmp` is a generic temporary test root without identity. |
| Private names in architectural/history reports | `ARCHITECTURE_V2_REPORT.md`, `OPEN_SOURCE_FILE_TRACKING_REPORT.md`, `docs/INSTALL_WINDOWS.md`, `reports/github_preflight_audit.md` | Retain only where documenting exclusions, history, or a non-use guarantee. They are not runtime fixture paths. |
| Credential examples | `docs/HANDOFF_CURRENT.md`, `docs/NEXT_TASK.md`, tests | Retain only explicit placeholders such as `your_key`, `${ENV_VAR}`, and `test-key`; scan found no real secret. |

## OBSOLETE

| Finding | Files | Decision/action |
| --- | --- | --- |
| Deprecated Audiveris-only standalone entry point | `src/reconstruction/reconstruction_pipeline.py` | Retain for compatibility because deletion could affect users. Remove only machine paths; do not change pipeline behavior. |
| Standalone private import/round-trip functions | `src/score_engine/musicxml/musicxml_to_score_ir.py`, `src/score_engine/validation/roundtrip_validator.py` | Retain as optional developer checks with explicit private configuration and safe skip behavior. |

## Expected post-cleanup scan allowances

The following strings may remain without constituting portability debt:

- `{PROGRAMFILES}` manifest templates and standard `C:\Program Files` result examples;
- generic placeholders such as `<REPOSITORY_ROOT>`, `<SYSTEM_TEMP>`, `<USER_HOME>`, and `X:\private-fixtures\...`;
- private work titles in the canonical validated Skill, exact `.gitignore` exclusion rules, and historical documentation explaining what is not bundled;
- environment-variable names and obvious credential placeholders.

No personal username, user-profile path, original private project drive path, local Codex/ZCode cache path, or required private fixture path is acceptable after cleanup.
