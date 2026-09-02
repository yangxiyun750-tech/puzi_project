---
name: focused-score-rebuild
description: Reconstruct clear printed sheet-music PDFs as editable MuseScore notation for monophonic parts, solo voice with basic piano accompaniment, and basic concert-band scores, with human QA, optional transposition, and local question-driven library classification. Do not use for handwritten/draft, blurry, incomplete, photographically distorted, orchestral, or highly complex notation.
---

# Focused Score Rebuild

Turn eligible printed PDFs into verified native MuseScore notation. Keep musical judgment in the Agent-and-human loop; use deterministic scripts for evidence, validation, review state, and catalog state, never for inventing notation.

## Enforce the scope

Accept only `melody` (one monophonic melodic staff), `voice_piano` (one solo vocal line with lyrics and basic two-staff piano accompaniment), and `wind_band_basic` (a conventionally notated basic concert-band score).

Treat orchestral scores, handwritten music, drafts, lead sheets without a fully notated melody, graphic/aleatoric notation, dense divisi, frequent cross-staff/polyphonic writing, highly complex contemporary notation, and materially damaged sources as out of scope. Do not silently broaden the job. Explain the boundary and ask for a clearer or simpler source.

## Non-negotiable rules

- Treat the source PDF as read-only evidence.
- Never transpose by moving PDF/vector graphics or noteheads.
- Never silently guess an uncertain pitch, octave, duration, voice, repeat, lyric, instrument identity, or transposition definition.
- Prefer correct native notation and professional engraving over source pixel positions.
- Do not declare completion from successful OMR, import, or export alone. Require structural, visual, and human musical QA.
- Keep private PDFs, renders, `.omr`, MuseScore files, crops, question logs, and catalogs out of the public repository.

## Gate the input before OMR

Read `references/intake-and-library-classification.md` and `references/multilingual-metadata.md`. Render representative pages for inspection, but do not run Audiveris until every page intended for recognition is eligible.

The PDF must be a clean printed/exported score or a high-quality scan. Reject or request a rescan when any music is blurred, clipped, obscured, handwritten, draft-quality, severely skewed, perspective-distorted, shadowed, low-contrast, overcompressed, or too low-resolution to distinguish notation and lyrics reliably.

Record `INPUT_STATUS = PASS`, `NEEDS_RESCAN`, or `OUT_OF_SCOPE` with page-level reasons. Only `PASS` may continue to OMR.

Extract source-grounded titles, contributor credits, and music information into `qa/source_metadata.json` with `scripts/metadata_record.py`. Preserve original Unicode separately from translated or romanized aliases. Use PDF text first, language-aware OCR second, verified vision third, and a human question for unresolved conflicts. Require `METADATA_STATUS = PASS` before filenames, catalog identity, or final credits are authoritative.

## Classify by short human dialogue

Create or resume a private local catalog with `scripts/library_catalog.py`. Ask at most three related intake/classification questions per turn. Record score family, source quality, genre/style, intended use, difficulty, instrumentation, and rights status; optional language and tags improve similarity grouping. Use named collections for related works and record why an entry belongs there.

Classification never overrides musical QA or input eligibility. `out_of_scope`, `needs_rescan`, and unresolved rights status block score processing. Similarity suggestions require user confirmation.

## Establish the reconstruction contract

Before processing, record:

- source PDF and eligible score page range;
- cover, blank, and legacy-part ranges excluded from primary OMR, or `not applicable`;
- work title and output basename;
- source pitch convention and verified source concert key;
- whether transposition is requested, destination concert key, spelling, and directed interval;
- selected score family, instrument/staff order, instrument changes, percussion behavior, and expected linked parts when applicable;
- expected movements, measures, pickups, meter changes, repeats, endings, and rehearsal structure;
- human-review mode: `guided` (default), `fast`, or `expert`.

For wind band, distinguish full-score pages from covers, blanks, and legacy parts; use legacy parts only as secondary evidence. Do not copy values from a previous work. If a dependent fact is unknown, discover it from the source or ask before that stage.

## Gate the environment

Read `references/successful-run-procedure.md` before production and apply `assets/PRODUCTION_STAGE_GATES_QA.md`.

