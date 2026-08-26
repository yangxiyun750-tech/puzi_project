# Skill Inventory — V0.1 Execution-Dependency Audit

Audit date: 2026-08-25
Historical success window: 2026-08-12 through the Logic-delivery step on 2026-08-13
Historical evidence: `<CODEX_HOME>/sessions/<historical-session>.jsonl` plus the related auto-review session
Current target: `<REPOSITORY_ROOT>`

## Interpretation

`Visible` means the Skill was advertised to the agent. `Invoked` requires stronger evidence: the Skill body was injected/read in the successful run or a recorded Skill-tool call resolved it. File presence or profile membership alone is not invocation.

The successful historical run injected exactly two Skill bodies: `skill-creator` once and `orchestral-score-rebuild` eight times. No evidence shows that a PDF, MuseScore, MusicXML, OMR, or separate QA Skill was invoked. PDF rendering, MuseScore, MusicXML, OMR, and QA were performed by binaries, scripts, direct tool calls, the orchestral Skill, conversation instructions, and agent/human review.

## Historical Codex catalog visible during the successful task

Paths below are the paths/families recorded in session instruction catalogs. Primary-runtime Skills appeared at more than one cache version; that does not make them runtime dependencies.

| Skill | Recorded path or path family | Purpose | Successful-run evidence | Classification | Open-source treatment |
|---|---|---|---|---|---|
| orchestral-score-rebuild | `<LEGACY_WORKSPACE>/.agents/skills/orchestral-score-rebuild/SKILL.md` | Printed orchestral PDF → native MuseScore, transposition, linked parts, QA | Body injected 8 times; user explicitly invoked it; workflow matches | **RUNTIME REQUIRED** | Include in repo |
| skill-creator | `<CODEX_HOME>/skills/.system/skill-creator/SKILL.md` | Create/update Skills | Body injected once to create `orchestral-score-rebuild`; not used to process notation | **DEVELOPMENT ONLY** | Document; do not require at runtime |
| skill-installer | `<CODEX_HOME>/skills/.system/skill-installer/SKILL.md` | Install Skills | Visible only; no body/call evidence | Unrelated to successful execution | Do not bundle/require |
| pdf | `<CODEX_HOME>/plugins/cache/openai-primary-runtime/pdf/<version>/skills/pdf/SKILL.md` | General PDF inspection/generation | Visible only; no Skill injection. `pdftoppm` and Python scripts were called directly | Optional convenience | Mention only |
| openai-docs | `<CODEX_HOME>/skills/.system/openai-docs/SKILL.md` | OpenAI/Codex documentation | Visible only in historical production | Unrelated to score runtime | Do not require |
| imagegen | `<CODEX_HOME>/skills/.system/imagegen/SKILL.md` | Raster generation/editing | Visible only; source/page rendering did not use it | Unrelated | Exclude |
| plugin-creator | `<CODEX_HOME>/skills/.system/plugin-creator/SKILL.md` | Codex plugin scaffolding | Visible only | Unrelated | Exclude |
| open-design | `<CODEX_HOME>/skills/open-design/SKILL.md` | Design artifacts/web UI | Visible only | Unrelated | Exclude |
| video-spec-builder | `<CODEX_HOME>/skills/video-spec-builder/SKILL.md` | Video specification | Visible only | Unrelated | Exclude |
| documents | `...\openai-primary-runtime\documents\<version>\skills\documents\SKILL.md` | DOCX work | Visible only | Unrelated | Exclude |
| presentations | `...\openai-primary-runtime\presentations\<version>\skills\presentations\SKILL.md` | Presentation work | Visible only | Unrelated | Exclude |
| spreadsheets | `...\openai-primary-runtime\spreadsheets\<version>\skills\spreadsheets\SKILL.md` | Spreadsheet artifacts | Visible only | Unrelated | Exclude |
| excel-live-control | `...\openai-primary-runtime\spreadsheets\<version>\skills\excel-live-control\SKILL.md` | Live Excel control | Visible only | Unrelated | Exclude |
| template-creator | `...\openai-primary-runtime\template-creator\<version>\skills\template-creator\SKILL.md` | Artifact-template Skills | Visible only | Unrelated | Exclude |
| adobe-batch-edit-photos | `...\app-69312da8e4dc81919370cb86fd172b6c\7.0.0\skills\adobe-batch-edit-photos\SKILL.md` | Photo batch editing | Visible only | Unrelated | Exclude |
| adobe-create-mockups | same Adobe package, matching Skill folder | Product mockups | Visible only | Unrelated | Exclude |
| adobe-create-social-variations | same Adobe package | Social asset variants | Visible only | Unrelated | Exclude |
| adobe-design-from-template | same Adobe package | Template-based visual design | Visible only | Unrelated | Exclude |
| adobe-edit-quick-cut | same Adobe package | Video quick cut | Visible only | Unrelated | Exclude |
| adobe-retouch-portraits | same Adobe package | Portrait retouching | Visible only | Unrelated | Exclude |
| ios-app-intents | session catalog package at revision `bd2122cb` | iOS App Intents | Visible only | Unrelated | Exclude |
| ios-debugger-agent | same package/revision | iOS debugging | Visible only | Unrelated | Exclude |
| ios-ettrace-performance | same package/revision | iOS performance tracing | Visible only | Unrelated | Exclude |
| ios-memgraph-leaks | same package/revision | iOS leak analysis | Visible only | Unrelated | Exclude |
| ios-simulator-browser | same package/revision | iOS simulator automation | Visible only | Unrelated | Exclude |
| swiftui-liquid-glass | same package/revision | SwiftUI visual effects | Visible only | Unrelated | Exclude |
| swiftui-performance-audit | same package/revision | SwiftUI performance | Visible only | Unrelated | Exclude |
| swiftui-ui-patterns | same package/revision | SwiftUI patterns | Visible only | Unrelated | Exclude |
| swiftui-view-refactor | same package/revision | SwiftUI refactoring | Visible only | Unrelated | Exclude |
| gsap | session catalog Hyperframes package at revision `bd2122cb` | Web animation | Visible only | Unrelated | Exclude |
| hyperframes | same package/revision | Motion-video workflow | Visible only | Unrelated | Exclude |
| hyperframes-cli | same package/revision | Hyperframes CLI | Visible only | Unrelated | Exclude |
| hyperframes-registry | same package/revision | Hyperframes registry | Visible only | Unrelated | Exclude |
| website-to-hyperframes | same package/revision | Convert website to Hyperframes | Visible only | Unrelated | Exclude |

