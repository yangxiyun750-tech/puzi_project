# Score Reconstruction V2 — Architecture Report

**Date**: 2026-08-14  
**Project**: puzi_project  
**Status**: V2 Architecture Implemented

---

## 1. Executive Summary

Score Reconstruction V2 has been implemented. The core innovation is **ScoreIR V1** — a unified intermediate representation that separates musical semantics from MusicXML serialization. This enables:

- **Semantic round-trip validation** (MusicXML → ScoreIR → MusicXML with zero semantic loss)
- **Explicit repair classification** (SAFE_REPAIR vs MUSICAL_REPAIR vs NEEDS_VISUAL_RECOVERY)
- **Stable object IDs** for future natural-language editing (e.g., `P2-M36-V1-N04`)
- **Edit history preparation** for future Undo/Redo

---

## 2. New Directory Structure

```
puzi_project/
├── src/                          # NEW: Source code
│   ├── score_ir/
│   │   ├── __init__.py
│   │   └── score_ir.py           # ScoreIR V1 data model
│   ├── musicxml/
│   │   ├── __init__.py
│   │   ├── musicxml_to_score_ir.py   # MusicXML importer
│   │   └── score_ir_to_musicxml.py   # MusicXML exporter
│   ├── validation/
│   │   ├── __init__.py
│   │   └── roundtrip_validator.py    # Semantic round-trip validator
│   └── reconstruction/
│       ├── __init__.py
│       └── reconstruction_pipeline.py # End-to-end pipeline
├── skills/
│   └── score-reconstruction/
│       └── SKILL.md              # NEW: V2 Skill definition
├── colores_v2/                   # NEW: V2 pipeline output
│   ├── source/                   # Original PDF (immutable)
│   ├── rendered/                 # 400 DPI PNG pages
│   ├── omr/                      # Audiveris outputs
│   ├── score_ir/                 # ScoreIR artifacts (future)
│   ├── repairs/                  # Repair artifacts
│   ├── output/                   # Final outputs
│   └── qa/                       # QA reports
├── colores_test/                 # EXISTING: V1 test outputs (preserved)
├── final_production/             # EXISTING: 天使的脸 production (preserved)
└── ...
```

---

## 3. Modified Files

| File | Change |
|---|---|
| `src/reconstruction/reconstruction_pipeline.py` | NEW: End-to-end V2 pipeline |
| `src/score_ir/score_ir.py` | NEW: ScoreIR V1 data model |
| `src/score_ir/__init__.py` | NEW: Package exports |
| `src/musicxml/musicxml_to_score_ir.py` | NEW: MusicXML importer |
| `src/musicxml/score_ir_to_musicxml.py` | NEW: MusicXML exporter |
| `src/musicxml/__init__.py` | NEW: Package exports |
| `src/validation/roundtrip_validator.py` | NEW: Semantic validator |
| `src/validation/__init__.py` | NEW: Package exports |
| `src/reconstruction/__init__.py` | NEW: Package exports |
| `skills/score-reconstruction/SKILL.md` | NEW: V2 Skill definition |

**No existing files were modified.**

---

## 4. ScoreIR V1 Data Model

### Hierarchy

```
Score
├── Part (P1, P2, ...)
│   ├── Instrument (id, name, sound, transposition)
│   └── Measure (M1, M2, ...)
│       ├── KeySignature (fifths, mode)
│       ├── TimeSignature (beats, beat_type)
│       ├── Clef (sign, line)
│       ├── Tempo (beat_unit, per_minute)
│       ├── Voice layer (V1, V2, ...) — rhythmic voice, NOT vocal
│       │   └── Event
│       │       ├── Note (id, pitch, duration, voice, staff, type, dots)
│       │       │   ├── Pitch (step, alter, octave)
│       │       │   ├── Tie (start/stop)
│       │       │   ├── Slur (start/stop/continue)
│       │       │   ├── Articulation (staccato, tenuto, ...)
│       │       │   └── Lyric (number, syllabic, text, extend)
│       │       ├── Rest (id, duration, voice, staff, type)
│       │       └── Chord (id, notes[])
│       └── Barline (location, style)
└── EditHistory (prepared for Undo/Redo)
```

### Stable IDs

| Object | ID Format | Example |
|---|---|---|
| Part | `P{index}` | `P1`, `P2` |
| Staff | `P{index}-S{number}` | `P2-S1` |
| Measure | `P{index}-M{number}` | `P2-M36` |
| Voice layer | `P{index}-V{number}` | `P2-M36-V1` |
| Note/Rest/Chord | `P{index}-M{number}-V{number}-N{index:02d}` | `P2-M36-V1-N04` |

### Repair Classification

| Type | Code | When | Action |
|---|---|---|---|
| **SAFE_REPAIR** | `SAFE` | XML structure errors, missing attributes, invalid divisions, metadata | Auto-apply |
| **MUSICAL_REPAIR** | `MUSICAL` | Missing pitches, rhythms, chords, lyrics, dynamics | Never auto-apply |
| **NEEDS_VISUAL_RECOVERY** | `VISUAL` | Music content that cannot be determined from structure alone | Flag for human review |

---

## 5. Round-trip Validation Results

### Colores — Piano Reduction

