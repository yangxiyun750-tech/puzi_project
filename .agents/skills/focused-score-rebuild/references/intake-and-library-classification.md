# Input Eligibility and Library Classification

Use this reference before OMR and whenever a work is added to or regrouped in the local catalog.

## Supported score families

- `melody`: one primarily monophonic melodic staff or part.
- `voice_piano`: one solo vocal line with lyrics and a basic two-staff piano accompaniment.
- `wind_band_basic`: a conventional basic concert-band full score whose instruments, rhythms, voices, and percussion can be represented directly in MuseScore.
- `out_of_scope`: orchestral, handwritten/draft, lead-sheet-only, graphic/aleatoric, highly complex contemporary, dense divisi/cross-staff/polyphonic, or otherwise unsupported notation.

If the score does not clearly fit one supported family, ask one focused question. Do not choose the closest family merely to make processing continue.

## PDF eligibility gate

Inspect all pages intended for recognition at normal view and enlarged view after rendering. Record page-level evidence for:

- complete pages, systems, staves, clefs, key/time signatures, and margins;
- sharp staff lines, noteheads, stems, beams, flags, dots, accidentals, tuplets, and lyric characters;
- correct orientation with no material skew or camera perspective;
- even lighting and contrast with no shadow, glare, bleed-through, moire, or compression blocks over notation;
- no draft marks, handwritten replacement notes, pasted corrections, watermarks, stamps, or annotations touching music;
- consistent readable resolution across every page.

Statuses:

- `eligible`: all intended pages are reliable enough for OMR and page-by-page human comparison;
- `needs_rescan`: a cleaner scan/export could plausibly fix the problem;
- `unsupported_source`: the source is handwritten, draft/graphic notation, materially incomplete, or cannot become reliable through rescanning.

Do not average page quality: one unreadable required page blocks the complete job. Tell the user exactly which pages failed and how to rescan: flat page, straight-on capture or scanner, full margins, grayscale/color without aggressive compression, and enough resolution to preserve the smallest notation and lyrics.

## Question-driven classification

Keep the exchange short. Ask no more than three related questions in one turn. Reuse answers already visible in the score or supplied by the user.

Required catalog fields:

1. `score_type`: `melody`, `voice_piano`, `wind_band_basic`, or `out_of_scope`;
2. `source_quality`: `eligible`, `needs_rescan`, or `unsupported_source`;
3. `genre`: user-facing style/genre, such as folk song, art song, pop, educational, march, or film music;
4. `purpose`: practice, teaching, rehearsal, performance, arranging, audition, or archive;
5. `difficulty`: `beginner`, `intermediate`, `advanced`, or `unknown`;
6. `instrumentation`: concise human-readable forces;
7. `rights_status`: `owned`, `licensed`, `public_domain`, `permission_confirmed`, or `unknown`.

Optional fields are `language` and free-form `tags`. Do not infer copyright permission. An `unknown` rights status may be cataloged but must not enter reconstruction until the user confirms authorization.

Suggested guided batches:

- Batch 1: confirm score family, intended use, and rights status.
- Batch 2: confirm genre/style, difficulty, and concise instrumentation.
- Batch 3 only if useful: language, tags, and which named collection(s) should contain the work.

Use natural language. The user never needs to type script commands.

## Local catalog and collections

Initialize private state with:

```text
python scripts/library_catalog.py init --catalog library/catalog.json
python scripts/library_catalog.py start --catalog library/catalog.json --work-id <id> --title <title> --source-pdf <path>
python scripts/library_catalog.py questions --catalog library/catalog.json --work-id <id> --limit 3
```

Record each confirmed answer with `answer`. The script appends an audit event to `library/classification_decisions.jsonl`. Use `collection-add` to create a named related-work library and `assign` only after the user confirms the grouping. Use `similar` to propose nearby entries; similarity is a metadata hint, not a musical conclusion.

Catalog status is deterministic:

- `NEEDS_ANSWERS`: required classification fields remain unanswered;
- `SOURCE_BLOCKED`: source quality is not eligible;
- `OUT_OF_SCOPE`: score family is unsupported;
- `RIGHTS_REVIEW_REQUIRED`: authorization is unresolved;
- `CLASSIFIED`: the entry may proceed, subject to environment and musical QA gates.

Keep the catalog in the user's private workspace. Store file paths or identifiers, not embedded PDF/image bytes. Do not commit private titles, paths, or metadata unless the user deliberately publishes them.
