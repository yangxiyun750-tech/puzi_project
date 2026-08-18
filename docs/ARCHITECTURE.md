# Architecture Documentation

## Overview

The Score Engine is a deterministic pipeline for converting printed orchestral
scores (PDF) into editable digital formats (MusicXML, MuseScore) with
rigorous quality assurance.

## Core Principle

> "AI understands intent; the program executes deterministic edits."

- **AI layer**: Parses natural language, inspects visual evidence, returns
  structured recommendations. Never rewrites MusicXML directly.
- **Score Engine**: All musical modifications are deterministic code operations
  on the canonical ScoreIR intermediate representation.

## Module Structure

```
src/
├── score_engine/           # Core score processing
│   ├── score_ir/           # Canonical IR: Score → Part → Measure → Voice → Event
│   ├── musicxml/           # MusicXML import/export (lossless round-trip)
│   ├── validation/         # Instrument identity, round-trip validation
│   └── measure_locator.py  # Measure → PDF coordinate mapping
├── ai/                     # AI model invocation (STUB — reserved)
│   ├── __init__.py         # AIClient abstract base
│   ├── intent_parser.py    # Natural language → EditIntent (STUB)
│   └── visual_recovery.py  # Visual evidence → RecoveryResult (STUB)
├── qa/                     # Quality assurance pipeline
│   ├── qa_model.py         # QA status machine (PASS/SAFE_REPAIR/AI_REVIEW/HUMAN_REVIEW)
│   ├── pdf_qa.py           # Input PDF quality checks
│   ├── structure_qa.py     # OMR structure validation
│   ├── instrument_qa.py    # Instrument identity QA
│   ├── rhythm_qa.py        # Rhythm/meter validation
│   ├── notation_qa.py      # Notation object pairing
│   ├── lyrics_qa.py        # Lyrics validation (conditional)
│   ├── range_qa.py         # Transposition/range checks
│   ├── render_qa.py        # MuseScore render verification
│   ├── visual_qa.py        # Visual evidence generation
│   ├── fixer.py            # Deterministic SAFE_REPAIR fixes
│   ├── reporter.py         # QA_SUMMARY.json + QA_REPORT.md
│   ├── qa_pipeline.py      # Orchestrator
│   └── visual_recovery.py  # Legacy visual recovery (to be replaced by ai/)
├── reconstruction/         # End-to-end reconstruction pipeline
│   └── reconstruction_pipeline.py
└── ...
```

## Data Flow

```
PDF Input
    ↓
Poppler (pdftoppm @ 400 DPI)
    ↓
Audiveris OMR → Raw MusicXML
    ↓
MusicXMLImporter → ScoreIR (canonical IR)
    ↓
Instrument Identity Resolution
    ↓
QA Pipeline (10 stages)
    ↓
SafeFixer (deterministic structural fixes)
    ↓
MusicXMLExporter → Fixed MusicXML
    ↓
MuseScore → .mscz / .pdf / .musicxml
    ↓
QA Report + Delivery Gate
```

## Key Design Decisions

1. **ScoreIR is the single source of truth.** All edits go through ScoreIR.
2. **SAFE_REPAIR vs MUSICAL_REPAIR vs NEEDS_VISUAL_RECOVERY** are strictly
   separated. No silent musical fixes.
3. **Instrument identity is multi-evidence.** Audiveris label is only a
   candidate, never the sole source of truth.
4. **Voice ≠ Vocal Part.** Voice is a rhythmic layer; Vocal Part is a human
   voice instrument.
5. **AI never rewrites MusicXML.** AI returns structured intent; the Score
   Engine executes deterministic edits.

## Reserved for Future Development

- `src/ai/` — AI model invocation (intent parsing, visual recovery)
- `web_api/` — HTTP/WebSocket API for enterprise deployment
- `frontend/` — Mini-program / web UI
- `rules/` — Music theory rules (transposition, ranges, clefs)
- `benchmark/` — Accuracy and performance testing
- `licensing/` — Third-party license compliance
- `logs/` — Structured operation logs
