# Clean Windows Machine Reproduction Checklist

Audit date: 2026-08-25
Answer to the required question: **A clone alone is not sufficient today.**

If a new user clones only the proposed open-source repository onto a clean Windows machine, the following exact additional software, capabilities, configuration, and human input are required to reproduce the successful workflow.

## 1. Clone and repository state

- Clone the future frozen/tagged repository, not the current `origin/main` as it exists on the audit date.
- Confirm these tracked resources exist:
  - `.agents/skills/focused-score-rebuild/SKILL.md`
  - `.agents/skills/focused-score-rebuild/references/qa-protocol.md`
  - `.agents/skills/focused-score-rebuild/references/successful-run-procedure.md`
  - `.agents/skills/focused-score-rebuild/assets/QA_REPORT_TEMPLATE.md`
  - all referenced Skill/helper/QA scripts
  - a complete Python requirements lock
  - MusicXML schema provenance/fetch instructions or legally redistributable schema files
- Do not assume anything under the original developer's `<USER_HOME>/.codex`, `<LEGACY_WORKSPACE>`, tool cache, or virtual environments exists.

**Current result:** fail. `origin/main` lacks critical current files and differs from the audited worktree.

## 2. Required Windows software

Install and verify:

1. **Python 3.12.x**. Historical success used 3.12.13; the current project venv uses 3.12.10. Pin and test the supported patch range before freeze.
2. **Poppler for Windows** providing `pdftoppm.exe`. Historical success used 26.05.0. The executable must support 400-DPI PNG rendering.
3. **Audiveris 5.11.0** from the official Windows installer. Verify the real CLI can start; retain its bundled Java runtime. Large 400-DPI A3 input may require `org.audiveris.omr.sheet.BookManager.LoadStep.maxPixelCount=40000000`.
4. **MuseScore Studio 4.7.4** (or a tested compatible 4.x release) providing `MuseScore4.exe`. CLI import/export and GUI/manual review are both needed.
5. A PDF/PNG viewer is useful for manual side-by-side review; it is not a hidden programmatic dependency.
6. **Logic Pro** is optional and only required to consume the downstream delivery on macOS; it is not required to reconstruct the MuseScore master.

MuseScore and Audiveris have their own licenses/redistribution terms and installation footprints. The repository should document official installation rather than bundle proprietary/third-party installers without permission. Poppler and MusicXML schema distribution must include compatible license notices.

## 3. Required executable configuration

The future environment doctor must discover paths or accept explicit configuration. Do not hard-code the original machine's paths.

Recommended configuration names:

```text
PYTHON_EXE
PDFTOPPM_EXE
AUDIVERIS_EXE
MUSESCORE_EXE
```

The current project already uses `MUSESCORE_EXE` in tests. The other names are a reproducibility recommendation, not yet a frozen interface.

Readiness must execute each binary and record path/version/result. File existence, a Start-menu shortcut, documentation, or generated scripts are not sufficient.

## 4. Required Python packages

For the historical scripts:

```text
pypdf
pdfplumber
Pillow
```

For current `puzi_project` source in addition to the above:

```text
lxml
numpy
music21
partitura
musicdiff
pypdfium2
PyMuPDF
```

Current observed versions are documented in `EXECUTION_DEPENDENCY_AUDIT.md`. Install from a committed lock/constraints file once one exists; do not use mutable developer virtual environments as the specification.

**OPEN_SOURCE_REPRODUCTION_GAP:** `requirements.txt` currently omits `pdfplumber`, `pypdfium2`, and PyMuPDF even though retained/current code imports them. Exact hashes and a tested clean-environment install are also absent.

## 5. Required Skill and project instructions

- Runtime: project-local `focused-score-rebuild` and its referenced procedure/QA resources.
- Development-only: `skill-creator` if maintainers want to edit the Skill; it is not needed to run an already tracked Skill.
- No user-global Skill is required.
- No separate PDF, MuseScore, MusicXML, OMR, or QA Skill was historically required.
- If V0.1 chooses current ZCode `OMR_FULL`, then `score-reconstruction-v2`, `musicxml-qa`, and `score-export` must also be tracked, documented, and included in clean-machine tests. Their current mere profile membership is not enough.

**OPEN_SOURCE_REPRODUCTION_GAP:** `AGENTS.md` and `.zcode/config.json` currently disagree about the default profile.

