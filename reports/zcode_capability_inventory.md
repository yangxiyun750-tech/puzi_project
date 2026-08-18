# ZCode Capability Inventory

**Project**: `D:\puzi_project`  
**Date**: 2026-08-18  
**Phase**: AI Score Toolkit / ZCode Capability Integration Phase 1  
**Status**: Audit complete; GitHub MCP installed, awaiting `GITHUB_TOKEN`

---

## A. Environment Audit

### A.1 Host Environment

| Item | Value |
|---|---|
| OS | Windows 10 (win32 10.0.26200 x64) |
| Shell | Git Bash |
| Python | 3.12.10 |
| pip | 25.0.1 |
| Node.js | v24.14.1 |
| npm | 11.11.0 |
| npx | 11.11.0 |
| Git | 2.53.0.windows.2 |
| `uv` | missing |
| `gh` CLI | missing |
| `ffmpeg` / `ffprobe` | missing |
| `pdftoppm` (Poppler) | missing |

### A.2 Python Environment

**Installed packages (site-packages)**:

| Package | Version | License | Purpose |
|---|---|---|---|
| lxml | 6.1.1 | BSD-3-Clause | XML/MusicXML parsing |
| numpy | 2.5.2 | BSD-3-Clause | Numerical ops |
| pillow | 12.3.0 | HPND | Image processing |
| pypdf | 6.16.0 | BSD-3-Clause | PDF text/page ops |
| music21 | 10.5.0 | BSD-3-Clause | Music analysis / parse |
| partitura | 1.9.0 | MIT | Music representation / parse |
| musicdiff | 5.2 | unknown | Score diff |
| matplotlib | 3.11.1 | PSF-based | Plotting (music21 dep) |
| scipy | 1.18.0 | BSD-3-Clause | Numerical (partitura dep) |
| requests | 2.34.2 | Apache-2.0 | HTTP (music21 dep) |
| pip | 25.0.1 | MIT | Package management |

**Notable missing packages**: opencv-python, pytesseract, verovio, oemer, homr, etc.

### A.3 Project Layout

```text
D:\puzi_project
├── .agents/skills/orchestral-score-rebuild/   # legacy score skill
├── .zcode/                                     # ZCode workspace config
│   ├── config.json                             # MCP templates + skill profiles
│   └── skills/score-reconstruction/            # project score skill (V2)
├── .zcode-plugin/                              # AI Score Toolkit plugin manifest
├── docs/                                       # project docs
├── frontend/                                   # placeholder (only __init__.py)
├── licensing/                                  # third-party license notes
├── logs/                                       # runtime logs
├── outputs/                                    # build outputs
├── reports/                                    # benchmark / QA reports
├── rules/                                      # placeholder rule module
├── src/
│   ├── ai/                                     # frozen Intent Parser V1.1
│   ├── omr_normalization/                      # OMR quality gate
│   ├── qa/                                     # QA modules
│   ├── reconstruction/                         # reconstruction pipeline
│   ├── rendering/                              # rendering modules
│   └── score_engine/                           # ScoreIR + transposition engine
├── tests/                                      # 302 tests (2 skipped)
├── web_api/                                    # placeholder web API module
└── ...project PDFs and build artifacts
```

### A.4 Dependency Manifest Files

| File | Status | Notes |
|---|---|---|
| `requirements.txt` | created | music21, partitura, musicdiff + existing deps |
| `pyproject.toml` | missing | Optional for later |
| `Pipfile` | missing | — |
| `package.json` | missing | Frontend is placeholder only |
| `AGENTS.md` (workspace) | created | Project instructions incl. frozen components |
| `~/.zcode/AGENTS.md` (user) | missing | Optional user defaults |

### A.5 ZCode Configuration

**User scope (`~/.zcode/`)**:

| Resource | Path | Status |
|---|---|---|
| User config | `~/.zcode/cli/config.json` | missing (not created yet) |
| User skills | `~/.zcode/skills/` | missing |
| User skills (compat) | `~/.agents/skills/` | missing |
| User commands | `~/.zcode/commands/` | missing |
| User commands (compat) | `~/.agents/commands/` | missing |
| User AGENTS.md | `~/.zcode/AGENTS.md` | missing |

