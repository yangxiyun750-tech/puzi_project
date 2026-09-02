# QA Protocol

Use this protocol for the corrected original-key score, again after optional transposition, and for final score/part engraving. Export success is not evidence of correct music.

## Build the comparison map

Map every eligible source page to printed page, systems, MuseScore measure range, rehearsal marks, expected staff count, and review status. Compare in the source pitch convention, then perform an independent concert-pitch harmonic check when relevant.

Flag measures with OMR warnings, dense chords, multiple voices, cues, cross-staff notation, unusual beams/tremolos, tuplets, grace notes, spanners across systems, repeats/endings, ledger-heavy chromatic writing, lyrics, instrument changes, percussion, duration/count mismatches, or any visual anomaly.

Record page, system, measure, staff, severity, observation, decision, correction, verification evidence, and status. Put genuine ambiguity in the human review queue.

## Validate rebuilt source notation

For every staff and measure, check:

1. Measure sequence, pickup, barlines, repeats, endings, and jumps.
2. Meter and exact duration in every voice, including hidden rests and irregular bars.
3. Pitch, octave, chord membership, unisons, and accidentals against the source.
4. Rests, dots, tuplets, tremolos, grace notes, cues, beams, stems, flags, and noteheads.
5. Tie endpoints, slur anchors, lyric extenders, articulations, ornaments, dynamics, hairpins, tempo, techniques, and rehearsals.
6. Lyrics, syllabification, verses, punctuation, melismas, encoding, and note anchoring.
7. Instrument order, real definitions, clefs, staff types, transposition metadata, percussion behavior, and instrument changes.

Playback is supplementary; it cannot prove spelling, voice allocation, notation objects, or engraving.

## Validate optional transposition

- Verify and record source and destination concert keys and the directed interval.
- Confirm representative sounding pitches move by the expected interval with the requested spelling.
- With concert pitch off, verify a sounding/written pitch pair and written key for every transposing or octave-transposing instrument.
- Check mid-score instrument changes, keyless staves, and percussion conventions.
- Confirm all non-pitch structural and semantic invariants remain unchanged.

## Validate structural invariants

Run `scripts/musicxml_invariants.py` on the verified original-key baseline and candidate. Review every finding. Independently confirm unchanged part/staff order, measures, meter, rhythms, note/rest counts, repeats/endings, tempo, rehearsals, dynamics, hairpins, articulations, tuplets, ties, slurs, lyrics, and clef-event locations. Explain intentional exceptions; do not waive unexplained changes.

## Validate final engraving

Inspect every score and part page at 200–400% and normal reading size. Check notehead–stem–beam geometry, flags, ledger lines, dots, accidentals, tuplets, spanners after breaks, collisions, spacing, margins, headers, names, brackets, multimeasure rests, cues, tacets, rehearsals, and page turns.

Render final PNGs beside the source. Compare musical content, not raw pixels: professional reflow and optional transposition legitimately move glyphs.

## Completion rule

Pass only when every page and part has evidence, no blocking/important issue remains unresolved, all decisions have been applied and verified, every structural finding is resolved or justified, saved outputs reopen correctly, and `.omr` plus the original-key baseline remain available.
