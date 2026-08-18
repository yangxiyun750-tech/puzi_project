# QA Report — Orchestral Score Rebuild

## Status

- Overall: `IN PROGRESS | REVIEW REQUIRED | PASS`
- Work: `天使的脸`
- Source PDF: `<path>`
- Source full-score pages: `<range>`
- Old part pages excluded from OMR: `<range/status>`
- Source concert key: `B major`
- Destination concert key: `E-flat major`
- Directed sounding interval: `+4 semitones`
- Source score convention: `<concert pitch | written pitch | mixed>`
- Reviewer/date: `<name/date>`

## Tool record

| Tool | Version | Command/settings | Result |
|---|---|---|---|
| Poppler/pdftoppm |  | 400 DPI PNG |  |
| Audiveris |  | batch, transcribe, export, save |  |
| MuseScore Studio |  | import/engraving/export |  |
| Structural audit |  | baseline vs final MusicXML |  |

## Source and page inventory

| Original PDF page | Printed page | Systems | Measures | Staves expected | Status | Evidence/notes |
|---:|---:|---:|---|---:|---|---|
|  |  |  |  |  |  |  |

## Instrument and transposition map

| Order | Source staff label | MuseScore instrument definition | Staff/Part transposition | Source pitch check | Final written key | Sounding/written spot check | Status |
|---:|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

- [ ] Concert pitch is B major before transposition.
- [ ] Final concert pitch is E-flat major.
- [ ] Sounding pitches moved +4 semitones.
- [ ] C instruments show E-flat major written.
- [ ] B-flat clarinet shows F major written.
- [ ] F horn shows B-flat major written.
- [ ] Every other transposing, octave-transposing, keyless, percussion, and instrument-change staff uses its MuseScore definition correctly.

## Structural invariants

| Invariant | Baseline | Final | Status/notes |
|---|---:|---:|---|
| Part/staff order and count |  |  |  |
| Bar count |  |  |  |
| Pickup/irregular measures |  |  |  |
| Meter changes |  |  |  |
| Repeats/endings/jumps |  |  |  |
| Tempo/rehearsal marks |  |  |  |
| Dynamics/hairpins |  |  |  |
| Articulations/ornaments |  |  |  |
| Tuplets |  |  |  |
| Ties/slurs |  |  |  |
| Lyrics |  |  |  |

Structural-audit report: `<path>`

## Suspicious measures

| ID | PDF page | System | Measure | Instrument/staff | Severity | Observation | Resolution/evidence | Status |
|---:|---:|---:|---:|---|---|---|---|---|
| 1 |  |  |  |  |  |  |  | OPEN |

## Page-by-page source validation

| PDF page | Pitch mode | Pitches/rhythm | Text/lyrics | Spanners/marks | Structure | Evidence | Status |
|---:|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

## Final engraving QA

- [ ] Noteheads attach to correct stems; stems attach correctly to beams.
- [ ] No floating beams or displaced flags.
- [ ] Ties connect intended identical pitches; slurs have correct anchors.
- [ ] Ledger lines and accidentals are correct and collision-free.
- [ ] Tuplets remain complete and legible.
- [ ] No missing or duplicated notes.
- [ ] No unexplained rhythmic overflow or underflow.
- [ ] Dynamics, articulations, tempo, lyrics, repeats/endings, and rehearsals remain intact.
- [ ] Full score and linked parts are professionally engraved.
- [ ] Every part has readable spacing, practical page turns, and no collisions.
- [ ] Final score PNGs were visually compared with the source.

## Part export inventory

| Order | Linked MuseScore part | Individual PDF | Pages | Opens | Written-pitch QA | Layout/page-turn QA | Status |
|---:|---|---|---:|---|---|---|---|
|  |  |  |  |  |  |  |  |

- [ ] `天使的脸_Eb_parts.pdf` contains all parts in order and excludes the conductor score.
- [ ] No old PDF part was separately transposed or delivered.

## Deliverables

| Deliverable | Exists/nonzero | Opens | Matches reviewed revision | Notes |
|---|---|---|---|---|
| `天使的脸_Eb_full_score.mscz` |  |  |  |  |
| `天使的脸_Eb_full_score.musicxml` |  |  |  |  |
| `天使的脸_Eb_full_score.pdf` |  |  |  |  |
| `天使的脸_Eb_parts.pdf` |  |  |  |  |
| Individual part PDFs |  |  |  |  |
| Audiveris `.omr` retained |  |  |  |  |

## Sign-off

- Open high-severity findings: `<count>`
- Unexplained structural differences: `<count>`
- Final decision: `PASS | REVIEW REQUIRED`
- Notes: `<limitations or confirmation>`