**Workspace scope (`D:\puzi_project\.zcode/`)**:

| Resource | Path | Status |
|---|---|---|
| Workspace config | `.zcode/config.json` | created |
| Workspace skills | `.zcode/skills/` | exists: `score-reconstruction` |
| Workspace skills (compat) | `.agents/skills/` | exists: `orchestral-score-rebuild` |
| Workspace commands | `.zcode/commands/` | missing |
| Workspace AGENTS.md | `AGENTS.md` | created |

**Built-in plugin cache (`~/.zcode/cli/plugins/cache/zcode-plugins-official/`)**:

| Plugin | Version | Skills Included |
|---|---|---|
| android-emulator | — | — |
| browser-use | 0.2.1 | `control-browser`, `web-gui-tester` |
| document-skills | 0.1.0 | `docx`, `pdf`, `pptx` |
| ios-simulator | — | — |
| restore-legacy-sessions | — | — |
| skill-creator | 0.1.0 | `skill-creator` |
| zcode-guide | 0.1.0 | `diagnosing-commands`, `diagnosing-hooks`, `diagnosing-mcp`, `diagnosing-plugins`, `diagnosing-skills`, `zcode-configuration-guide` |

---

## B. Skills Inventory

### B.1 Already Present / Detected

| Skill | Path | Version | License | Source | Status | Notes |
|---|---|---|---|---|---|---|
| `orchestral-score-rebuild` | `.agents/skills/orchestral-score-rebuild/` | — | Project custom | Legacy Codex/Claude skill | **present, legacy** | Older full-score rebuild workflow; references Audiveris + MuseScore |
| `score-reconstruction-v2` | `skills/score-reconstruction/` | — | Project custom | Current project skill | **present, canonical** | Updated V2 workflow using ScoreIR; supersedes `orchestral-score-rebuild` |

### B.2 Requested Skills — Assessment

Legend:
- **Integration type**: `skill` / `MCP` / `Python library` / `CLI` / `app plugin`
- **Scope**: `user` / `workspace` / `global` / `project`
- **Enabled by default recommendation**: `yes` / `no` / `profile-only`

#### Anthropic Skills

| Skill | Status | Version | Source | License | Integration | Conflicts | Credential | Vendor-safe | Scope | Default |
|---|---|---|---|---|---|---|---|---|---|---|
| `skill-creator` | installed (builtin) | 0.1.0 | ZCode official plugin cache | plugin TOS | skill | None | None | yes | user/global | yes (on demand) |
| `mcp-builder` | **missing** | — | Anthropic skill library (not in ZCode cache) | unknown | skill | — | None | unknown | user | no |
| `webapp-testing` | **missing** | — | Anthropic skill library | unknown | skill | Browser Use plugin already provides browser automation | None | unknown | user | no |
| `frontend-design` | **missing** | — | Anthropic skill library | unknown | skill | — | None | unknown | user | no |
| `pdf` | installed (builtin) | 0.1.0 | ZCode official plugin cache | plugin TOS | skill | None | None | yes | user/global | no (local-use only, verify license) |

**Decision**: `skill-creator` and `pdf` are already available via the built-in ZCode plugin cache. The other Anthropic skills (`mcp-builder`, `webapp-testing`, `frontend-design`) are **not present in the ZCode marketplace/cache** and their external source/license could not be verified in this phase. They are **deferred** pending manual install from a trusted source.

#### Superpowers Skills

| Skill | Status | Version | Source | License | Integration | Conflicts | Credential | Vendor-safe | Scope | Default |
|---|---|---|---|---|---|---|---|---|---|---|
| `systematic-debugging` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `test-driven-development` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `verification-before-completion` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `brainstorming` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `writing-plans` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `executing-plans` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `requesting-code-review` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `receiving-code-review` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `using-git-worktrees` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `finishing-a-development-branch` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |
| `subagent-driven-development` | **missing** | — | Anthropic / community | unknown | skill | — | None | unknown | user | no |