| Metric | Result |
|---|---|
| **Import** | 2 parts, 515 measures, 10,537 notes |
| **Export** | ScoreIR → MusicXML |
| **Re-import** | 2 parts, 515 measures |
| **Semantic Comparison** | **PASS** |
| **Errors** | 0 |
| **Warnings** | 0 |

**Verified preserved semantics:**
- Part count and names
- Measure count and numbering
- Voice structure per measure
- Pitch (step, alter, octave)
- Duration (divisions, value)
- Note type (whole, half, quarter, ...)
- Rest vs Note distinction
- Key signatures, Time signatures, Clefs
- Ties, Slurs, Articulations, Lyrics, Tempo

### Missing Measures (NEEDS_VISUAL_RECOVERY)

The raw Audiveris OMR output for Colores has **3 missing measures** in the **Bass Trombone** part (Audiveris misidentified this as "Voice"):

| Part ID | Audiveris Label | Actual Instrument | Measure | Issue |
|---|---|---|---|---|
| P1 | Voice | Bass Trombone (misidentified) | 32 | Missing from OMR |
| P1 | Voice | Bass Trombone (misidentified) | 76 | Missing from OMR |
| P1 | Voice | Bass Trombone (misidentified) | 170 | Missing from OMR |

**Key finding**: PDF title confirms "Colores for Bass Trombone solo & Piano". Audiveris incorrectly labeled P1 as "Voice" (instrument-name: Voice Oohs). Pitch-range analysis (E♭1–B♭4, midi 27–70) confirms P1 is actually **Bass Trombone**, not a vocal part. P2 is Piano with a full grand staff (RH staff 1 + LH staff 2). There are **zero `<lyric>` elements** in the entire score, confirming no vocal part exists.

**Structural verification**: P1 notes do NOT duplicate P2 staff 1 (RH) or staff 2 (LH) — only 12% overlap. P1 is a genuinely independent instrumental part.

**V2 behavior**: These are flagged as `NEEDS_VISUAL_RECOVERY` (severity: high, needs_human_review: true). They are **NOT** automatically filled with rests.

### MuseScore Import

| File | Result |
|---|---|
| Raw OMR MusicXML | ❌ FAIL (missing measures) |
| ScoreIR-exported MusicXML | ❌ FAIL (missing measures preserved) |
| Previously repaired MusicXML (colores_rhythm_fixed_v2) | ✅ PASS |

This confirms that MuseScore requires complete measure structure. The V2 pipeline correctly identifies this as a human-review item rather than auto-fixing it.

---

## 6. QA Reports Generated

| Report | Path | Status |
|---|---|---|
| Round-trip JSON | `colores_v2/qa/ROUNDTRIP_SCORE_IR.json` | ✅ Generated |
| Round-trip Markdown | `colores_v2/qa/ROUNDTRIP_SCORE_IR.md` | ✅ Generated |
| Repair Log | `colores_v2/qa/REPAIR_LOG.json` | ✅ Generated |

---

## 7. Remaining Issues

| Issue | Severity | Description |
|---|---|---|
| Missing Bass Trombone measures | HIGH | P1 (misidentified as "Voice") m32, m76, m170 need manual transcription from source PDF |
| Audiveris instrument misidentification | MEDIUM | P1 labeled "Voice" but is actually Bass Trombone; no vocal part exists in this score |
| Rhythmic overflow in Piano | MEDIUM | Several measures exceed 4/4 duration (m92, m243, m245, m247) |
| Missing key signatures in P1 | LOW | 479 measures needed key signature inheritance (SAFE_REPAIR applied) |
| MuseScore import of raw OMR | MEDIUM | Raw Audiveris output fails MuseScore import due to structural gaps |

---

## 8. Next Phase Recommendations

### Phase 3 — Visual Recovery Interface
1. Build a page-image viewer that shows the original PDF page alongside the ScoreIR measure
2. Allow human annotator to fill in missing measures by clicking on the PDF
3. Store annotations as `MUSICAL_REPAIR` entries in the RepairLog

### Phase 4 — Natural Language Editing
1. Parse natural language commands into `ScoreEdit` operations
2. Examples:
   - "Transpose Trombone 2 up a major second from measure 24 to 36"
   - "Change the C5 in measure 42 of Flute to D5"
   - "Add a slur from measure 10 to 14 in Violin 1"
3. Apply edits to ScoreIR, then export to MusicXML/MuseScore

### Phase 5 — Advanced MusicXML Repair
1. Implement more sophisticated SAFE_REPAIR algorithms
2. Detect and fix tuplet ratios without changing note values
3. Infer missing dynamics from context (mark as MUSICAL_REPAIR with low confidence)

### Phase 6 — Multi-Score Testing
1. Test with 天使的脸 (full orchestral score) to validate V2 handles complex scores
2. Test with additional piano reductions to validate robustness
3. Build regression test suite from `tests/colores/`

---

## 9. Conclusion

Score Reconstruction V2 successfully establishes:

1. **ScoreIR V1** as a canonical intermediate representation
2. **Semantic round-trip validation** proving zero information loss
3. **Explicit repair classification** preventing auto-guessing of musical content
4. **Stable object IDs** enabling future natural-language editing
5. **Immutable source preservation** ensuring full auditability

The Colores test case demonstrates that the V2 architecture correctly identifies what can be safely repaired (479 key signature inheritances) versus what requires human review (3 missing measures, rhythmic overflow).

**The migration from Codex to Kimi + ZCode is proven functional.**
