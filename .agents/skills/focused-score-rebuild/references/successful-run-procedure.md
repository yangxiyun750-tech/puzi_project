# Successful Run Procedure and Stage Gates

This reference is normative for a production reconstruction. Skip a gate only when the user expressly changes scope and the QA report records the reason and consequence.

## Intake gate — Eligibility and classification

Render and inspect all required pages before OMR. Continue only when the source contains clear, complete printed notation and fits `melody`, `voice_piano`, or `wind_band_basic`. Record page-level reasons and stop with `NEEDS_RESCAN` or `OUT_OF_SCOPE` when appropriate.

Capture multilingual source metadata under `multilingual-metadata.md`. Resolve identity-affecting conflicts and require `METADATA_STATUS = PASS`; translations and romanizations remain aliases unless the user selects them for display.

Use `library_catalog.py` to ask and record at most three related classification questions per turn. Processing requires `CLASSIFIED`; unresolved rights, an ineligible source, or an unsupported family blocks OMR.

## Gate 0 — Environment readiness

Resolve the exact source PDF. Execute the real Audiveris, MuseScore Studio 4, `pdftoppm`, Python, and Audiveris Java runtimes. Record paths, versions, and invocation results. Run the repository doctor and capability doctor. Stop on a required-tool failure; unverified visual capability must route to a declared human reviewer.

## Gate 1 — Original-key prototype

Preserve the source PDF. For a long or multi-staff source, reconstruct a small representative page range at 400 DPI; a short monophonic source may be one auditable unit. Retain `.omr`, MusicXML/MXL, MuseScore, renders, and QA. Obtain visual and musical approval before expanding unless the user explicitly waives the prototype after reviewing the risk.

## Gate 2 — Real instrument structure

Replace generic OMR staves with real MuseScore instrument definitions, not labels. Confirm order, staff count, clefs, percussion behavior, transposition metadata, octave transposition, instrument changes, and multi-staff grouping.

## Gate 3 — Complete original-key reconstruction

Use only declared eligible score pages as primary OMR input. For wind band, legacy parts are secondary evidence for an individual ambiguity. Preserve source pitch convention, bar count, meter, repeats, tempo, instrumentation, text, and all notation.

## Gate 4 — Native semantic-object repair

Restore lyrics as native Lyrics objects with syllables, verses, melismas, punctuation, and anchors. Restore rolled chords and glissandi with native Arpeggio and Glissando objects. Repair source-determined ties, slurs, articulations, dynamics, hairpins, techniques, tempo, endings, fermatas, tremolos, grace notes, clefs, barlines, and special notation. Leave genuine ambiguity in the review queue rather than inventing content.

## Gate 5 — Human verification dialogue

Read `human-review-dialogue.md` and `review-issue-schema.md`. Build page-by-page evidence and a resumable queue. Ask only unresolved musical questions, record natural-language decisions, apply the approved changes, and verify them. Do not advance while `QA_STATUS = BLOCKED`.

## Gate 6 — Pre-transposition verification

Save and reopen a verified original-key `.mscz` and MusicXML baseline. Confirm real instruments, source pitch convention, source concert key, and all resolved review items. If transposition is not requested, this becomes the final musical baseline.

## Gate 7 — Optional concert-key transposition

Verify rather than assume the source concert key. Derive and record the directed chromatic interval and destination spelling. Transpose native music objects in MuseScore concert-pitch view and let real instrument definitions generate written notation. Preserve every non-pitch invariant and run baseline/final MusicXML checks.

## Gate 8 — Linked parts and layout when applicable

For basic wind band, generate fresh linked parts from the corrected master and do not transpose legacy PDF parts. Verify identity, written pitch, instrument changes, multimeasure rests, cues, breaks, collisions, page turns, and combined-parts order. Skip this gate for monophonic or voice-piano work unless the user requests separate parts.

## Gate 9 — Persistence and round trip

Save, close, and reopen the `.mscz`. Verify native lyrics, arpeggios/glissandi, instrument definitions, optional transposition, layout, and linked parts persist. Reopen requested MusicXML exports in MuseScore and compare musical structure and written-pitch behavior.

## Decision ownership

| Decision | Deterministic code | Reasoning/vision provider | Human musical review |
|---|---|---|---|
| Files, counts, hashes, XML invariants | Primary | Interprets failures | Fallback |
| Source/render visual comparison | Supporting metrics | Requires verified capability | Final authority for ambiguity |
| Ambiguous pitch/rhythm/voice | Must not guess | Proposes evidence-backed options | Required when source remains ambiguous |
| Instrument and transposition semantics | Validates metadata | Interprets score context | Required when unresolved |
| Engraving and page turns | Detects some problems | Visual review | Final acceptance |

## Completion rule

Completion requires every applicable gate, a filled QA report, zero unexplained structural differences, no unresolved blocking or important issue, verified saved outputs, and explicit documentation of any user-accepted cosmetic deferral.