**Decision**: All Superpowers skills are **deferred**. They are not in the ZCode built-in cache and no verified install URL was provided. They can be added later from a trusted marketplace or GitHub repo after license/owner review.

#### Music Skills

| Skill | Status | Version | Source | License | Integration | Conflicts | Credential | Vendor-safe | Scope | Default |
|---|---|---|---|---|---|---|---|---|---|---|
| `mcp-score` score-generate | **missing** | — | External / Melogen | unknown | skill/MCP | — | Melogen API key | unknown | user/project | no |

**Decision**: `mcp-score` is **deferred** until a verified source and credential are available.

#### Project Custom Skills

| Skill | Status | Version | Source | License | Integration | Conflicts | Credential | Vendor-safe | Scope | Default |
|---|---|---|---|---|---|---|---|---|---|---|
| `score-reconstruction-v2` | present | — | project custom | project | skill | orchestral-score-rebuild (legacy) | None | yes | workspace | yes (OMR profile) |
| `omr-benchmark` | **missing** | — | to be created | project | skill | None | None | yes | workspace | no |
| `musicxml-qa` | **missing** | — | to be created | project | skill | None | None | yes | workspace | no |
| `score-export` | **missing** | — | to be created | project | skill | None | None | yes | workspace | no |

**Decision**: `score-reconstruction-v2` is the canonical score skill. `orchestral-score-rebuild` is kept as legacy reference but should be considered deprecated. The remaining custom skills are **not created in this phase** per instruction not to start new feature development.

---

## C. MCP Inventory

### C.1 Current MCP Configuration

| Scope | Config File | Servers | Status |
|---|---|---|---|
| User | `~/.zcode/cli/config.json` | missing | no MCP servers |
| Workspace | `.zcode/config.json` | created | 9 templates, GitHub installed but disabled |
| Fallback user | `~/.agents/mcp.json` | missing | no MCP servers |
| Fallback workspace | `.agents/mcp.json` | missing | no MCP servers |

### C.2 Requested MCPs — Assessment

| MCP | Status | Version | Source | License | Integration | Conflicts | Credential | Scope | Default |
|---|---|---|---|---|---|---|---|---|---|
| `mcp-score` | **missing** | — | Melogen / external | unknown | MCP | — | Melogen API key | project | no |
| `Melogen MCP` | **missing** | — | Melogen / external | unknown | MCP | — | Melogen API key | project | WAITING_FOR_CREDENTIAL |
| `GitHub official MCP` | installed | 1.9.0 | GitHub (`github/github-mcp-server` release binary) | MIT | MCP | — | `GITHUB_PERSONAL_ACCESS_TOKEN` (env) | project | no |
| `Microsoft Playwright MCP` | **missing** | — | Microsoft (`microsoft/playwright-mcp`) | Apache-2.0 | MCP | Browser Use skill/plugin provides overlapping browser automation | None (local browser) | user | no |
| `zai-mcp-server` | **missing** | — | Z.ai | unknown | MCP | — | Z.ai API key | user | no |
| `web-search-prime` | **missing** | — | ZCode marketplace / third party | unknown | MCP | — | API key likely | user | no |
| `web-reader` | **missing** | — | ZCode marketplace / third party | unknown | MCP | — | API key likely | user | no |
| `mcp-musescore` | **missing** | — | community | unknown | MCP | MuseScore CLI already available | None / local | project | disabled |
| `dorico-mcp-server` | **missing** | — | community / Steinberg | proprietary | MCP | — | Dorico license | project | disabled |

**Decision**: `github` MCP is **installed** (package `@modelcontextprotocol/server-github@2025.4.8`) and configured in `.zcode/config.json`, but remains disabled until `GITHUB_TOKEN` is set. All other requested MCPs remain **deferred or template-only** in this phase. Templates are in `.zcode/config.json` (workspace scope) with credentials sourced from environment variables. No credentials are written to the repository.

---

## D. OMR Provider Toolchain Inventory