Before touching a source score, run `python -m score_rebuild doctor` (or `score-rebuild.cmd doctor`) and `capability-doctor`. Stop on an environment `FAIL`. An unverified visual provider is not available; use the declared human reviewer.

## Prepare an auditable workspace

Keep the original PDF unchanged. Separate `source_pages/`, `omr/`, `baseline/`, `qa/`, `final/previews/`, and `final/parts/`. Capture tool versions and exact commands in `QA_REPORT.md`. Keep score inputs, page images, `.omr`, MuseScore files, exports, crops, and decision logs out of the public repository.

## Render and recognize

1. Isolate only the eligible declared score pages.
2. Render them with Poppler `pdftoppm`, preferring 400 DPI PNG.
3. Verify count, order, orientation, crop, legibility, and unclipped staves.
4. Build an ordered Audiveris compound book with `scripts/make_audiveris_playlist.py`; never trust lexical page order.
5. Run Audiveris batch build/transcription/export/save after checking the installed CLI help.
6. Retain the playlist, logs, `.omr`, and MusicXML/MXL.
7. Correct Audiveris interactively when that is safer than extensive downstream reconstruction.

For a long or multi-staff source, reconstruct a representative prototype before expanding. A short monophonic source may proceed as one auditable unit after the input gate.

## Build the native MuseScore source model

1. Import MusicXML/MXL into MuseScore Studio and save a pre-transposition `.mscz` checkpoint.
2. Preserve measure structure and staff order. Remove a staff only after proving it spurious.
3. Assign real MuseScore instrument definitions before any transposition. Do not fake transposing instruments with labels or manual offsets.
4. Determine whether the printed score uses concert or written pitch. Verify the source concert key and harmonic alignment in MuseScore concert-pitch view.
5. Restore native Lyrics, Arpeggio, Glissando, tuplet, tie, slur, articulation, dynamic, hairpin, tempo, repeat, ending, rehearsal, clef, and instrument-change objects where the source determines them.
6. Use standard MuseScore engraving defaults for ordinary stems, beams, rests, accidental offsets, and spacing. Preserve intentional exceptions from the source.

Apply family-specific checks:

- `melody`: enforce the printed clef, key, meter, octave, lyrics/chord symbols, and one intended melodic voice unless the source clearly contains another voice.
- `voice_piano`: use a real vocal instrument and real Piano grand staff; restore Lyrics objects, verses, syllable anchors, melismas, pedaling, arpeggios, and cross-staff notation only when clearly printed.
- `wind_band_basic`: verify every real instrument, written/concert pitch semantics, staff order, percussion behavior, instrument changes, and linked-part identity.

## Run the human verification dialogue

After the first complete MuseScore reconstruction and before transposition or final delivery, read `references/human-review-dialogue.md` and `references/review-issue-schema.md`.

- Compare every source page with the rebuilt rendering before asking questions.
- Resolve source-determined issues yourself and record the evidence.
- Put only genuine ambiguities into `qa/review_queue.json` using `scripts/review_queue.py`.
- Ask in small, page-oriented batches. The default guided mode presents at most three related issues per turn.
- Whenever possible, show a source crop and rebuilt crop with the staff/measure identified.
- Accept natural-language answers; translate them into recorded decisions without forcing command syntax on the user.
- Apply a musical correction only after the decision is clear, then verify the edited score and mark the issue resolved.
- Persist the queue and `qa/decisions.jsonl` so another Agent can resume without repeating answered questions.

Do not continue to transposition while `QA_STATUS = BLOCKED`.

## Validate the original-key reconstruction

Read `references/qa-protocol.md` and copy `assets/QA_REPORT_TEMPLATE.md` to the project workspace.

- Account for every page, system, staff, measure, voice, instrument, and structural event.
- Compare pitch, octave, chord membership, rests, rhythms, tuplets, spanners, marks, text, lyrics, repeats/endings, and clefs.
- Run MusicXML structural checks and resolve or explain every finding.
- Save and reopen the verified original-key `.mscz` and MusicXML baseline.
- Require `QA_STATUS = PASS` before musical transposition. `PASS_WITH_DEFERRED_COSMETIC_ITEMS` is acceptable only when the user explicitly accepts the cosmetic deferrals.