## 6. Required model/provider capabilities

Provide:

```text
code_reasoning_provider
visual_review_provider
human_review_fallback
```

- `code_reasoning_provider` must orchestrate local tools, read/write project files, reason over MusicXML and logs, and sustain the multi-stage repair loop.
- `visual_review_provider` must accept source/rendered page images and reason about notation/layout. Do not assume a text-only model has vision.
- One provider may satisfy both contracts, but the contracts remain separate from a model brand/name.
- `human_review_fallback` must be musically qualified and must decide unresolved pitches/rhythms/voices, transposition semantics, engraving/page turns, and final acceptance.

The historical provider was reported as `gpt-5.6-sol`; exact-provider parity is not required if capability acceptance tests pass.

For current ZCode's OpenAI-compatible client, configure secrets outside Git:

```text
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_SUPPORTS_TEMPERATURE   # optional provider compatibility flag
```

Never commit API keys. A local/offline provider may use different configuration if it satisfies the same capability contract.

**OPEN_SOURCE_REPRODUCTION_GAP:** no repository-owned clean-machine test currently proves image-input support, tool orchestration, or minimum reasoning behavior for a configured provider.

## 7. Optional integrations and variables

None of the following is required for historical reproduction:

- Codex `open-design` MCP
- `xcodebuildmcp`
- GitHub connector
- `mcp-score`
- `mcp-musescore`
- Dorico MCP
- Playwright
- ZAI, web-search, or web-reader MCPs
- general PDF Skill

Variables such as `ZAI_API_KEY`, `WEB_SEARCH_API_KEY`, `WEB_READER_API_KEY`, and `DORICO_LICENSE` belong only to disabled/optional integrations. Do not put them in the required setup path.

## 8. Per-score inputs and legal/manual requirements

The user must provide:

- a source PDF they are legally entitled to process;
- the full-score page range and any old-part page range;
- expected instrument/staff order and known transposing instruments;
- source pitch convention/key and requested destination concert key;
- expected movements, bar count, repeats/endings, pickups, lyrics, and deliverables where known;
- a human reviewer for ambiguous musical content and final visual acceptance.

The repository cannot bundle arbitrary copyrighted source scores or fonts. Test fixtures must be original, public-domain, licensed, or synthetic.

## 9. Clean-machine acceptance sequence

Run without processing a copyrighted production score:

- [ ] Fresh clone has no required untracked files.
- [ ] Python virtual environment installs from the committed lock/requirements without manual package additions.
- [ ] `python --version` is in the supported range.
- [ ] `pdftoppm -v` starts and records version.
- [ ] Audiveris CLI starts and records version; Java runtime is usable.
- [ ] `MuseScore4.exe --version` starts and records version.
- [ ] `scripts/musicxml_invariants.py --self-test` passes.
- [ ] Unit/integration tests pass with only documented variables.
- [ ] MusicXML XSD validator can locate a legally sourced schema with verified checksum.
- [ ] A small licensed/synthetic two-page fixture completes render → OMR → MusicXML → MuseScore → reopen → QA.
- [ ] Instrument fixture proves B-flat clarinet and Horn in F written/concert behavior.
- [ ] Native-object fixture proves Lyrics, Arpeggio, and Glissando persistence after save-close-reopen.
- [ ] Linked-part fixture persists and exports after save-close-reopen.
- [ ] Full-score and part MusicXML reopen in MuseScore and pass invariants.
- [ ] Vision-provider acceptance test proves image input; otherwise manual visual review is explicitly selected.
- [ ] Human reviewer signs the musical/engraving acceptance section.

## 10. Current freeze blockers

Every line is an **OPEN_SOURCE_REPRODUCTION_GAP**:

- Critical current source, Skills, tests, reports, and third-party schema material are untracked.
- The pre-audit snapshot had 14 tracked modifications and 21,182 untracked files; these audit changes bring the observed counts to 15 and 21,190 until reviewed and committed. Large virtualenv/work directories obscure the release boundary.
- Python declarations do not match imports.
- Third-party MusicXML schema provenance/license/checksum/install is incomplete.
- Default execution profile is contradictory.
- External executable discovery is not repository-owned and tested.
- Provider capability acceptance is not implemented.
- A clean clone has not passed the acceptance sequence above.

Therefore, do not tag or declare V0.1 frozen yet.
