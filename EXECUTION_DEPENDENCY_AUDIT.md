# Complete Execution-Dependency Audit — V0.1 Candidate

Audit date: 2026-08-25
Target repository/worktree: repository root (`.`)
Historical source workspace retained outside the public repository as: `<LEGACY_WORKSPACE>`
Decision: **V0.1 IS NOT FROZEN AND IS NOT READY TO FREEZE**

No score was opened, processed, transposed, or exported during this audit.

## Audit basis and confidence

The historical baseline is the successful multi-turn Codex workflow on 2026-08-12/13 through the Logic Pro delivery. Evidence was taken from the Codex JSONL session and auto-review logs, generated reports/artifacts, helper scripts, repository history, current configuration, executable invocation, Python import scans, and Git tracking state.

The relevant historical session recorded 405 shell calls, 71 patch calls, 59 image-view calls, 13 plan updates, 13 web lookups, and 2 workspace-dependency lookups. It recorded no MCP call. This supports a workflow driven by local executables/scripts plus reasoning/vision and human review—not by an undocumented MCP service.

## A. Skills

The exhaustive Skill list, paths, purposes, invocation evidence, and classifications are in `SKILL_INVENTORY.md`, `SKILL_INVENTORY_GLOBAL_CURRENT.md`, and `SKILL_INVENTORY_ZCODE_PLUGIN_CACHE.md`.

Key findings:

- `orchestral-score-rebuild` was the only demonstrated runtime Skill; its body was injected eight times in the successful historical task.
- system `skill-creator` was injected once to author/update that Skill and is development-only.
- The general PDF Skill was visible but not invoked. PDF operations came from Poppler, Python libraries, and direct tools.
- No historical separate MusicXML, MuseScore, OMR, or QA Skill was found or invoked.
- Current `.zcode/skills/musicxml-qa`, `score-export`, and `score-reconstruction-v2` postdate the successful run. They may be current runtime components, but cannot be retroactively credited for historical success.
- `.tools` Skill source trees also postdate the successful run and have no production invocation evidence.

## B. Agent and project instructions

| Instruction/configuration | Historical role | Current role | Reproducibility classification |
|---|---|---|---|
| `.agents/skills/orchestral-score-rebuild/SKILL.md` | Direct historical workflow instruction | Still project-local | **REQUIRED** |
| `references/qa-protocol.md` and `assets/QA_REPORT_TEMPLATE.md` | Referenced by the Skill; define page/measure/source/transposition/engraving QA | Still applicable | **REQUIRED** |
| successful user prompt sequence | Supplied environment gate, two-page prototype, exact instrumentation, lyric/Harp repair, persistence and Logic export steps | Previously hidden in conversation | **REQUIRED; now extracted to `references/successful-run-procedure.md` and QA** |
| root `AGENTS.md` | Did not exist during historical success | Postdates success; freezes current source files and declares profile behavior | Current project instruction; must be reconciled before freeze |
| `.zcode/config.json` | Did not drive historical Codex run | Enables `OMR_FULL`, `DEV_SAFE`, `DEV_COMPLEX` | Current ZCode runtime configuration |
| `.zcode-plugin/plugin.json` | Not historical | Registers ZCode Skills/commands/MCP/agents | Current packaging, not historical |
| `PUZI_PROJECT_HANDOFF.md` | Postdates historical success | Describes later auto-repair and provider conventions | Current development context |
| `docs/CURRENT_HANDOFF.md`, `docs/HANDOFF_CURRENT.md` | Postdate historical success | Describe current architecture/tests/env vars | Current development context |
| `reports/codex_parity_audit.md` | Retrospective evidence | States final result used Audiveris + scripted repairs + MuseScore/manual cleanup + human QA | Audit evidence, not runtime |
| `reports/codex_repair_logic_audit.md` | Retrospective evidence | Quantifies generic vs review-gated vs fixture/manual repair | Audit evidence, not runtime |
| `CLAUDE.md` | Not found in the audited project | none | Not a dependency |