Historical cache versions explicitly observed for primary-runtime Skills include `26.805.11740`, `26.812.11052`, and later `26.819.11345`. They are environment-owned, mutable caches and must not be copied into this repository.

## Current `puzi_project` project-local Skills

These are all `SKILL.md` files under `.agents/skills` and `.zcode/skills` on the audit date. Except for `orchestral-score-rebuild`, they were created/installed after the historical successful run and cannot be credited for it.

| Skill | Path | Purpose | Invocation evidence | Classification | Open-source treatment |
|---|---|---|---|---|---|
| orchestral-score-rebuild | `.agents/skills/orchestral-score-rebuild/SKILL.md` | Historical printed-score workflow | Historical Codex: invoked; later ZCode: one smoke invocation | **RUNTIME REQUIRED for historical path** | Track and document |
| score-reconstruction-v2 | `.zcode/skills/score-reconstruction/SKILL.md` | Newer ScoreIR-first OMR workflow | Enabled/current; no historical evidence | Current runtime option, not historical dependency | Track only if V0.1 adopts it |
| musicxml-qa | `.zcode/skills/musicxml-qa/SKILL.md` | Deterministic MusicXML QA | Current profile; no historical evidence; currently untracked | Current runtime option | Track or remove from required profile before freeze |
| score-export | `.zcode/skills/score-export/SKILL.md` | Score/part export | Current profile; no historical evidence; currently untracked | Current runtime option | Track or remove from required profile before freeze |
| omr-benchmark | `.zcode/skills/omr-benchmark/SKILL.md` | OMR benchmarking | No historical evidence | Development/benchmark | Optional |
| score-generate | `.zcode/skills/score-generate/SKILL.md` | Score generation | No historical evidence | Unrelated to reconstruction runtime | Optional |
| brainstorming | `.zcode/skills/brainstorming/SKILL.md` | Requirement discovery | No historical evidence | Development only | Optional |
| executing-plans | `.zcode/skills/executing-plans/SKILL.md` | Plan execution discipline | No historical evidence | Development only | Optional |
| frontend-design | `.zcode/skills/frontend-design/SKILL.md` | Frontend design | No historical evidence | Unrelated | Exclude from runtime |
| mcp-builder | `.zcode/skills/mcp-builder/SKILL.md` | MCP development | No historical evidence | Development only | Optional |
| receiving-code-review | `.zcode/skills/receiving-code-review/SKILL.md` | Review handling | No historical evidence | Development only | Optional |
| requesting-code-review | `.zcode/skills/requesting-code-review/SKILL.md` | Request reviews | No historical evidence | Development only | Optional |
| skill-creator | `.zcode/skills/skill-creator/SKILL.md` | Skill authoring | No historical ZCode invocation | Development only | Optional |
| systematic-debugging | `.zcode/skills/systematic-debugging/SKILL.md` | Debugging discipline | No historical evidence | Development only | Optional |
| test-driven-development | `.zcode/skills/test-driven-development/SKILL.md` | TDD workflow | No historical evidence | Development only | Optional |
| verification-before-completion | `.zcode/skills/verification-before-completion/SKILL.md` | Completion verification | No historical evidence | Development only | Optional |
| webapp-testing | `.zcode/skills/webapp-testing/SKILL.md` | Web testing | No historical evidence | Unrelated | Exclude from score runtime |
| writing-plans | `.zcode/skills/writing-plans/SKILL.md` | Planning documents | No historical evidence | Development only | Optional |

