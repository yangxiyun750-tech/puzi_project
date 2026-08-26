# Fresh-Clone Reproduction Check

Date: 2026-08-27

## Decision

- `SANITIZATION = PASS`
- `FRESH_CLONE_REPRODUCTION = PASS`
- `V0.1_FREEZE_READY = NO`
- `PHYSICAL_CLEAN_MACHINE_VERIFIED = NO`

The local fresh-clone baseline passed. V0.1 is not marked freeze-ready because the full tracked repository still contains legacy machine-specific standalone entry points and fixture/debug paths outside the Phase 0.5 staged-file sanitization authorization.

## Checkpoint

- Commit: `30e85082438d93706260ca76f42585422552ffa8`
- Commit subject: `chore: close score-rebuild reproduction gaps`
- Commit type: non-release checkpoint
- Release tag: none
- Published: no

The checkpoint contains the 33 reviewed Phase 0.5 runtime and documentation files. Unrelated working-tree modifications were not included.

## Fresh clone

- Location: `C:\tmp\score-rebuild-phase06-30e8508-20260827`
- Clone mode: local Git clone with `--no-local`
- Checked-out commit: `30e85082438d93706260ca76f42585422552ffa8`
- Remote after checkout: removed before testing
- Initial status: clean

No file was copied from the original working tree. The clone received only objects tracked by the checkpoint commit.

Generated local test state was limited to the ignored clone-local `.venv`, `.phase06_logs`, Python caches, and the schema acquired by the documented installer.

## Phase 0.5 staged-file sanitization

The complete staged diff was rescanned before commit.

Results:

- no private PDF, MSCZ, MusicXML, MXL, OMR, PNG, or other private-score artifact;
- no API key, token, password, or secret value;
- no personal user directory, original working-tree path, session identifier, or GUID;
- no temporary file, virtual environment, cache, or generated binary;
- ZCode commands changed from local repository/cache paths to executable names resolved by the client environment;
- audit paths changed to repository-relative paths, environment variables, or generic placeholders.

Standard Windows system installation paths under `C:\Program Files` were retained where they record doctor results. They contain no user identity or machine identifier.

## Internal Skill availability

Result: `PASS`

Tracked and present in the clone:

- `.agents/skills/orchestral-score-rebuild/SKILL.md`
- `references/qa-protocol.md`
- `references/successful-run-procedure.md`
- `assets/QA_REPORT_TEMPLATE.md`
- `assets/PRODUCTION_STAGE_GATES_QA.md`
- `scripts/make_audiveris_playlist.py`
- `scripts/musicxml_invariants.py`

The runtime manifest contains one required user-facing Skill and no runtime dependency on `skill-creator`. Core `score_rebuild`, Skill, manifest, schema, and validation paths contain no reference to the original repository.

## Fresh environment construction

1. Located documented external Python 3.12 through `py -3.12`.
2. Created a new `.venv` inside the clone.
3. Installed only `requirements.txt`.
4. Acquired the exact pinned MusicXML 4.0 schemas with `python -m score_rebuild schema-install`.
5. Verified every schema file against the SHA-256 values in `score-rebuild-manifest.json`.

Dependency installation and schema acquisition both exited with code `0`.

## Environment doctor

Result: `PASS=18 WARN=1 FAIL=0`, exit code `0`.

Passed:

- Python 3.12.10;
- all nine required Python distributions/imports;
- Poppler `pdftoppm` 26.05.0;
- Audiveris 5.11.0;
- MuseScore Studio 4.7.4;
- Audiveris-bundled OpenJDK 25.0.3;
- canonical internal Skill and all required resources;
- pinned MusicXML 4.0 schema;
- project write probe;
- system temporary-directory write probe.

Warning:

- optional `pdfplumber` was not installed. It is not required by the canonical V0.1 doctor/smoke path.

Poppler was resolved through the documented `PDFTOPPM_EXE` override. Its current-machine installation happens to be managed outside the repository; this is an allowed external binary, not a project file or hidden repository dependency. A physical clean-machine test should use a normal standalone Poppler installation.

## Capability doctor

Result: exit code `0`.

- `CODE_REASONING: AVAILABLE` — generic operator-verified coding-agent declaration.
- `VISUAL_REVIEW: NOT_CONFIGURED` — image support was not inferred.
- `HUMAN_REVIEW_FALLBACK: AVAILABLE` — generic operator declaration.
- `PIPELINE_MODE: MANUAL_VISUAL_REVIEW_REQUIRED`.

The unavailable automated visual provider is not treated as a failure for the human-in-the-loop V0.1 baseline.

## Synthetic smoke test

Result: `PASS`, exit code `0`.

Verified entirely from fresh-clone project code and the tracked synthetic fixture:

1. repository-authored MusicXML input parsed;
2. pinned MusicXML 4.0 XSD validation passed;
3. MusicXML invariant self-test passed;
4. MuseScore imported MusicXML and created native MSCZ;
5. MuseScore reopened the MSCZ and exported PDF;
6. Poppler rendered the PDF to PNG;
7. `BASIC_PIPELINE_CONNECTIVITY` was reported.

The test is intentionally an environment/connectivity test, not a private-score or musical-quality regression test.

The seven Phase 0.5 reproducibility unit tests also passed from the clone. Runtime module-origin checks resolved `score_rebuild` and the MusicXML validator inside the clone, and confirmed that the original working tree was absent from `sys.path`.

## Hidden-dependency and path-leak checks

Execution logs contained no reference to:

- the original repository/workspace;
- Desktop or Documents directories;
- a private score or private fixture directory;
- temporary legacy scripts;
- a global custom Skill;
- ZCode runtime configuration;
- Codex conversation/session state;
- `skill-creator` as a runtime dependency.

The doctor log includes the resolved external `PDFTOPPM_EXE` and system `TEMP` locations. Both are documented environment/system dependencies. Neither was read from the original repository, and neither supplied project code or private data.

The clone had no Git remote during execution. Test-generated `.venv`, schema, logs, and caches were ignored and were not mistaken for tracked runtime inputs.

## Missing dependencies

No required dependency was missing for the canonical V0.1 fresh-clone doctor and synthetic smoke baseline.

## Unexpected external dependencies

No undeclared external dependency was used by the tested baseline. Python, Python packages, Poppler, Audiveris, MuseScore, Java, network schema acquisition, and the human/coding-agent capability declarations are all represented in the manifest or installation documentation.

## Remaining reproduction gaps

The following tracked files predate the Phase 0.5 staged set and were not modified under the current authorization:

1. `src/reconstruction/reconstruction_pipeline.py` has a legacy standalone `main()` that hardcodes a developer-local Poppler path. The canonical Phase 0.6 doctor/smoke path did not import or execute this entry point, but the path is not portable.
2. `src/score_engine/musicxml/musicxml_to_score_ir.py` contains a standalone test helper with a private fixture path.
3. `src/score_engine/validation/roundtrip_validator.py` contains standalone test/output paths for the same historical fixture.
4. Historical tracked handoff/report documents still contain the old repository location. They were not execution inputs.
5. A second physical Windows computer has not been tested.

Items 1–4 are not hidden dependencies of the successful local fresh-clone baseline, so `FRESH_CLONE_REPRODUCTION = PASS`. They are nevertheless repository portability/sanitization debt and prevent a conservative V0.1 freeze decision.

No V0.2 behavior, musical reconstruction behavior, private score, release tag, GitHub publication, or release artifact was created or changed.
