# Production Stage-Gate QA Supplement

Copy these sections into the private project QA report.

## Production stage gates

| Gate | Evidence | Result |
|---|---|---|
| 0. Source and executable readiness | paths, versions, invocation logs | `PASS / STOP` |
| Intake. PDF eligibility | page-level clarity/completeness evidence and `INPUT_STATUS` | `PASS / NEEDS_RESCAN / OUT_OF_SCOPE` |
| Metadata. Multilingual title/music information | source metadata record, evidence locations, export comparison | `PASS / REVIEW_REQUIRED` |
| Catalog. Question-driven classification | catalog entry, decision log, collection confirmation |  |
| 1. Original-key prototype | `.omr`, MusicXML, MuseScore, source comparison |  |
| 2. Real instrument definitions | staff map and transposition metadata |  |
| 3. Complete original-key reconstruction | page and measure audit |  |
| 4. Native semantic-object repair | Lyrics, Arpeggio, Glissando, special notation |  |
| 5. Human verification dialogue | queue, decisions, evidence, verified corrections |  |
| 6. Verified original-key checkpoint | reopened `.mscz` and baseline MusicXML |  |
| 7. Optional concert-key transposition | concert/written checks and invariants |  |
| 8. Linked parts and layout when applicable | part inventory and visual QA |  |
| 9. Persistence and MusicXML round trip | reopened master, parts, and exports |  |

## Human review record

- Review mode: `guided / fast / expert`
- Queue: `<path>`
- Decision log: `<path>`
- `QA_STATUS`: `PASS / PASS_WITH_DEFERRED_COSMETIC_ITEMS / REVIEW_REQUIRED / BLOCKED`
- [ ] Every blocking/important decision was applied to native notation and verified.
- [ ] Only explicitly accepted cosmetic items are deferred.
- [ ] A resumed Agent can continue from the queue without repeating resolved questions.

## Native-object and persistence checks

- [ ] Lyrics use native Lyrics objects with correct notes, verses, punctuation, and melismas.
- [ ] Rolled chords use native Arpeggio objects with correct chord anchors.
- [ ] Glissandi use native Glissando objects with correct start and destination anchors.
- [ ] No ambiguous musical content was silently guessed.
- [ ] Save-close-reopen preserved native objects, instruments, optional transposition, linked parts, and layout.
- [ ] Requested MusicXML exports reopened in MuseScore and passed structural and written-pitch checks.

## Capability record

| Capability | Provider/reviewer | Evidence | Result |
|---|---|---|---|
| code reasoning |  | command/script/XML review log |  |
| visual review |  | source/rendered image comparison |  |
| deterministic validators |  | reports/self-tests |  |
| human review fallback |  | reviewer and decision log |  |
