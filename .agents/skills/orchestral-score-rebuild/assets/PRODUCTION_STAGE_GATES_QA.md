# Production Stage-Gate QA Supplement

Copy these sections into the project QA report. They preserve successful requirements that previously existed only in conversation history.

## Production stage gates

| Gate | Evidence | Result |
|---|---|---|
| 0. Source and executable readiness | exact paths, versions, invocation logs | `PASS / STOP` |
| 1. Original-key two-page prototype | `.omr`, MusicXML, MuseScore, source comparison |  |
| 2. Real instrument definitions | staff map and transposition metadata |  |
| 3. Complete original-key reconstruction | full-score page and measure audit |  |
| 4. Native semantic-object repair | Lyrics, Arpeggio, Glissando, special notation |  |
| 5. Verified pre-transposition checkpoint | reopened `.mscz` and baseline MusicXML |  |
| 6. Concert-key transposition | concert/written checks and invariants |  |
| 7. Linked parts and layout | part inventory and visual QA |  |
| 8. Save-close-reopen persistence | reopened master and linked parts |  |
| 9. MusicXML round trip/downstream export | every export reopened in MuseScore |  |

## Native-object and persistence checks

- [ ] Chinese text is stored as native Lyrics objects, anchored to correct vocal notes, with verses and melismas preserved.
- [ ] Harp rolled chords use native Arpeggio objects with correct chord anchors.
- [ ] Harp glissandi use native Glissando objects with correct start and destination anchors.
- [ ] No ambiguous pitch, rhythm, voice, tie/slur, lyric, or Harp object was silently guessed.
- [ ] The saved master was closed and reopened; native objects, instrument definitions, transposition, linked parts, and layout persisted.
- [ ] Every requested MusicXML export was reopened in MuseScore and passed pitch, rhythm, measure-count, key, transposition, lyric, repeat, dynamic, tuplet, and Harp-object checks.

## Capability record

| Capability | Provider/reviewer | Evidence | Result |
|---|---|---|---|
| `code_reasoning_provider` |  | command/script/XML review log |  |
| `visual_review_provider` |  | source/rendered image comparison |  |
| deterministic validators |  | reports/self-tests |  |
| `human_review_fallback` |  | reviewer and decisions |  |
