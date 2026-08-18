# QA Protocol

Use this protocol for the corrected pre-transposition score and again after transposition. A successful export is not evidence of correct music.

## Build the comparison map

Map every original full-score page to its printed page number, systems, MuseScore measure range, rehearsal marks, expected staff count, and review status.

Compare in the source pitch convention. If the printed score is at written pitch, compare with MuseScore Concert pitch off; if at concert pitch, compare with it on. Also perform an independent concert-pitch harmonic check.

## Mark suspicious measures

Flag a measure, even before proving an error, when it contains or borders:

- an Audiveris warning, failed step, or low-confidence symbol;
- dense chords, divisi, cross-staff notation, multiple voices, cues, or ossias;
- short beams, tremolos, unusual flags, or beams across rests/barlines;
- tuplets, nested tuplets, grace notes, acciaccaturas, or unusual noteheads;
- ties/slurs across systems/pages, endings, segnos/codas, repeats, or mid-measure clefs;
- ledger-heavy chromatic writing, unisons/seconds, or notes close to barlines;
- lyric melismas, multiple verses, tempo equations, or OCR-sensitive text;
- instrument changes, transposing staves, keyless staves, percussion, or condensed writing;
- a mismatch in duration, note/rest count, staff count, or system boundary;
- any visual anomaly, even if playback sounds plausible.

Record page, system, measure, staff, severity, observation, resolution, and evidence.

## Validate rebuilt source notation

For every staff and measure, check:

1. Measure sequence, pickup, barlines, repeats, endings, and jumps.
2. Meter and exact duration in every voice, including hidden rests and irregular bars.
3. Pitch, octave, chord membership, and unisons against the original.
4. Accidentals, cautionaries, key signatures, spelling, and ledger lines.
5. Rests, dots, tuplets, tremolos, grace notes, cues, and voices.
6. Beam grouping, stem attachment/direction, flags, cross-staff notation, and noteheads.
7. Tie endpoints versus slur anchors, phrase marks, and lyric extenders.
8. Articulations, ornaments, dynamics, hairpins, tempo/technique text, and rehearsal marks.
9. Lyrics, syllabification, elisions, melismas, verse order, punctuation, and encoding.
10. Instrument names/order, clefs, staff type, transposition definition, and instrument changes.

Use playback only as an additional diagnostic; it cannot prove spelling, voice allocation, or engraving.

## Validate the transposition

- Confirm Concert pitch is B major before the `天使的脸` transposition.
- Confirm representative pitches in every pitched staff move +4 semitones.
- Confirm final Concert pitch is E-flat major, not D-sharp major.
- Confirm key changes and chord symbols move consistently.
- With Concert pitch off, verify C instruments in E-flat major, B-flat clarinet in F major, and F horn in B-flat major.
- For every other pitched staff, record the MuseScore instrument definition and Staff/Part transposition; verify the written key and a sounding/written pitch pair.
- Check mid-score instrument changes, octave-transposing instruments, keyless instruments, and percussion conventions.

## Validate structural invariants

Run `scripts/musicxml_invariants.py` on the corrected pre-transposition and final MusicXML. Review all findings. Independently confirm unchanged part/staff order, measures, meter, rhythms, note/rest counts, repeats/endings, tempo, rehearsals, dynamics, hairpins, articulations, tuplets, ties, slurs, lyrics, and clef-event locations.

Explain intentional exceptions. Do not waive unexplained differences.

## Validate final engraving

Inspect every score and part page at 200–400% zoom and normal reading size.

- Check notehead–stem–beam geometry, flags, ledger lines, dots, accidentals, and tuplets.
- Check spanner anchors after line/page breaks.
- Check collisions, staff spacing, balance, margins, headers, numbers, names, and brackets.
- Check part multimeasure rests, existing cues, tacets, rehearsals, and page turns.
- Ensure no important entry or continuation is hidden by a page turn.
- Ensure the combined parts PDF contains all and only intended parts.

Render final PNGs and review them beside the source. Do not use raw pixel difference as the acceptance test because transposition and professional reflow legitimately move glyphs.

## Completion rule

Pass only when all pages and parts have evidence; no high-severity item remains; every structural finding is resolved or justified; final files open and match the reviewed revision; and the `.omr` plus pre-transposition baseline remain available.