| Tool | Status | Version | Path / Source | License | Integration | Notes |
|---|---|---|---|---|---|---|
| Audiveris | installed | 5.11.0 (per licensing/README) | `C:\Program Files\Audiveris\Audiveris.exe` | AGPL-3.0 | CLI | **License review required** before commercial use / distribution |
| Melogen | **missing** | — | external | unknown | API / MCP | WAITING_FOR_CREDENTIAL |
| PDF2Muse | **missing** | — | external | unknown | CLI / API | not evaluated |
| oemer | **missing** | — | external | unknown | Python | not evaluated |
| homr | **missing** | — | external | unknown | Python | **experimental only**, AGPL review required |

**Provider capability manifest**: see Section H (Score Engine / QA Toolchain) for the unified manifest.

---

## E. Score Engine / QA Toolchain Inventory

| Tool | Status | Version | Source | License | Integration | Notes |
|---|---|---|---|---|---|---|
| music21 | installed | 10.5.0 | pip (`music21`) | BSD-3-Clause | Python library | smoke-tested |
| partitura | installed | 1.9.0 | pip (`partitura`) | MIT | Python library | smoke-tested |
| musicdiff | installed | 5.2 | pip (`musicdiff`) | unknown | Python library | smoke-tested; license verify before commercial use |
| MuseScore CLI | installed | 4.7.4 | `C:\Program Files\MuseScore 4` | GPL-3.0 | CLI | external tool, not linked |
| Verovio | **missing** | — | npm / pip | LGPL | CLI / JS | optional QA, deferred |
| Poppler `pdftoppm` | **missing** | — | system / MSYS2 | GPL-2.0 | CLI | required by legacy skill; not in PATH |

---

## F. Future Frontend Dependencies

| Dependency | Status | Notes |
|---|---|---|
| OpenSheetMusicDisplay | **missing** | Recorded only; no frontend development this phase |

---

## G. ZCode Plugin Structure — Design

**Proposed project-level plugin**: `AI Score Toolkit`

**Goal**: Manage project skills, commands, MCP, and subagents from a single plugin.

**Structure (not created yet)**:

```text
.zcode-plugin/
└── plugin.json
    ├── name: ai-score-toolkit
    ├── skills: ["../skills/score-reconstruction"]
    ├── commands: ["../commands"]
    ├── mcpServers: ["../mcp"]
    └── agents: ["../agents"]
```

**Constraint**: No third-party source-available or proprietary skill source code is copied into the plugin. Each third-party capability is referenced by:
- source URL
- license
- version
- install method

---

## H. Skill Enable Profiles

**Profiles designed (not all skills are installed yet)**:

### CORE_DEV
Enabled:
- `systematic-debugging` (deferred)
- `test-driven-development` (deferred)
- `verification-before-completion` (deferred)
- `writing-plans` (deferred)

### OMR
Enabled:
- `score-reconstruction-v2` (present)
- `omr-benchmark` (deferred)
- `musicxml-qa` (deferred)

### SCORE_EDIT
Enabled:
- `score-generate` (deferred)
- `score-export` (deferred)

### FRONTEND
Enabled:
- `frontend-design` (deferred)
- `webapp-testing` (deferred)

**Default policy**: Only `score-reconstruction-v2` is enabled for the OMR profile. All other skills remain disabled until manually installed and assigned to a profile.

---

## I. Security Summary

**Not done in this phase**:
- No modification to Intent Parser V1.1
- No modification to resolver
- No modification to transpose engine
- No deletion of current OMR
- No automatic selection of Melogen as primary provider
- No API keys written to files or reports
- No unknown third-party install scripts executed
- No project source overwritten by skill installation
- Not all skills enabled simultaneously

**Credential handling**:
- All credentials must use environment variables or ZCode secret configuration.
- No secrets committed to the repository.
- Melogen credential: template created, marked `WAITING_FOR_CREDENTIAL`.

---

## J. License Review Items