Important conflict: current `AGENTS.md` says the default OMR profile contains only `score-reconstruction-v2`, while current `.zcode/config.json` enables `OMR_FULL` with four Skills. The freeze candidate has no single authoritative statement of the default execution path.

## C. MCP, connectors, plugins, and integrations

| Integration | Purpose | Configured now | Historical-use evidence | Classification |
|---|---|---:|---|---|
| MuseScore Studio CLI | Native score import/engraving/export | yes, executable | Extensive direct CLI/artifact evidence | **REQUIRED binary, not MCP** |
| Audiveris CLI | OMR | yes, executable | Direct CLI/artifact evidence | **REQUIRED binary** |
| Poppler `pdftoppm` | 400-DPI PDF rendering | yes, executable | Direct workflow evidence | **REQUIRED binary** |
| Codex `open-design` MCP | design artifacts | enabled in current Codex | no historical score call | unrelated |
| Codex `xcodebuildmcp` | Apple/Xcode tooling | enabled in current Codex | no historical score call | unrelated |
| ZCode `github` integration | repository access | enabled read-only | no historical score evidence | optional development integration |
| ZCode `mcp-score` | score integration | disabled | none | optional/unproven |
| ZCode `playwright` | browser testing | disabled | none | unrelated to historical score run |
| ZCode `zai-mcp-server` | model/vision integration | disabled | none | optional provider |
| ZCode `web-search` | web search | disabled | historical web research used direct web tool, not this MCP | optional documentation aid |
| ZCode `web-reader` | page reader | disabled | none | optional |
| ZCode `mcp-musescore` | MuseScore MCP | disabled | none; historical use was CLI | optional/unproven; not required |
| ZCode `dorico-mcp-server` | Dorico integration | disabled | none | unrelated |

Conclusion: no MCP, connector, plugin, or cloud service is a demonstrated dependency of the successful score conversion. Web lookups helped discover command usage, but the reproducible commands must be documented locally; web access is optional.

## D. Non-Skill execution dependencies

### Executables

| Component | Historical successful path/version | Current verification | Requirement |
|---|---|---|---|
| Audiveris | `C:\Program Files\Audiveris\Audiveris.exe`, 5.11.0 | CLI starts and reports 5.11.0 | **REQUIRED** |
| MuseScore Studio | `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`, 4.7.4 | CLI starts/reports 4.7.4 | **REQUIRED** |
| Poppler `pdftoppm` | `${PDFTOPPM_EXE}`, 26.05.0 | executable reports 26.05.0 | **REQUIRED**; clean users must install their own Poppler or set the documented override |
| Python | historical bundled path `...\dependencies\python\python.exe`, 3.12.13 | project/system Python 3.12.10; bundled path currently 3.12.13 | **REQUIRED**, support 3.12.x must be declared/tested |
| Java | Audiveris-bundled `C:\Program Files\Audiveris\runtime\bin\java.exe` | OpenJDK 25.0.3 current | **REQUIRED indirectly**, normally bundled by Audiveris installer |

Historical Audiveris processing included `-Dorg.audiveris.omr.sheet.BookManager.LoadStep.maxPixelCount=40000000` for large 400-DPI A3 pages. The current `src/omr/providers/audiveris_provider.py` instead renders with `pypdfium2` and does not implement that exact Poppler/Audiveris setting, so it is not an exact replacement for the proven path.

### Python imports and packages

Historical successful helper scripts directly imported only three non-stdlib packages:

| Package/import | Historical function | Current version evidence | Requirement |
|---|---|---|---|
| `pypdf` | PDF page/extraction helpers | bundled env 6.10.0; project venv 6.16.1 | **REQUIRED for affected scripts** |
| `pdfplumber` | PDF inspection/text helpers | bundled env 0.11.9; missing in project venv | **REQUIRED for historical helpers** |
| `PIL` / Pillow | image/reference processing | 12.3.0 in both inspected envs | **REQUIRED for affected scripts** |

