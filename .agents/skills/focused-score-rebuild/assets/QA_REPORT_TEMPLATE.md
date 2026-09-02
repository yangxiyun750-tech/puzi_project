# QA Report — Focused Score Rebuild

## Status and project contract

- Overall: `IN PROGRESS | REVIEW REQUIRED | PASS`
- `QA_STATUS`: `PASS | PASS_WITH_DEFERRED_COSMETIC_ITEMS | REVIEW_REQUIRED | BLOCKED`
- Work: `<title>`
- Original title/language/script: `<value / BCP-47 / ISO 15924>`
- Display title and aliases: `<display / translated / romanized>`
- Confirmed contributors and roles: `<names / roles / evidence>`
- Source metadata record: `<qa/source_metadata.json>`
- `METADATA_STATUS`: `<PASS | REVIEW_REQUIRED>`
- Source PDF: `<path>`
- Supported score family: `<melody | voice_piano | wind_band_basic>`
- Eligible score pages: `<range>`
- `INPUT_STATUS`: `<PASS | NEEDS_RESCAN | OUT_OF_SCOPE>`
- Page-level source-quality findings: `<evidence>`
- Cover/blank/legacy-part pages excluded from OMR: `<range/status/not applicable>`
- Source score convention: `<concert pitch | written pitch | mixed>`
- Verified source concert key: `<key>`
- Transposition requested: `<yes/no>`
- Destination concert key and spelling: `<key/not applicable>`
- Directed sounding interval: `<interval/not applicable>`
- Review mode: `<guided | fast | expert>`
- Reviewer/date: `<name/date>`
- Catalog: `<library/catalog.json>`
- Classification log: `<library/classification_decisions.jsonl>`
- Collection(s): `<names/not assigned>`
- Classification status: `<CLASSIFIED | NEEDS_ANSWERS | SOURCE_BLOCKED | OUT_OF_SCOPE | RIGHTS_REVIEW_REQUIRED>`

## Tool and capability record

| Tool/capability | Version/provider | Command/settings/evidence | Result |
|---|---|---|---|
| Poppler/pdftoppm |  | 400 DPI PNG |  |
| Audiveris |  | batch, transcribe, export, save |  |
| MuseScore Studio |  | import/engraving/export |  |
| Structural audit |  | MusicXML report |  |
| Visual review |  | source/render comparison |  |
| Human review fallback |  | reviewer/decision log |  |

## Source and page inventory

| Original PDF page | Printed page | Systems | Measures | Staves expected | Evidence/notes | Status |
|---:|---:|---:|---|---:|---|---|
|  |  |  |  |  |  |  |

## Instrument and transposition map

| Order | Source staff label | MuseScore instrument definition | Staff/Part transposition | Source pitch check | Final written key | Sounding/written spot check | Status |
|---:|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

- [ ] Source concert key and pitch convention are verified, not assumed.
- [ ] Every staff uses the intended real MuseScore definition.
- [ ] Every transposing, octave-transposing, keyless, percussion, and instrument-change staff is checked.
- [ ] If transposed, sounding pitches and written keys match the requested destination and spelling.

## Structural invariants

| Invariant | Original-key baseline | Candidate/final | Status/notes |
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

## Human review queue

- Queue: `<qa/review_queue.json>`
- Decision log: `<qa/decisions.jsonl>`
- Summary: `<qa/review_summary.md>`

| Issue ID | Page/system | Measure | Instrument/staff | Category | Severity | Decision | Verification evidence | Status |
|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |

- [ ] Questions were asked only after source, rebuilt score, validators, and available secondary evidence were checked.
- [ ] Every accepted correction was applied to native notation and then verified.
- [ ] No resolved question is repeated after resuming the task.
- [ ] No blocking or important issue remains unresolved.
- [ ] Any deferred issue is cosmetic and explicitly accepted by the user.

## Page-by-page source validation

| PDF page | Pitch mode | Pitches/rhythm | Text/lyrics | Spanners/marks | Structure | Evidence | Status |
|---:|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

## Final engraving QA

- [ ] Noteheads attach to correct stems; stems attach correctly to beams.
- [ ] No floating beams or displaced flags.
- [ ] Ties connect intended identical pitches; slurs have correct anchors.
- [ ] Ledger lines, accidentals, dots, tuplets, rests, and voices are correct.
- [ ] No missing/duplicated notes or unexplained rhythmic overflow/underflow.
- [ ] Dynamics, articulations, tempo, lyrics, repeats/endings, and rehearsals remain intact.
- [ ] The score and any applicable linked parts are professionally engraved.
- [ ] Every part has readable spacing, practical page turns, and no collisions.
- [ ] Final score PNGs were visually compared with the source.

## Part export inventory

| Order | Linked MuseScore part | Individual PDF | Pages | Opens | Written-pitch QA | Layout/page-turn QA | Status |
|---:|---|---|---:|---|---|---|---|
|  |  |  |  |  |  |  |  |

- [ ] Combined parts PDF contains all and only intended parts.
- [ ] No old PDF part was separately transposed or delivered as a rebuilt part.

## Deliverables

| Deliverable | Exists/nonzero | Opens | Matches reviewed revision | Notes |
|---|---|---|---|---|
| `<basename>_full_score.mscz` |  |  |  |  |
| `<basename>_full_score.musicxml` |  |  |  |  |
| `<basename>_full_score.pdf` |  |  |  |  |
| `<basename>_parts.pdf` |  |  |  |  |
| Individual part PDFs |  |  |  |  |
| Audiveris `.omr` retained |  |  |  |  |

## Sign-off

- Open blocking/important findings: `<count>`
- Deferred cosmetic findings: `<count>`
- Unexplained structural differences: `<count>`
- Final decision: `PASS | PASS_WITH_DEFERRED_COSMETIC_ITEMS | REVIEW REQUIRED`
- Notes: `<limitations or confirmation>`
