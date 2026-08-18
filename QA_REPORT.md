# QA Report — 天使的脸 (Final Concert E-flat Production)

## Result

**PASS WITH ADVISORY MUSICIAN SPOT CHECKS**

The final score is native, editable MuseScore notation. The source PDF was used
only as a visual/text reference and was not modified. No PDF vector elements or
graphical noteheads were transposed.

- Source of truth: `天使的脸 - 乐谱和分谱.pdf`
- Source full-score pages used: 1–8
- Secondary part-reference pages available: 9–28
- Source PDF SHA-256: `7AA87A71501D64993BA3439182A64E2E777BF0C5CED6547D32AF94B514B8A884`
- Master score: 18 instruments, 19 physical staves (Harp grand staff), 54 measures
- Final concert key: E-flat major
- Full-score output: 8 pages
- Parts output: 18 individual PDFs, 19 combined pages

## Final outputs

- `天使的脸_Eb_full_score.mscz`
- `天使的脸_Eb_full_score.musicxml`
- `天使的脸_Eb_full_score.pdf`
- `天使的脸_Eb_parts.pdf`
- `parts/01_Flute.pdf` through `parts/18_Double_Bass.pdf`
- `parts/01_Flute.mscz` through `parts/18_Double_Bass.mscz`
- `previews/page-1.png` through `previews/page-8.png`

The retained Audiveris project is
`../../full_score_original_rebuilt/天使的脸_original_rebuilt.omr`.

## Original-score repair completed before transposition

### Solo Voice lyrics

- Restored all Chinese lyric text found on source pages 2–8.
- Lyrics are MuseScore lyric objects attached to vocal notes, not staff text.
- Preserved the two simultaneous verses in measures 12–32 and the single lyric
  line thereafter.
- Preserved the printed Chinese characters, note alignment, verse order, and
  visible melisma continuation.
- Final MusicXML contains 199 lyric objects.

### Harp

- Harp remains a native two-staff MuseScore Harp instrument.
- Preserved 42 native arpeggio endpoints in the MusicXML round trip.
- Restored the measure-33 `gliss.` as a native MuseScore Glissando with anchored
  start and destination notes; it round-trips as a MusicXML slide start/stop.
- Harp chords associated with the arpeggios and glissando were preserved.

### Other repaired notation

- Genuine 6:4 tuplets remain in measures 24, 33, and 45.
- Preserved repeats and first/second endings, dynamics, hairpins, ties, slurs,
  articulations, fermatas, clefs, barlines, tempo, and measure count.
- Preserved/restored technique and score text including `pizz.`, `arco`, `rit.`,
  and `小提琴 solo`.
- No notehead, stem, beam, flag, ledger-line, accidental, rest, or voice collision
  severe enough to impair reading was found in the final eight-page rendering.

## Native instrument definitions and written keys

| # | Instrument | Physical staves | Native MuseScore definition | Final written key/behavior |
|---:|---|---:|---|---|
| 1 | Flute | 1 | `wind.flutes.flute` | E-flat major |
| 2 | Oboe | 1 | `wind.reed.oboe` | E-flat major |
| 3 | B-flat Clarinet | 1 | `wind.reed.clarinet.bflat` | F major; chromatic transposition `-2` |
| 4 | Bassoon | 1 | `wind.reed.bassoon` | E-flat major |
| 5 | Horn in F 1 | 1 | `brass.french-horn` | B-flat major; chromatic transposition `-7` |
| 6 | Horn in F 2 | 1 | `brass.french-horn` | B-flat major; chromatic transposition `-7` |
| 7 | Timpani | 1 | `drum.timpani` | E-flat major, bass clef |
| 8 | Cymbals | 1 | `metal.cymbal.crash` | Native one-line percussion staff/PERC clef |
| 9 | Triangle | 1 | `metal.triangle` | Native one-line percussion staff/PERC clef |
| 10 | Glockenspiel | 1 | `pitched-percussion.glockenspiel` | E-flat major; sounds two octaves above |
| 11 | Vibraphone | 1 | `pitched-percussion.vibraphone` | E-flat major |
| 12 | Harp | 2 | `pluck.harp` | E-flat major, grand staff |
| 13 | Solo Voice | 1 | `voice.vocals` | E-flat major, vocal staff |
| 14 | Violin 1 | 1 | `strings.group` | E-flat major |
| 15 | Violin 2 | 1 | `strings.group` | E-flat major |
| 16 | Viola | 1 | `strings.group` | E-flat major, alto clef |
| 17 | Violoncello | 1 | `strings.group` | E-flat major, bass clef |
| 18 | Double Bass | 1 | `strings.group` | E-flat major; sounds one octave below |

