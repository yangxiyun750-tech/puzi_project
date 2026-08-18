---
name: orchestral-score-rebuild
description: Rebuild professionally engraved printed orchestral or concert-band full scores from PDF using high-resolution page rendering, Audiveris OMR, MuseScore Studio cleanup, concert-key transposition, linked-part generation, and page-by-page musical QA. Use when a printed full score or combined score-and-parts PDF must become an editable MuseScore score, a clean transposed full score, and correctly transposed instrumental part PDFs. Do not use for graphical PDF notehead manipulation, handwritten music, lead sheets, or pixel-faithful PDF editing.
---

# Orchestral Score Rebuild

Reconstruct notation as music data, validate it against the printed source, transpose the sounding music, and engrave linked score and parts in MuseScore Studio.

## Enforce the core rule

- Treat the source PDF as read-only reference material.
- Never transpose by moving noteheads, staff objects, or PDF vector elements.
- Never separately transpose the old PDF instrumental parts.
- Prefer correct, readable notation over matching source pixels.
- Do not declare completion from successful OMR or export alone. Require musical and visual QA.

## Establish the project contract

Record the source PDF; the page range containing the **full score**; old-part page ranges; title; source and destination concert keys; directed interval; score pitch convention; instrument/staff order; instrument changes; expected movements, measures, pickups, repeats, endings, and parts.

For this repository's `天使的脸` build, use:

- source concert key: B major;
- destination concert key: E-flat major;
- sounding-pitch movement: up 4 semitones (major third);
- final basename: `天使的脸_Eb`.

Use E-flat spelling, not enharmonic D-sharp major. If explicitly used for another work, replace only these project-specific values and filenames.

## Prepare an auditable workspace

Keep the original PDF unchanged. Separate `source_pages/`, `omr/`, `baseline/`, `final/previews/`, `final/parts/`, and `qa/`. Capture tool versions and exact commands in `QA_REPORT.md`. Check each installed tool's local help before relying on flags.

## Render the source PDF

1. Inspect the combined PDF and isolate the full-score page range. Exclude covers, blanks, and old part pages from the OMR book.
2. Render the selected pages with Poppler `pdftoppm`, preferring 400 DPI PNG:

   ```text
   pdftoppm -png -r 400 -f FIRST -l LAST "source.pdf" "source_pages/page"
   ```

3. Verify page count, order, orientation, crop, legibility, and unclipped staves.
4. Use lower resolution only for a documented resource limit.

## Run Audiveris OMR

1. Build one ordered compound book from the page images. Use `scripts/make_audiveris_playlist.py`; never trust lexical filesystem order.
2. Batch-build, transcribe, save, and export. A typical current sequence is:

   ```text
   audiveris -batch -playlist "omr/full-score-playlist.xml"
   audiveris -batch -transcribe -export -save -output "omr/output" -- "omr/full-score-playlist.omr"
   ```

   Adapt only after checking the installed Audiveris help, and verify actual output paths.
3. Retain the `.omr` project, playlist, logs, and exported `.mxl`/MusicXML.
4. Review failed steps and suspicious regions. Correct the `.omr` interactively when safer than extensive downstream repair, then re-export.

Do not feed old part pages into the full-score book. Consult them only as secondary evidence for a genuinely ambiguous full-score passage.

## Normalize the MuseScore source model

1. Import the Audiveris `.mxl`/MusicXML into MuseScore Studio and save a native pre-transposition checkpoint.
2. Preserve instrument order and measure structure. Remove a staff only after proving it is spurious.
3. Map every staff to the correct MuseScore instrument definition **before transposition**. Use MuseScore definitions for written-pitch transposition, range, clefs, percussion, octave transposition, and instrument changes; do not invent staff offsets.
4. Resolve pitch semantics explicitly:
   - determine whether the printed score shows written or concert pitch;
   - enable Concert pitch and confirm all pitched staves reproduce the declared source concert key and harmonic alignment;
   - check transposing staves against C-instrument material and the original;
   - correct imported pitches or metadata if Audiveris omitted transposition information;
   - record the result in the report.
