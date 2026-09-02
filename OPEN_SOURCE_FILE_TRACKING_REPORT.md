# Open-Source File Tracking Report

Date: 2026-08-26
Scope: Phase 0.5 only. Classification is based on `git status --short` and `git ls-files --others --exclude-standard` at the repository root.

## Classification rules

- `REQUIRED_RUNTIME`: needed to install, diagnose, validate, or run the V0.1 candidate. External acquired dependencies may remain ignored when redistribution terms or provenance require acquisition.
- `REQUIRED_DOCUMENTATION`: needed to reproduce or audit the V0.1 candidate.
- `PRIVATE_GOLDEN_FIXTURE`: private/copyrighted score sources and successful-score artifacts; never commit.
- `GENERATED_OUTPUT`: derived OMR, MuseScore, PDF, image, benchmark, or QA output; do not commit as runtime source.
- `TEMPORARY`: virtual environments, caches, audit clones, and scratch files.
- `UNRELATED`: preserved development material outside the Phase 0.5/V0.1 reproduction boundary.

## REQUIRED_RUNTIME — track now

| Path/group | Why |
| --- | --- |
| `.agents/skills/focused-score-rebuild/SKILL.md` | Canonical, agent-neutral workflow contract (already tracked; modified). |
| `.agents/skills/focused-score-rebuild/assets/PRODUCTION_STAGE_GATES_QA.md` | Runtime QA stage gates. |
| `.agents/skills/focused-score-rebuild/references/successful-run-procedure.md` | Reproduction/run procedure referenced by Skill and manifest. |
| `.gitignore` | Protects private scores and generated/runtime-local artifacts. |
| `.zcode/config.json` | Optional ZCode integration; only the canonical `SCORE_REBUILD` profile is enabled. |
| `AGENTS.md` | Agent-neutral discovery and canonical Skill declaration. |
| `requirements.txt` | Core Python dependency declaration, including `pypdfium2` and `PyMuPDF`. |
| `requirements-optional.txt` | Optional `pdfplumber` declaration for legacy/advanced PDF text helpers. |
| `score-rebuild-manifest.json` | Machine-readable platform, binary, package, schema, Skill, and capability contract. |
| `score-rebuild.cmd` | Windows entry point for doctor/capabilities/schema/smoke commands. |
| `score_rebuild/*.py` | Reproduction CLI, manifest loader, environment doctor, capability doctor, schema acquisition, and synthetic smoke test. |
| `src/validation/__init__.py` and `src/validation/musicxml_xsd_validator.py` | Runtime MusicXML 4.0 validation with clear missing-schema failure. |
| `tests/fixtures/smoke/minimal_score.musicxml` | Repository-authored non-copyrighted smoke fixture. |
| `tests/test_score_rebuild_reproducibility.py` | Phase 0.5 regression tests. |

### REQUIRED_RUNTIME — acquire locally, do not track

| Path/group | Git treatment | Why |
| --- | --- | --- |
| `third_party/musicxml_4_0/schema/` | ignored | Exact W3C MusicXML 4.0 files are acquired from the pinned upstream commit and hash-verified. The repository tracks provenance and acquisition instructions instead of redistributing the files. |
| Audiveris, MuseScore Studio, Poppler, Python | external install | Required executables; paths are discovered or supplied through documented environment overrides. Binaries are not vendored. |

## REQUIRED_DOCUMENTATION — track now

- `CLEAN_MACHINE_REPRODUCTION.md`
- `EXECUTION_DEPENDENCY_AUDIT.md`
- `REPRODUCIBILITY_GRAPH.md`
- `SKILL_INVENTORY.md`
- `SKILL_INVENTORY_GLOBAL_CURRENT.md`
- `SKILL_INVENTORY_ZCODE_PLUGIN_CACHE.md`
- `docs/AGENT_INTEGRATION.md`
- `docs/INSTALL_WINDOWS.md`
- `docs/MUSICXML_SCHEMA_SETUP.md`
- `OPEN_SOURCE_FILE_TRACKING_REPORT.md`
- `CURRENT_MACHINE_REPRODUCTION_CHECK.md`

These files document the dependency graph, Skill provenance/boundary, clean installation, schema provenance, current-machine evidence, and exact Git boundary.

## PRIVATE_GOLDEN_FIXTURE — ignore, never track

- Root files matching `天使的脸*` and `Colores*` score/export formats.
- `prototype_pages_1_2/`, `full_score_original_rebuilt/`, `final_production/`, `LOGIC_PRO_DELIVERY/`, `colores_test/`, and `colores_v2/`.
- Any private source PDF, extracted page, Audiveris `.omr`, MuseScore `.mscz`/`.mscx`, MusicXML, linked part, lyric repair artifact, or visual reference derived from those scores.