The Triangle import regression found during final QA was corrected from a
generic strings definition back to the native `metal.triangle` definition.

## Transposition validation

- Original concert-pitch key verified from the pre-transposition score: B major.
- Destination concert-pitch key: E-flat major.
- Sounding interval applied: +4 semitones.
- 2,003 pitched note objects moved exactly +4 semitones.
- Six unpitched Cymbals/Triangle events were intentionally left unpitched.
- Final written key signatures verified:
  - C/concert-pitch instruments: E-flat major (`-3` fifths)
  - B-flat Clarinet: F major (`-1` fifth)
  - F Horns: B-flat major (`-2` fifths)
- Clarinet, Horn, Glockenspiel, and Double Bass transposition metadata is intact.
- Lyrics, rhythms, voices, rests, chord membership, ties, tuplets, articulations,
  arpeggios, and the Harp glissando were unchanged by transposition.

## Automated invariant results

- Pre-transposition repaired checkpoint: **PASS**
  - 18 parts
  - 54 measures per part
  - 199 lyrics
  - 42 Harp arpeggio endpoints
  - native Harp glissando start/stop
- Final skill MusicXML invariant checker: **PASS**
  - zero global findings
  - zero measure findings
- Exact transposition validator: **PASS**
  - all 2,003 pitched objects moved by the requested interval
  - rhythm/notation signatures unchanged
- Final package validator: **PASS**
  - 8 full-score pages
  - 18 individual part PDFs
  - 19 combined part pages
  - 8 full-score PNG previews

Supporting records:

- `../qa/MUSICXML_INVARIANTS_FINAL.md`
- `../qa/FINAL_PACKAGE_VALIDATION.json`

## Parts provenance and linkage

MuseScore Studio generated all 18 default parts directly from the final master
score. Each delivered part `.mscz` contains MuseScore `linkedTo` relationships
to the master score elements; the Harp part contains both linked staves. The
individual PDFs and combined parts PDF were rendered from those generated
MuseScore part scores, not from pages 9–28 of the old PDF.

MuseScore 4 materializes unopened default parts on demand. The master `.mscz`
therefore recreates the same default parts in the Parts dialog, while the
generated part `.mscz` files are retained alongside the PDFs as auditable linked
part artifacts.

## Visual engraving QA

The final full score was rendered to eight PNG previews and inspected page by
page. All 18 individual part first pages were also rendered and inspected.

Passed visual checks:

- noteheads attached to stems
- stems attached to beams; no floating beams
- flags positioned normally
- ties and slurs visually anchored
- ledger lines and accidentals readable
- 6:4 tuplets intact
- no visible missing or duplicated note objects caused by transposition
- no measure rhythm overflow or underflow found by the invariant checks
- repeat/ending structure retained
- Chinese lyrics legible and aligned in the score and Solo Voice part
- Harp arpeggios and measure-33 glissando visible and anchored
- no clipped systems in the full score or generated parts

## Discrepancies and human-review list

Confirmed pitch discrepancies introduced by repair/transposition: **none**.

Confirmed rhythm discrepancies introduced by repair/transposition: **none**.
The previously missing sextuplet ratios in measures 24, 33, and 45 had already
been corrected before this production pass and remain correct.

No measure is blocked by an unresolved ambiguity. Because the original source
was OMR-derived, the following remain recommended musician spot checks rather
than known errors:

- m3 Glockenspiel: completion rest and dense run
- m10–12 Flute/Oboe: high-register pitches and long slur endpoints
- m12–32 Solo Voice: two-verse lyric syllable placement
- m24, m33, m45: sextuplet pitches and endpoints
- m33 Harp: glissando origin/destination and associated chord
- m42–50 lower strings: `pizz.`/`arco` transitions
- m47–54: final vocal phrase, `rit.`, violin-solo text, and fermata anchors

These advisories do not indicate detected mismatches; they identify the most
musically consequential locations for an optional performer/editor proofread.

## Output integrity

| File | SHA-256 |
|---|---|
| `天使的脸_Eb_full_score.mscz` | `788187C7D0F73E969F373A4F342A575B8B725C73985CACD1E3B483D827A78144` |
| `天使的脸_Eb_full_score.musicxml` | `0288D2880D25533982376B8E38492EA6CEB67A1B5E85242217CCC0E895E59D29` |
| `天使的脸_Eb_full_score.pdf` | `F72CD72FA243E0999C4095AD5AA4901CD29B535CBA91D0C869352B853C6B0B94` |
| `天使的脸_Eb_parts.pdf` | `EADFF84EE457EC59660590BCB5071830DC9AB11107178CDAF94AEF8853FC27B9` |