5. Clean using standard MuseScore engraving:
   - reset stems to defaults (`Select Similar`, then `Ctrl+R` in current MuseScore Studio);
   - set ordinary beams to time-signature defaults, then recreate intentional exceptional beaming from the source;
   - reset accidental imported offsets selectively;
   - retain and repair tuplets, slurs, ties, articulations, dynamics, tempo, repeats, endings, lyrics, rehearsal marks, meter, clefs, and names;
   - use appropriate text styles/fonts and professional orchestral layout.

Never globally delete breaks, beams, text, or spanners when some are meaningful.

## Validate before transposition

Compare page by page and staff by staff with the **original PDF**. Read `references/qa-protocol.md` and copy `assets/QA_REPORT_TEMPLATE.md` to the project root as `QA_REPORT.md`.

- Account for every page, system, staff, measure, voice, and instrument.
- Compare pitches, chords, rests, rhythms, tuplets, spanners, marks, dynamics, text, lyrics, repeats/endings, rehearsal marks, and clefs.
- Identify suspicious measures even when no error is yet proven.
- Resolve or explicitly leave open each item with page, system, staff, and measure references.
- Confirm B major at concert pitch for `天使的脸`.

Save corrected pre-transposition `.mscz` and uncompressed MusicXML baselines.

## Transpose the music

For `天使的脸`:

1. Turn on Concert pitch and verify B major.
2. Select the whole score and use **Tools → Transpose → Chromatically → To key → Up → E-flat major**.
3. Transpose key signatures and chord symbols. Never use diatonic transposition.
4. Confirm sounding pitches moved exactly +4 semitones and are spelled in E-flat major.
5. Confirm rhythm, meter, bar count, repeats, tempo, dynamics, articulations, lyrics, orchestration, and rehearsal structure did not change.

Turn Concert pitch off and verify MuseScore-derived written notation. Required spot checks:

- C instruments: E-flat major written;
- B-flat clarinet: F major written;
- F horn: B-flat major written.

For every other instrument, inspect its MuseScore definition and Staff/Part properties. Preserve conventional open/atonal signatures and octave-transposing notation where appropriate.

Run `scripts/musicxml_invariants.py` against baseline and final MusicXML. Treat every reported difference as suspicious until explained.

## Generate linked parts

1. Generate/open MuseScore's linked part for each instrument only after the full score is corrected and transposed.
2. Never paste separately transposed notation into unlinked documents.
3. Preserve instrument changes and multi-staff instruments in the appropriate part.
4. Engrave parts for names, page/staff size, multimeasure rests, breaks, rehearsal marks, existing cues, collision avoidance, and practical page turns.
5. Export all parts as one parts-only PDF and as individual PDFs. Verify count/order and that the combined file excludes the conductor score.

## Run final notation and visual QA

Inspect the full score and every part at high zoom. Confirm:

- noteheads attach to correct stems, stems to beams, with no floating beams or displaced flags;
- ties connect intended identical pitches and slurs have correct anchors;
- ledger lines, accidentals, dots, tuplets, rests, and voices are correct;
- no collisions, missing notes, duplicated notes, or unexplained rhythmic overflow/underflow in any measure remain;
- repeats, endings, tempo, dynamics, lyrics, and rehearsal structure survive;
- concert- and written-pitch checks pass for every instrument;
- score/part spacing and page turns are practical.

Render the final score to PDF and page PNGs. Compare each final page side by side with its source. Expect pitch height, accidentals, breaks, and pagination to change; compare musical content, not pixels.

## Deliver identifiable outputs

Produce:

```text
天使的脸_Eb_full_score.mscz
天使的脸_Eb_full_score.musicxml
天使的脸_Eb_full_score.pdf
天使的脸_Eb_parts.pdf
parts/<individual linked part PDFs>
QA_REPORT.md
```

Retain the Audiveris `.omr` and correction artifacts. Verify every required file exists, opens, has nonzero size, and matches the reviewed MuseScore revision. Do not complete with a high-severity musical discrepancy or unexplained structural finding.

## Resources

- Use `scripts/make_audiveris_playlist.py` to create the naturally sorted compound-book playlist.
- Use `scripts/musicxml_invariants.py` to compare baseline and final MusicXML while ignoring expected pitch values.
- Read `references/qa-protocol.md` during page-by-page and final QA.
- Copy and fill `assets/QA_REPORT_TEMPLATE.md`.