Current source additionally imports:

| Package | Current observed version | Declared in `requirements.txt` | Status |
|---|---:|---:|---|
| `lxml` | 6.1.1 | yes | current runtime |
| `numpy` | project venv 2.5.2 | yes | current runtime |
| `music21` | 10.5.0 | yes | current runtime |
| `partitura` | 1.9.0 | yes | current runtime |
| `musicdiff` | 5.2 | yes | current runtime |
| `pypdfium2` | 5.13.0 | **no** | **OPEN_SOURCE_REPRODUCTION_GAP** |
| `PyMuPDF` / `fitz` | imported by current source; absent in inspected project venv | **no** | **OPEN_SOURCE_REPRODUCTION_GAP** |
| `pdfplumber` | required by retained historical helpers; missing from project venv | **no** | **OPEN_SOURCE_REPRODUCTION_GAP** |

The current XSD validation path also expects `third_party/musicxml_4_0/schema/`. That tree is currently untracked; its source, license, checksum, and install/fetch procedure must be recorded.

### Helper code

The historical workspace contains 33 Python scripts used or retained around the successful run, including playlist creation, MusicXML invariants, PDF/lyric mapping, full-score construction, final-production repairs, transposition, linked-part and Logic exports. These scripts are necessary evidence, but not all are general algorithms: retrospective audits estimate approximately 25–30% as safely generic, 30–35% as review-gated, and the remainder fixture-specific or manual/agent-mediated. Reproduction must preserve that distinction and must not market fixture-specific transforms as universal OMR repair.

## E. Model and human capability dependencies

The historical agent identifier was `gpt-5.6-sol`. The exact model name is evidence, not the portability contract.

| Capability contract | Used for | Requirement |
|---|---|---|
| `code_reasoning_provider` | Long-horizon planning, filesystem/CLI orchestration, script creation/repair, XML reasoning, interpreting validator output | **REQUIRED**; provider must support sufficiently long context and local tool execution/editing |
| `visual_review_provider` | Read source and MuseScore page images, locate visible OMR/engraving mismatches, review lyric alignment, Harp objects, parts, collisions | **REQUIRED capability** unless every visual stage is performed manually; image input is not assumed |
| deterministic validators | Counts, MusicXML invariants, hashes, executable checks, round-trip comparisons | **REQUIRED** but insufficient alone |
| `human_review_fallback` | Ambiguous pitch/rhythm/voice, instrument semantics, native-object correctness, professional engraving/page turns, final musical acceptance | **REQUIRED fallback and final authority** |

Current ZCode code uses `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`, and can send base64 images through an OpenAI-compatible client. A compatible endpoint must explicitly support the required image input; a text-only model cannot satisfy `visual_review_provider`.

## F. Successful conversation-derived procedure classification

Legend: `CODE`, `SKILL`, `PROJECT`, `CONVERSATION`, and `HUMAN` may all apply to one stage.

