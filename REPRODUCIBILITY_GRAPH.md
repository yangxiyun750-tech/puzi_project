# Reproducibility Graph — Successful Printed-Orchestral-Score Workflow

Audit date: 2026-08-25
Status: audited, **not frozen**

## Legend

- **[REQUIRED]** — demonstrated or unavoidable for the successful path.
- **[OPTIONAL]** — useful but not demonstrated as necessary.
- **[DEVELOPMENT ONLY]** — used to build/test/document the workflow, not to process a score.
- **[HUMAN FALLBACK]** — required authority when notation is ambiguous or acceptance is subjective.

## Complete dependency chain

```text
[REQUIRED] User intent + source PDF + declared full-score page range
    |
    v
[REQUIRED] project-local orchestral-score-rebuild Skill
    |
    +--> [REQUIRED] successful-run stage-gate reference
    +--> [REQUIRED] QA protocol + QA report template
    +--> [REQUIRED] repository helper scripts
    |
    v
[REQUIRED] environment readiness gate
    +--> Python 3.12.x
    +--> Poppler / pdftoppm
    +--> Audiveris + Java runtime
    +--> MuseScore Studio 4
    |
    v
[REQUIRED] immutable source handling
    |
    v
[REQUIRED] Poppler 400-DPI full-score page rendering
    |
    v
[REQUIRED] ordered Audiveris book/playlist
    |
    v
[REQUIRED] Audiveris transcribe + save .omr + export MusicXML/MXL
    |
    +--> [REQUIRED] retain logs, playlist, .omr, images
    |
    v
[REQUIRED] original-key two-page prototype
    +--> [REQUIRED] MusicXML invariants
    +--> [REQUIRED] MuseScore native notation import
    +--> [REQUIRED] visual source comparison
    +--> [HUMAN FALLBACK] prototype acceptance / ambiguous notation
    |
    v
[REQUIRED] real MuseScore instrument mapping
    +--> B-flat Clarinet transposition definition
    +--> Horn in F definitions
    +--> Harp grand staff
    +--> Solo Voice
    +--> clefs, percussion behavior, staff order/count
    |
    v
[REQUIRED] complete original-key full-score reconstruction
    +--> [OPTIONAL] legacy printed parts as secondary evidence only
    +--> [REQUIRED] page/staff/measure comparison with original PDF
    |
    v
[REQUIRED] repair/verification loop
    +--> deterministic structure and XML checks
    +--> code-guided safe repairs
    +--> reasoning + vision review
    +--> native Chinese Lyrics repair
    +--> native Harp Arpeggio and Glissando repair
    +--> [HUMAN FALLBACK] unresolved pitch/rhythm/voice/object/layout
    |
    v
[REQUIRED] verified original-key MuseScore checkpoint + MusicXML baseline
    |
    v
[REQUIRED] concert-pitch source-key verification
    |
    v
[REQUIRED] transpose MUSIC in MuseScore to requested concert key
    |
    +--> [REQUIRED] MuseScore instrument definitions derive written pitch
    +--> [REQUIRED] baseline/final MusicXML invariant checks
    +--> [REQUIRED] written/concert-pitch spot checks
    |
    v
[REQUIRED] fresh linked-part generation from master
    |
    +--> [REQUIRED] written-pitch and identity checks
    +--> [REQUIRED] part layout/page-turn visual QA
    +--> [HUMAN FALLBACK] professional engraving acceptance
    |
    v
[REQUIRED] save -> close -> reopen persistence validation
    |
    v
[REQUIRED] score/part PDF + MSCZ + MusicXML export
    |
    v
[REQUIRED when requested] MusicXML round-trip reopen in MuseScore
    |
    +--> [OPTIONAL] Logic Pro import package
    +--> PDFs as visual references; linked-part relation is not portable
    |
    v
[REQUIRED] QA report, zero unexplained structural differences,
           no open high-severity musical findings
```

## Agent/capability branch

```text
[REQUIRED] code_reasoning_provider
    +--> plans, commands, script repair, XML interpretation, evidence synthesis

[REQUIRED] visual_review_provider OR equivalent manual visual reviewer
    +--> original-vs-rendered page inspection, lyrics/Harp objects, collisions/layout

[HUMAN FALLBACK] musically qualified reviewer
    +--> ambiguous notation, transposition semantics, native-object correctness,
         final professional acceptance

[REQUIRED] deterministic scripts
    +--> counts, hashes, measure/part/invariant checks, executable readiness
    +--> cannot replace vision or musical judgment
```

## Skill and integration branch

```text
[REQUIRED] orchestral-score-rebuild (project local)

[DEVELOPMENT ONLY] skill-creator
    +--> authored/updated the runtime Skill

[OPTIONAL] PDF Skill
    +--> visible historically, not invoked

[OPTIONAL] current ZCode score-reconstruction-v2 / musicxml-qa / score-export
    +--> postdate successful baseline; required only if V0.1 explicitly adopts OMR_FULL

[OPTIONAL] web lookup
    +--> documentation discovery only; commands must be local for reproduction

[OPTIONAL] MCP servers/connectors
    +--> none demonstrated in the historical successful path

[DEVELOPMENT ONLY] .tools Skill source checkouts, code-review/TDD/planning Skills

[UNRELATED] design, Adobe, iOS, Hyperframes, office-document Skills
```

## Repository/external boundary

| Inside proposed repository | Must be installed/configured externally | Must be supplied per score |
|---|---|---|
| project-local Skill and references | MuseScore Studio 4 | legal source PDF |
| QA template/protocol | Audiveris + Java runtime | full-score/part page ranges |
| helper scripts and tests | Poppler `pdftoppm` | instrument order and source/destination key contract |
| Python dependency declaration/lock | Python 3.12.x + packages | model/provider credentials if cloud-hosted |
| environment doctor and config examples | reasoning provider and vision capability | human musical reviewer when ambiguity remains |
| MusicXML schema acquisition/provenance instructions | optional Logic Pro for downstream import | acceptance decisions and QA sign-off |

## Freeze gates

The graph is only reproducible after every **[REQUIRED]** repository node is tracked, dependency versions are installable from a clean machine, the environment doctor passes, the provider capability check passes, and the repository can run its non-score self-tests from a clean clone. Current status fails those conditions; see `CLEAN_MACHINE_REPRODUCTION.md`.