| Item | License | Status |
|---|---|---|
| Audiveris | AGPL-3.0 | review required; noted in `licensing/README.md` |
| homr | AGPL (likely) | review required if adopted |
| MuseScore | GPL-3.0 | external CLI, acceptable as separate process |
| Poppler | GPL-2.0 | external CLI, acceptable as separate process |
| music21 | BSD-3-Clause | permissive |
| partitura | MIT | permissive |
| musicdiff | unknown | verify before commercial use |

**No commercial license conclusion is made in this phase.**

---

## K. Phase 1 Integration Results

### K.1 Installed / Registered Skills

| Skill | Location | Action | Status |
|---|---|---|---|
| `score-reconstruction-v2` | `.zcode/skills/score-reconstruction/` | Migrated from `skills/score-reconstruction/` to workspace `.zcode/skills/` for ZCode discovery | enabled (OMR profile) |
| `orchestral-score-rebuild` | `.agents/skills/orchestral-score-rebuild/` | Kept as legacy reference, marked deprecated | not enabled |

**Skills deferred** (not in ZCode cache / source not verified):
- All Anthropic skills except `skill-creator` and `pdf` (already builtin)
- All Superpowers skills
- `mcp-score` / Melogen MCP
- `omr-benchmark`, `musicxml-qa`, `score-export`

### K.2 Installed / Registered MCPs

| MCP | Config Location | Status |
|---|---|---|
| `mcp-score` | `.zcode/config.json` | template, disabled, `WAITING_FOR_CREDENTIAL` |
| `melogen-mcp` | `.zcode/config.json` | template, disabled, `WAITING_FOR_CREDENTIAL` |
| `github` | `.zcode/config.json` | installed (v1.9.0 binary), disabled until `GITHUB_PERSONAL_ACCESS_TOKEN` set |
| `playwright` | `.zcode/config.json` | template, disabled |
| `zai-mcp-server` | `.zcode/config.json` | template, disabled |
| `web-search-prime` | `.zcode/config.json` | template, disabled |
| `web-reader` | `.zcode/config.json` | template, disabled |
| `mcp-musescore` | `.zcode/config.json` | template, disabled by default |
| `dorico-mcp-server` | `.zcode/config.json` | template, disabled by default |

All MCP credentials reference environment variables. No secrets written to repository.

### K.3 Installed Python / CLI Tools

| Tool | Version | Install Method |
|---|---|---|
| music21 | 10.5.0 | `pip install music21` |
| partitura | 1.9.0 | `pip install partitura` |
| musicdiff | 5.2 | `pip install musicdiff` |
| matplotlib | 3.11.1 | dependency of music21 |
| scipy | 1.18.0 | dependency of partitura |
| requests | 2.34.2 | dependency of music21 |

Existing CLI tools confirmed:
- MuseScore Studio 4.7.4 at `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`
- Audiveris 5.11.0 at `C:\Program Files\Audiveris\Audiveris.exe`

Still missing:
- `pdftoppm` (Poppler)
- `ffmpeg` / `ffprobe`
- `uv`
- `gh` CLI

### K.4 Skipped / Rejected Items + Reasons

| Item | Reason |
|---|---|
| Anthropic `mcp-builder`, `webapp-testing`, `frontend-design` | Not present in ZCode built-in cache; external source/license not verified |
| All Superpowers skills | Not present in ZCode cache; no verified install URL provided |
| `mcp-score` / Melogen MCP activation | No `MELOGEN_API_KEY` available; template only |
| `zai-mcp-server`, `web-search-prime`, `web-reader` | No verified install source/credentials; template only |
| `mcp-musescore`, `dorico-mcp-server` | Optional/default disabled per instruction |
| `pdf` skill active use | Local-use only; license check recommended before commercial use |
| `Verovio` | Optional; deferred |
| `OpenSheetMusicDisplay` | Frontend dependency; recorded only |
| `oemer`, `PDF2Muse`, `homr` | Not evaluated; external source/license not verified |

### K.5 Credential-Required Items

