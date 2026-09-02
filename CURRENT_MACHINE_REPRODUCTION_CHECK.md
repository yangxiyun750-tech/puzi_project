# Current Machine Reproduction Check

Date: 2026-08-26
Project: repository root (`.`)
Scope: Phase 0.5 reproducibility closure only. No private score was opened, modified, transposed, or regenerated.

## Result

The current Windows machine passes the environment doctor and the repository-authored synthetic smoke test. A second run from a newly created isolated Python 3.12 virtual environment, populated only from `requirements.txt`, also passes.

This proves local dependency declaration and basic pipeline connectivity. It is not evidence of musical-quality equivalence, visual-review quality, Audiveris recognition accuracy, or reproduction on a physically separate clean Windows machine.

## Current project virtual environment

- Environment doctor: `PASS=18 WARN=1 FAIL=0`, exit code `0`.
- Synthetic smoke test: `BASIC_PIPELINE_CONNECTIVITY`, exit code `0`.
- Warning: optional `pdfplumber` is not installed. It is used only by legacy/private-fixture-specific PDF text helpers and is not a core V0.1 runtime dependency.

## Fresh isolated virtual environment

Environment: `.tmp/phase05_clean_venv` (temporary and excluded from Git).

Installation source: only the repository `requirements.txt`, using Python `3.12.10`.

Doctor result: `PASS=18 WARN=1 FAIL=0`, exit code `0`.

Verified components:

| Component | Result | Detected version/path |
| --- | --- | --- |
| Python | PASS | 3.12.10; isolated venv interpreter |
| lxml | PASS | 6.1.2 |
| numpy | PASS | 2.5.2 |
| Pillow | PASS | 12.3.0 |
| pypdf | PASS | 6.16.2 |
| music21 | PASS | 10.5.0 |
| partitura | PASS | 1.9.0 |
| musicdiff | PASS | 5.2 |
| pypdfium2 | PASS | 5.13.0 |
| PyMuPDF | PASS | 1.28.2 |
| pdfplumber | WARN | Optional; not installed |
| Poppler `pdftoppm` | PASS | 26.05.0; supplied through `PDFTOPPM_EXE` |
| Audiveris | PASS | 5.11.0; `C:\Program Files\Audiveris\Audiveris.exe` |
| MuseScore Studio | PASS | 4.7.4; `C:\Program Files\MuseScore 4\bin\MuseScore4.exe` |
| Audiveris Java | PASS | OpenJDK 25.0.3; Audiveris bundled runtime |
| Project Skill/resources | PASS | canonical project-local `focused-score-rebuild` Skill |
| MusicXML schema | PASS | pinned MusicXML 4.0 files; all SHA-256 values match |
| Project and temporary writes | PASS | create/write/delete probe succeeded |

Fresh-environment synthetic smoke result, exit code `0`:

1. Repository-authored, non-copyrighted MusicXML fixture parsed.
2. Pinned MusicXML 4.0 XSD validation passed.
3. MusicXML invariant self-test passed.
4. MuseScore imported MusicXML and saved native MSCZ.
5. MuseScore reopened MSCZ and exported PDF.
6. Poppler rendered the PDF to PNG.

Audiveris executable and bundled Java startup are verified by the doctor. The smoke test intentionally does not claim OMR quality from a synthetic page.

## Capability doctor

- Code reasoning: `AVAILABLE` only because the provider was named and explicitly operator-verified.
- Visual review: `NOT_CONFIGURED`.
- Human review fallback: `AVAILABLE`.
- Effective mode: `MANUAL_VISUAL_REVIEW_REQUIRED`.

The capability doctor does not manufacture a visual-review PASS. Automated visual QA remains unavailable until a named provider is explicitly verified; the documented human-review fallback is required meanwhile.

## Remaining reproduction boundary

The following is still required before a release freeze:

1. Review and commit the exact Phase 0.5 tracked set; this task intentionally creates no commit or tag.
2. Clone that commit on a separate clean Windows 10/11 machine.
3. Follow `docs/INSTALL_WINDOWS.md`, acquire the pinned schema, and rerun doctor/capability doctor/smoke test.
4. Record external-machine results, including executable discovery without relying on this machine's Codex Poppler cache path.
5. Configure and explicitly verify an automated visual-review provider, or formally accept manual visual review as the release operating mode.

Therefore: `V0.1_FREEZE_READY = NO`.
