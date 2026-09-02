# Multilingual Title and Music Metadata

Use this reference during intake, before choosing filenames or creating the library entry, and again during final export verification.

## Evidence order

Read title-page, cover, first-score-page, movement-heading, and credit text in this order:

1. embedded PDF text with its Unicode characters and page coordinates;
2. OCR configured for the scripts/languages actually visible on the page;
3. a verified vision provider when text extraction and OCR are absent or conflict;
4. a short human question when a meaningful field remains uncertain.

Never transliterate first and treat the result as source text. Preserve exact visible text, punctuation, diacritics, capitalization, CJK characters, and contributor order. OCR output is a proposal until it agrees with the rendered page or a human confirms it. Record conflicting readings instead of silently selecting one.

## Record model

Create `qa/source_metadata.json` with `scripts/metadata_record.py`. Each value carries its evidence method, page/location, language tag, script, confidence, and confirmation status.

Title kinds are `original`, `subtitle`, `alternate`, `translated`, `romanized`, and `supplied` (only when no title is printed). Contributor roles include composer, arranger, lyricist, editor, translator, orchestrator, and publisher. Music-information fields include opus/catalog number, movement, dedication, tempo text, instrumentation, lyric language, source pitch convention, and verified source concert key.

Use BCP-47 language tags when known and ISO 15924 script codes when useful. `und` and `Zyyy` are acceptable while unknown. Do not translate names, titles, tempo terms, or dedications unless the translation is separately identified.

## Confirmation gate

`METADATA_STATUS = PASS` requires one confirmed `original` or explicitly `supplied` display title, source evidence for retained values, and resolution of conflicts affecting identity, filename, catalog grouping, rights, movement order, source key, or pitch convention.

Low-confidence or conflicting items go into the human review queue with category `metadata`. Ask at most three related questions per turn and show the page crop when available.

## Propagation and verification

Use the confirmed original title as the default display title. Keep translated and romanized titles as aliases unless the user chooses one for display. Derive a filesystem-safe basename separately; never alter the metadata record to accommodate filename restrictions.

Copy confirmed title, subtitle, movement, and contributor roles into native MuseScore/MusicXML fields where supported. After export, compare the reopened `.mscz`, MusicXML `<work>`, `<movement-title>`, `<creator type=...>`, and title-page credits with the metadata record. Missing or changed confirmed values block delivery unless the user accepts a documented format limitation.

Metadata supports discovery and cataloging; it never substitutes for musical verification of key, pitch convention, instrumentation, or movement structure.