| Item | Credential | Status |
|---|---|---|
| Melogen MCPs | `MELOGEN_API_KEY` | `WAITING_FOR_CREDENTIAL` |
| GitHub MCP | `GITHUB_PERSONAL_ACCESS_TOKEN` | installed, disabled until credential set (read-only, toolsets=repos,issues,pull_requests) |
| zai-mcp-server | `ZAI_API_KEY` | template only |
| web-search-prime | `WEB_SEARCH_PRIME_API_KEY` | template only |
| web-reader | `WEB_READER_API_KEY` | template only |
| Dorico MCP | `DORICO_LICENSE` | template only |

### K.6 License-Review Items

| Item | License | Status |
|---|---|---|
| Audiveris | AGPL-3.0 | review required before commercial use |
| homr | AGPL (likely) | review required if adopted |
| musicdiff | unknown | verify before commercial use |

### K.7 Smoke Test Results

Script: `tests/smoke_test_toolchain.py`

| Test | Result |
|---|---|
| MusicXML generation | PASS |
| MusicXML → music21 parse | PASS (4 parts) |
| MusicXML → Partitura parse | PASS (4 parts) |
| MusicXML → MuseScore CLI render | PASS |
| MusicXML A/B → musicdiff | PASS (cost=24, ops=4) |

Artifacts were written to an isolated temp directory and left for inspection.

### K.7.5 GitHub MCP Health Check

Server: `D:\puzi_project\.tools\github-mcp-server\github-mcp-server.exe` (official release v1.9.0)

| Check | Result |
|---|---|
| Binary starts (`--version`) | PASS — `Version: 1.9.0`, commit `cdfa34e...` |
| stdio transport starts with `--read-only --toolsets=repos,issues,pull_requests` | PASS |
| `initialize` handshake | PASS |
| `tools/list` returns only read-only tools | PASS — 22 tools, no write/merge/delete tools |
| Enabled toolsets inferred from tools | `repos`, `issues`, `pull_requests` |
| No actual GitHub API write operations performed | PASS (used dummy token, no tool calls) |

> The server remains disabled in `.zcode/config.json` until `GITHUB_PERSONAL_ACCESS_TOKEN` is exported.

### K.8 ZCode Enabled Profile

**Active profile**: `OMR`
**Enabled skill**: `score-reconstruction-v2`
**All other skills**: disabled

### K.9 Files Changed / Created

| File | Action |
|---|---|
| `reports/zcode_capability_inventory.md` | created |
| `requirements.txt` | created |
| `.zcode/config.json` | created (MCP templates + skill profiles) |
| `.zcode-plugin/plugin.json` | created (AI Score Toolkit plugin manifest) |
| `.zcode/skills/score-reconstruction/SKILL.md` | migrated from `skills/score-reconstruction/` |
| `AGENTS.md` | created (workspace instructions) |
| `tests/smoke_test_toolchain.py` | created |
| `.tools/github-mcp-server/` | created (official GitHub MCP Server binary + checksums) |
| `.gitignore` | created (excludes `.tools/`, `*.zip`) |

No frozen components modified.

### K.10 Commands Executed

```bash
# Python toolchain install
python -m pip install music21 partitura musicdiff

# Smoke test
python tests/smoke_test_toolchain.py

# Full regression test
PYTHONPATH=src python -m unittest discover -s tests

# Synthetic benchmark
PYTHONPATH=src python run_nl_edit_benchmark_v1.py

# GitHub MCP migration
npm uninstall -g @modelcontextprotocol/server-github
curl -L -o .tools/github-mcp-server/github-mcp-server_Windows_x86_64.zip \
  https://github.com/github/github-mcp-server/releases/download/v1.9.0/github-mcp-server_Windows_x86_64.zip
# (SHA256 verified: 29e901869c639bb8e7e908496653d37a02d260761c64921fd83a4d9f4fd137f9)
python -m zipfile -e .tools/github-mcp-server/*.zip .tools/github-mcp-server/
.tools/github-mcp-server/github-mcp-server.exe --version
```

### K.11 Test Suite Status

- Full test suite: **302/302 OK** (2 skipped)
- Synthetic benchmark V1: **22/22 PASS**
- No regressions introduced by Phase 1 integration.

---

*Phase 1 complete. Awaiting approval before starting Phase 2.*