## Transpose only when requested

1. Verify the source concert key in MuseScore concert-pitch view; do not assume it.
2. Derive and record the directed chromatic interval and destination spelling.
3. Transpose native music objects, key signatures, and chord symbols in MuseScore. Never use graphical shifting or a diatonic operation when chromatic key transposition is intended.
4. Let real MuseScore instrument definitions determine written pitches and key signatures.
5. Confirm representative sounding/written pitch pairs for every transposing, octave-transposing, keyless, percussion, and instrument-change staff.
6. Preserve rhythm, meter, measures, repeats, tempo, dynamics, lyrics, tuplets, spanners, orchestration, and rehearsal structure.
7. Run `scripts/musicxml_invariants.py` against the verified baseline and final MusicXML. Treat every unexpected difference as suspicious.

If no transposition is requested, retain the verified source key and skip only this gate; do not skip reconstruction QA.

## Generate and verify linked parts when applicable

1. For `wind_band_basic`, generate fresh linked MuseScore parts from the corrected master. Never transpose legacy PDF parts separately.
2. Preserve instrument changes and multi-staff instruments in their intended linked parts.
3. Engrave names, multimeasure rests, cues, breaks, collisions, and practical page turns.
4. Save, close, and reopen the master; confirm linked parts and native objects persist.
5. Preserve the editable MuseScore master containing all linked parts. PDF is a viewing/printing derivative, never the sole final deliverable.
6. Export score MusicXML as an editable interchange source. For wind band, export combined and individual part PDFs; export per-part MusicXML or standalone editable part files when requested.
7. Reopen the final `.mscz` and every requested MusicXML export in MuseScore, then compare measure count, keys, written pitch, rhythm, lyrics, repeats, dynamics, tuplets, applicable linked-part presence, and special objects.

## Final gate and deliverables

Inspect score and part pages at high zoom and normal reading size. Confirm notehead/stem/beam geometry, flags, ledger lines, accidentals, dots, tuplets, ties/slurs, voice separation, collisions, page turns, and all source semantics.

Always deliver an authoritative editable MuseScore master, editable MusicXML, printable PDF, QA report, and review records. Use project-derived names rather than hard-coded work titles:

```text
<basename>.mscz
<basename>.musicxml
<basename>.pdf
QA_REPORT.md
qa/review_queue.json
qa/decisions.jsonl
qa/source_metadata.json
```

For `wind_band_basic`, also deliver combined and individual linked-part PDFs and requested editable part exports. For `voice_piano`, create a separate vocal or piano part only when requested. A monophonic score normally needs no linked-part package.

The minimum completed delivery includes both editable sources and printable derivatives:

- native MuseScore `.mscz` master, containing linked parts when applicable;
- score `.musicxml` for interchange and secondary editing;
- score PDF plus applicable combined and individual part PDFs;
- QA and human-decision records.

Do not flatten, discard, or replace the native master after PDF export. MusicXML may not preserve every MuseScore layout or linked-part relationship, so the `.mscz` master is the authoritative editable source and the PDFs are visual references.

Retain the `.omr`, source renders, verified pre-transposition baseline, review evidence, and correction history in the private project workspace. Do not complete with an unexplained structural difference or unresolved musical finding.

## Resources

- Read `references/successful-run-procedure.md` for production stage gates.
- Read `references/intake-and-library-classification.md` before accepting a source or classifying a work.
- Read `references/multilingual-metadata.md` before naming, cataloging, or exporting title and music information.
- Read `references/human-review-dialogue.md` when OMR/MuseScore reconstruction is ready for human verification.
- Read `references/review-issue-schema.md` before creating or updating review issues.
- Read `references/qa-protocol.md` during original-key, post-transposition, score, and part QA.
- Apply `assets/PRODUCTION_STAGE_GATES_QA.md` and copy `assets/QA_REPORT_TEMPLATE.md` into each private project workspace.
- Use `scripts/metadata_record.py`, `scripts/library_catalog.py`, `scripts/make_audiveris_playlist.py`, `scripts/review_queue.py`, and `scripts/musicxml_invariants.py` for deterministic metadata evidence, catalog state, playlist, review state, and structural checks.