No private score file appeared in the proposed tracked set. Existing historical helper scripts may contain fixture-specific filenames, but the corresponding score data is excluded.

## GENERATED_OUTPUT — ignore, do not track

- `outputs/`, `workdir/`, `orchestral_rebuild_*/`, `benchmarks/`, and per-score `previews/`, `source_pages/`, `qa_crops/`, `rendered/`, or `omr/` directories.
- Generated score/media formats covered by `.gitignore`: PDF, MSCZ/MSCX, OMR, PNG/JPEG/TIFF, audio, and video.
- Generated benchmark/recovery/normalization report patterns listed in `.gitignore`.
- Locally generated schema `SOURCE.json` together with the ignored acquired schema directory.

## TEMPORARY — ignore, do not track

- `.venv/`, `.venv_homr/`, `.venv_oemer/`, `venv/`, environment directories, `.tmp/`, `.tools/`, build/dist metadata, test/type/lint caches, and `__pycache__/`/`*.pyc`.
- Phase 0.5 temporary schema audit clones/backups and `.tmp/phase05_clean_venv`.
- `tmp_rest_test*.musicxml` and local logs.

The `src/omr` source allow-list is followed by a more specific cache exclusion so its generated `__pycache__` files do not become visible untracked files.

## UNRELATED — preserve locally, do not track in this V0.1 set

### Optional/internal ZCode Skill library

All currently untracked `.zcode/skills/*/SKILL.md` directories are development/operator aids, not dependencies of the one canonical project Skill:

`brainstorming`, `executing-plans`, `frontend-design`, `mcp-builder`, `musicxml-qa`, `omr-benchmark`, `receiving-code-review`, `requesting-code-review`, `score-export`, `score-generate`, `skill-creator`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `webapp-testing`, and `writing-plans`.

They remain present and disabled; Phase 0.5 does not delete or simplify them.

### Future/post-success implementation modules

- `src/ai/visual_repair_client.py`
- `src/auto_repair/**`
- `src/delivery/**`
- `src/normalization/**`
- `src/omr/**` (source files only; caches are `TEMPORARY`)
- `src/reconstruction/pipeline.py`
- `src/recovery/**`
- `src/repair/**`
- `src/score_engine/gap_resolution_engine.py`
- `src/score_engine/meter_constraint_engine.py`
- `src/validation/release_gates.py`

These modules belong to later development/V0.2 or broader pipeline work. They are not deleted, rewritten, or claimed as V0.1 reproduction prerequisites.

Associated untracked tests are likewise `UNRELATED` to the Phase 0.5 tracked set:

- `tests/test_actionable_evidence_filter.py`
- `tests/test_delivery_pipeline.py`
- `tests/test_musicxml_normalization_v1.py`
- `tests/test_reconstruction_pipeline_v1.py`
- `tests/test_recovery_router_v1.py`
- `tests/test_release_hardening.py`
- `tests/test_review_queue_v1.py`

### Superseded/retrospective documents and reports

- `PUZI_PROJECT_HANDOFF.md`
- `docs/CURRENT_HANDOFF.md`
- `docs/dependency_license_inventory.md` (superseded for MusicXML schema treatment by `docs/MUSICXML_SCHEMA_SETUP.md`)
- `reports/ORCHESTRAL_SKILL_ZCODE_INTEGRATION.md`
- `reports/SKILL_ACTIVATION_AUDIT.md`
- `reports/SKILL_ROUTING_FINAL.md`
- `reports/codex_parity_audit.md`
- `reports/codex_repair_logic_audit.md`

They remain available locally but are not runtime inputs and are not included in the V0.1 candidate tracking boundary.

## Modified tracked files deliberately excluded from Phase 0.5 staging

The working tree already contains other modified tracked files. Phase 0.5 does not stage or rewrite them:

- `reports/github_preflight_audit.md`
- `reports/nl_edit_benchmark_v1.json`
- `reports/nl_edit_benchmark_v1.md`
- `reports/nl_transpose_e2e_report.md`
- `reports/zcode_capability_inventory.md`
- `src/ai/openai_compatible_client.py`
- `src/ai/provider_capability.py`
- `src/reconstruction/__init__.py`
- `src/reconstruction/reconstruction_pipeline.py`
- `src/score_engine/musicxml/musicxml_to_score_ir.py`
- `src/score_engine/transposition/interval.py`
- `tests/test_score_engine.py`
- `tests/test_transposition.py`

These are treated as `UNRELATED` to the present staging operation. Their local changes are preserved.

## Tracking decision

Only the files listed under `REQUIRED_RUNTIME — track now` and `REQUIRED_DOCUMENTATION — track now` are eligible for staging in this task. No commit, release commit, tag, or freeze is created.

`V0.1_FREEZE_READY = NO` until the staged set is reviewed/committed and reproduced from that commit on a separate clean Windows machine.
