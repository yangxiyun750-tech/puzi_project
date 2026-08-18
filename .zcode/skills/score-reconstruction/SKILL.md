---
name: score-reconstruction-v2
description: Reconstruct professionally engraved printed scores from PDF using high-resolution rendering, Audiveris OMR, ScoreIR intermediate representation, MuseScore Studio cleanup, and semantic round-trip validation. Use when a printed full score or piano reduction must become an editable MuseScore score with a validated intermediate data model. Do not use for handwritten music, lead sheets, or pixel-faithful PDF editing.
---

# Score Reconstruction V2

Reconstruct notation as music data via a canonical ScoreIR model, validate round-trip semantics, and produce editable outputs.

## Core Principles

- The source PDF is read-only reference material.
- Never modify the original PDF or the raw OMR output.
- Never guess missing musical content (pitches, rhythms, chords, lyrics).
- Distinguish **SAFE_REPAIR** (structural fixes) from **MUSICAL_REPAIR** (requires human review).
- Prefer correct, readable notation over matching source pixels.
- Do not declare completion from successful OMR or export alone. Require semantic round-trip validation.

## Terminology (Critical)

| Term | Meaning | Example |
|---|---|---|
| **Part** | Instrument or performer | Flute, Piano, Horn in F |
| **Staff** | One physical five-line staff | Piano RH staff, Piano LH staff |
| **Voice** | Rhythmic voice layer *inside* a staff | Voice 1 = RH melody, Voice 2 = RH inner voice, Voice 5 = LH |
| **Vocal Part** | A *real* human-voice instrument | Soprano, Solo Voice, Choir |
| **Lyric** | Text under notes, only present if detected | Requires real `<lyric>` elements |

**Rules:**
- MusicXML `<voice>` is a **rhythmic layer**, never a vocal indicator.
- Piano, Violin, Flute, etc. may contain multiple `<voice>` layers for polyphonic notation.
- Do **not** assume every score has a Vocal Part or lyrics.
- Only enable **lyrics recovery** when real `<lyric>` elements or a Vocal Part are detected.
- All instrument-specific repair modules must be **dynamically enabled** based on actual detected instrumentation.

## Repair Classification

| Type | Description | Action |
|---|---|---|
| `SAFE_REPAIR` | XML structure errors, missing attributes, invalid divisions, metadata fixes | Auto-apply |
| `MUSICAL_REPAIR` | Missing pitches, rhythms, chords, lyrics, dynamics | Flag as `NEEDS_VISUAL_RECOVERY` |
| `NEEDS_VISUAL_RECOVERY` | Music content that cannot be determined from structure alone | Human review required |

## ScoreIR V1

Canonical intermediate representation between MusicXML and MuseScore.

- Every editable object has a stable ID: `PartID-MeasureNumber-VoiceID-EventIndex`
- Supports: Part, Staff, Measure, Voice, Note, Rest, Chord, Pitch, Duration, KeySignature, TimeSignature, Clef, Tempo, Dynamics, Articulation, Tie, Slur, Lyric
- EditHistory prepared for future Undo/Redo
- Round-trip validation ensures musical semantics are preserved

## Workflow

1. **Preserve source**: Copy PDF to `workdir/source/`.
2. **Render**: `pdftoppm -png -r 400 source.pdf workdir/rendered/page`
3. **OMR**: Audiveris batch → raw `.mxl` in `workdir/omr/`
4. **Import**: MusicXML → ScoreIR (`MusicXMLImporter`)
5. **Instrument Identity Resolution**: Resolve canonical instruments (`InstrumentIdentityResolver`)
6. **Safe repairs**: Structural fixes only (`apply_safe_repairs`)
7. **Export**: ScoreIR → MusicXML (`MusicXMLExporter`)
8. **Round-trip validation**: Re-import and compare semantics (`RoundtripValidator`)
9. **MuseScore**: Import MusicXML → `.mscz` → export PDF / MusicXML
10. **QA**: Generate reports, list all `NEEDS_VISUAL_RECOVERY` items

## Instrument Identity Resolution

Audiveris `instrument-name` is a **candidate only**, never the single source of truth.

### Evidence hierarchy (highest to lowest)

| Priority | Source | Reliability |
|---|---|---|
| 1 | PDF title / instrumentation text | Highest |
| 2 | Staff-left instrument name / abbreviation | High |
| 3 | Staff count and grouping (grand staff detection) | High |
| 4 | Clef (F4, G2, C3, PERC) | High |
| 5 | Pitch range (bass vs tenor vs alto vs soprano) | Medium |
| 6 | Key signature / transposition behavior | Medium |
| 7 | Note overlap with other parts (detects duplicates) | Medium |
| 8 | Audiveris instrument-name | Low |
| 9 | AI visual inspection of source PDF | Low (V2 placeholder) |

### Output format

Each Part receives:

```
canonical_instrument: <resolved name>
source_label: <what Audiveris called it>
confidence: high | medium | low
staff_count: <number of staves>
clef: <clef signature>
pitch_range: <low> – <high>
is_vocal: true | false
needs_verification: true | false
verification_reason: <why human review is needed>
evidence:
  - <evidence item 1>
  - <evidence item 2>
```

### Vocal detection rules

A Part is **genuine vocal** only if:
- Label is explicitly a vocal type (`Soprano`, `Alto`, `Tenor`, `Bass`, `Solo Voice`, `Choir`), OR
- Label is vocal-generic AND real `<lyric>` elements exist in the music

**NOT vocal**: `Voice Oohs` without lyrics, any instrumental part with `<voice>` rhythmic layers.

### Dynamic repair module activation

All instrument-specific repair modules (e.g., percussion staff fix, harp arpeggio detection, vocal lyric injection) must be **enabled dynamically** based on resolved instrument identities. Never hard-code a fixed instrumentation.

## Directory Structure

```
workdir/
  source/          # Original PDF (immutable)
  rendered/        # 400 DPI PNG pages
  omr/             # Audiveris playlist, .omr, raw .mxl
  score_ir/        # ScoreIR serialized form (future)
  repairs/         # Repair artifacts
  output/          # Final .mscz, .musicxml, .pdf
  qa/              # Validation reports, repair logs
```

## Validation

Round-trip validation compares:
- Part count, Staff count, Measure count
- Voice structure per measure
- Pitch (step, alter, octave)
- Duration (divisions, value)
- Rest vs Note
- Key signatures, Time signatures, Clefs
- Ties, Slurs, Dynamics, Articulations, Lyrics, Tempo

**PASS** = zero ERROR findings. **FAIL** = any ERROR.

## References

- `src/score_ir/score_ir.py` — Data model
- `src/musicxml/musicxml_to_score_ir.py` — MusicXML importer
- `src/musicxml/score_ir_to_musicxml.py` — MusicXML exporter
- `src/validation/roundtrip_validator.py` — Round-trip validator
- `src/reconstruction/reconstruction_pipeline.py` — End-to-end pipeline
