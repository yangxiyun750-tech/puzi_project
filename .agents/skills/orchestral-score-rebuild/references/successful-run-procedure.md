# Successful Run Procedure and Stage Gates

This reference makes the validated multi-conversation workflow explicit. It is normative for a production reconstruction. A stage may be skipped only when the user expressly changes scope and the QA report records the reason.

## Gate 0 — Environment readiness

Before touching the source score:

1. Resolve the exact source PDF path and confirm it is readable.
2. Resolve and execute the actual Audiveris CLI, MuseScore Studio 4 CLI, `pdftoppm`, Python 3, and Audiveris Java runtime.
3. Record executable paths, versions, commands, and invocation results.
4. Stop if a required executable cannot start. Documentation, shortcuts, and installer remnants are not proof of installation.
5. Run the repository environment doctor and record its output. Run the capability doctor separately; unverified visual capability must use manual review.
6. Use score-rebuild-manifest.json as the machine-readable dependency contract.

## Gate 1 — Original-key two-page prototype

1. Preserve the original PDF unchanged.
2. Extract only the first two full-score pages and render them at 400 DPI.
3. Run Audiveris, retain the `.omr`, export MusicXML/MXL, and run structural checks.
4. Import into MuseScore as native notation. Never move PDF/vector noteheads.
5. Compare both pages against the original. Do not guess ambiguous pitch or rhythm; report it.
6. Obtain visual/musical approval before expanding to the complete score.

## Gate 2 — Real instrument structure

Replace generic OMR staves with real MuseScore instrument definitions, not labels. Confirm exact order, staff count, clefs, percussion behavior, transposition metadata, and multi-staff grouping. Explicitly validate B-flat clarinet, Horn in F, Harp grand staff, Solo Voice, Viola, Violoncello, Double Bass, and percussion.

## Gate 3 — Complete original-key reconstruction

Use only the declared full-score pages as the primary OMR source. Existing part pages are secondary evidence for individual ambiguities. Preserve the original written/concert-pitch convention, bar count, meter, repeats, tempo, orchestration, and all notation. Run page-by-page source comparison and MusicXML structural checks before transposition.

## Gate 4 — Native semantic-object repair

- Restore Chinese lyrics as MuseScore Lyrics objects anchored syllable by syllable, including verses and melismas. Do not use generic staff text or change notes to make text fit.
- Restore Harp rolled chords with native Arpeggio objects and glissandi with native Glissando objects, including correct start and destination anchors. Do not fake them with text or unattached lines.
- Repair source-determined ties, slurs, articulations, dynamics, hairpins, pizz./arco, tempo, endings, fermatas, tremolos, grace notes, clefs, barlines, and special notation.
- If evidence is ambiguous, leave a review item instead of inventing notation.

## Gate 5 — Pre-transposition verification

Save a verified original-key `.mscz` checkpoint and MusicXML baseline. Confirm every real instrument definition and the concert-pitch source key in MuseScore. Record all unresolved items; do not transpose with a high-severity source discrepancy.

## Gate 6 — Concert-key transposition

Transpose music objects in MuseScore concert-pitch view to the requested concert key. Let instrument definitions generate written pitches and signatures. Preserve rhythms, structure, lyrics, spanners, harp objects, dynamics, articulations, orchestration, and rehearsal structure. Run baseline/final invariants and written-versus-concert spot checks.

## Gate 7 — Linked parts and layout

Generate fresh linked parts from the corrected master; never transpose legacy PDF parts. Verify part identity, written pitch, multimeasure rests, cues, breaks, collisions, page turns, and combined-parts ordering.

## Gate 8 — Persistence validation

Save the master, close MuseScore, reopen the saved `.mscz`, and verify that linked parts, native lyrics, arpeggios/glissandi, instrument definitions, transposition, layout, and score/part relationships persist. An in-memory success is not sufficient.

## Gate 9 — MusicXML round trip and downstream delivery

Export full-score and per-part MusicXML where requested. Reopen every exported file in MuseScore and compare measure count, pitch/rhythm, key signatures, written transposition, lyrics, repeats/endings, dynamics, tuplets, and Harp objects. Explain that linked-part relationships and some engraving do not survive MusicXML import into a DAW such as Logic Pro; supply PDFs as visual references.

## Decision ownership

| Decision | Deterministic code | Reasoning/vision provider | Human musical review |
|---|---|---|---|
| File/tool existence, counts, hashes, XML invariants | Primary | May interpret failures | Fallback |
| Source-page visual comparison | Supporting metrics | Required capability | Final authority for ambiguity |
| Ambiguous pitch/rhythm/voice | Must not guess | Proposes evidence-backed answer | Required if not source-determined |
| Instrument identity/transposition semantics | Validates metadata | Interprets score context | Required for unresolved cases |
| Professional engraving and page turns | Detects some collisions | Visual review | Final acceptance |

## Completion rule

Do not call a production pass complete merely because files exported. Completion requires all applicable gates, a filled QA report, zero unexplained structural differences, no open high-severity musical findings, and explicit documentation of every remaining human-review item.