Current `.zcode/config.json` enables `OMR_FULL`, `DEV_SAFE`, and `DEV_COMPLEX`. `OMR_FULL` names `score-reconstruction-v2`, `musicxml-qa`, `orchestral-score-rebuild`, and `score-export`. This is a current configuration dependency, not proof of historical use. It also conflicts with the root `AGENTS.md` statement that the default OMR profile contains only `score-reconstruction-v2`.

## Vendored/source-checkout Skill trees under `.tools`

These source checkouts were added after the historical run. They are inventory items, not demonstrated production dependencies.

### `.tools/anthropic-skills-src/skills-main/skills`

| Skill/source folder | Purpose class | Invocation | Classification |
|---|---|---|---|
| algorithmic-art | visual generation | none | unrelated |
| brand-guidelines | brand design | none | unrelated |
| canvas-design | visual design | none | unrelated |
| claude-academy-guide | platform guidance | none | development only |
| claude-api | API development | none | development only |
| discernment-nudge | agent guidance | none | development only |
| doc-coauthoring | documents | none | unrelated |
| docx | Word documents | none | unrelated |
| frontend-design | frontend design | none | unrelated |
| internal-comms | business writing | none | unrelated |
| mcp-builder | MCP development | none | development only |
| pdf | general PDF work | none | optional convenience, not historical |
| pptx | presentations | none | unrelated |
| skill-creator | Skill authoring | none in successful run | development only |
| slack-gif-creator | GIF generation | none | unrelated |
| theme-factory | styling/themes | none | unrelated |
| web-artifacts-builder | web artifacts | none | unrelated |
| webapp-testing | web testing | none | unrelated |
| xlsx | spreadsheets | none | unrelated |
| template | source template `SKILL.md` | none | development source, not a runtime Skill |

Each path is `<REPOSITORY_ROOT>/.tools/anthropic-skills-src/skills-main/skills/<folder>/SKILL.md`, except template at `<REPOSITORY_ROOT>/.tools/anthropic-skills-src/skills-main/template/SKILL.md`.

### `.tools/superpowers-src/superpowers-main/skills`

| Skill | Invocation | Classification |
|---|---|---|
| brainstorming | none | development only |
| dispatching-parallel-agents | none | development only |
| executing-plans | none | development only |
| finishing-a-development-branch | none | development only |
| receiving-code-review | none | development only |
| requesting-code-review | none | development only |
| subagent-driven-development | none | development only |
| systematic-debugging | none | development only |
| test-driven-development | none | development only |
| using-git-worktrees | none | development only |
| using-superpowers | none | development only |
| verification-before-completion | none | development only |
| writing-plans | none | development only |
| writing-skills | none | development only |

Each path is `<REPOSITORY_ROOT>/.tools/superpowers-src/superpowers-main/skills/<name>/SKILL.md`.

## Current user/global Skills

`<USER_HOME>/.agents/skills` is empty on the audit date. Current `<CODEX_HOME>/skills` contains `imagegen`, `openai-docs`, `plugin-creator`, `review-agent`, `skill-creator`, `skill-installer`, `open-design`, and `video-spec-builder`. None is required for historical score execution; `skill-creator` remains development-only. User/global Skill installation is mutable external state, so runtime reproduction must rely on the tracked project-local orchestral Skill.

The earlier 2026-08-23 ZCode audit recorded `<USER_HOME>/.agents/skills/open-design` as a symlink to the Codex user Skill; it is absent in the current scan and had no invocation evidence. The current ZCode plugin cache contains 15 additional Skills, exhaustively listed in SKILL_INVENTORY_ZCODE_PLUGIN_CACHE.md; all are development-only, optional, or unrelated to the historical score run.

## Required conclusion

- Historical runtime Skill dependency: **`orchestral-score-rebuild` only**.
- Historical development dependency: **`skill-creator` only**, used to author the runtime Skill.
- No separate PDF, MuseScore, MusicXML, OMR, or QA Skill was historically invoked.
- Current `OMR_FULL` adds newer Skills that must be tracked and versioned if V0.1 intends to require that profile.