| Successful step | Classification before audit | Evidence/notes | Extraction result |
|---|---|---|---|
| Initial environment readiness check | CONVERSATION + deterministic shell | User required actual CLI start and stop-on-missing | Gate 0 in `successful-run-procedure.md`; QA gate table |
| Two-page OMR prototype | CONVERSATION + SKILL + CODE + HUMAN | Explicit pages 1–2 scope, `.omr`, MusicXML, MuseScore, visual acceptance | Gate 1 |
| Reject PDF/vector notehead shifting | SKILL + CONVERSATION | Repeated core rule | Retained in Skill and Gate 1 |
| Audiveris → MusicXML → native MuseScore | SKILL + CODE | Skill commands, playlist and invariant scripts, artifacts | Retained |
| Generic Voice → real instrument mapping | CONVERSATION + fixture CODE + HUMAN | OMR staves were corrected after prototype | Gate 2 |
| B-flat Clarinet definition | CONVERSATION + fixture CODE + HUMAN | Required real MuseScore transposition metadata | Gate 2 and instrument QA |
| Horn in F definitions | CONVERSATION + fixture CODE + HUMAN | Same | Gate 2 and instrument QA |
| Harp definition/grand staff | CONVERSATION + fixture CODE + HUMAN | Same | Gate 2 |
| Solo Voice definition | CONVERSATION + fixture CODE + HUMAN | Same | Gate 2 |
| Full-score reconstruction | SKILL + CONVERSATION + CODE + HUMAN | Pages 1–8 primary, legacy parts secondary | Gate 3 |
| Original PDF visual comparison | SKILL + visual provider + HUMAN | 59 historical image-view calls | Gates 1, 3, 4, 7 |
| Chinese Lyrics restoration | CONVERSATION + `map_pdf_lyrics_to_voice.py`/production scripts + visual/HUMAN | Native lyric objects were required | Gate 4 and QA native-object check |
| Harp arpeggio restoration | CONVERSATION + production scripts + visual/HUMAN | Native Arpeggio objects required | Gate 4 and QA |
| Harp glissando restoration | CONVERSATION + production scripts + visual/HUMAN | Native Glissando anchors required | Gate 4 and QA |
| Special notation repair | CONVERSATION + scripts + visual/HUMAN | Mix of deterministic, review-gated, and manual fixes | Gate 4; guessing prohibited |
| Final concert-key transposition | SKILL + CODE/MuseScore + HUMAN | Concert pitch verified before transposition | Gates 5–6 |
| Written/concert-pitch validation | SKILL + validators + HUMAN | Clarinet/Horn spot checks and invariant audit | Gate 6 |
| Linked-part generation | SKILL + scripts/MuseScore + HUMAN | Fresh linked parts from master | Gate 7 |
| Part layout | SKILL + MuseScore + visual/HUMAN | Practical page turns/collisions | Gate 7 |
| Save → close → reopen part validation | CONVERSATION + HUMAN/tool check | Required proof of persistence, not just in-memory state | Gate 8 and QA |
| MusicXML round-trip validation | CONVERSATION + CODE/MuseScore | Reopen exports and compare | Gate 9 and QA |
| Logic-compatible full-score/part MusicXML | CONVERSATION + export scripts + MuseScore | Linked relationship not portable; PDFs supplied | Gate 9 |

All identified conversation-only requirements are now represented in the staged Skill reference and QA additions. They still need to be tracked in Git with the rest of this audit.

## G/H. Reproducibility and clean-machine answer

- Dependency graph: `REPRODUCIBILITY_GRAPH.md`
- Exact clean-machine checklist: `CLEAN_MACHINE_REPRODUCTION.md`

## I. Freeze decision and open gaps

**FREEZE_STATUS = NOT READY**

The audit categories are complete, and conversation-only procedures have been extracted, but the worktree cannot yet be declared a reproducible V0.1 baseline because:

1. `origin/main` contains only the initial commit. The pre-audit worktree snapshot had 14 tracked modifications and 21,182 untracked files; these audit changes bring the observed counts to 15 tracked modifications and 21,190 untracked files until they are reviewed and committed.
2. Critical current runtime files are untracked, including `musicxml-qa`, `score-export`, current Audiveris provider, semantic review/release gates, handoff, and MusicXML XSD material.
3. `requirements.txt` omits `pypdfium2`, `pdfplumber`, and PyMuPDF despite current/historical imports.
4. The exact supported Python version and reproducible lock/checksum strategy are not declared.
5. MusicXML 4.0 XSD provenance/license/install mechanism is incomplete.
6. `AGENTS.md` and `.zcode/config.json` disagree about the default Skill profile.
7. Several current files described as frozen by `AGENTS.md` are modified in the worktree.
8. Exact executable discovery/configuration for a clean machine is not yet implemented as a repository-owned environment doctor.
9. Model capability/provider configuration is not yet tested as a clean-machine acceptance gate.

Every item above is an **OPEN_SOURCE_REPRODUCTION_GAP**. No commit, tag, release, or freeze was created by this audit.
