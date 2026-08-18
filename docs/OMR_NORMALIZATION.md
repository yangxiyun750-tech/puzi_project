# OMR Validation / Recovery / Normalization Layer

## 1. Purpose

The OMR Validation / Recovery / Normalization Layer sits between the raw Audiveris OMR output and the Score Engine. It is responsible for:

- Detecting structural defects in raw OMR MusicXML.
- Classifying every defect as either a deterministic fix or a human/AI review item.
- Producing a provenance trace for every finding.
- Emitting a normalized MusicXML only when deterministic fixes are safe.
- Never overwriting the raw OMR source.

The layer does **not** guess musical content. If a missing measure, an overflow, or an underflow cannot be resolved deterministically, it is reported as unresolved.

## 2. Design Principles

1. **Raw MusicXML is immutable.** The layer reads raw files and writes new files under a separate prefix/path.
2. **No score-specific logic.** Detectors operate only on MusicXML structure and music-theory invariants (measure duration, divisions, voice layering, notation pairing).
3. **No measure-number whitelists.** Detectors never contain references to M172, M92, Colores, or fixed part IDs.
4. **Fix only what is provably correct.** Current deterministic fixes are limited to:
   - Forward elements that can be safely converted to explicit rests without changing measure totals.
5. **Everything else is reported.** Overflow, underflow, missing measures, empty measures, unpaired notations, and ambiguous divisions changes become `OMRIssue` records with classification and severity.

## 3. Position in Data Flow

```
PDF Input
    ↓
Poppler @ 400 DPI
    ↓
Audiveris OMR → Raw MusicXML  (immutable)
    ↓
OMRNormalizer
    - detect
    - classify
    - deterministic fix (when provably safe)
    - report
    ↓
Normalized MusicXML + OMR_ISSUE_REPORT.json
    ↓
OMRQualityGate
    - STRICT: block if unresolved blocking_for_edit issues remain
    - PERMISSIVE: allow degraded editing with warnings
    ↓
MusicXMLImporter → ScoreIR
    ↓
QA Pipeline / SafeFixer / Score Engine
    ↓
Deliverables
```

`MusicXMLImporter` remains unchanged. The normalizer and quality gate are optional preprocessing wrappers.

## 4. Issue Schema

See `src/omr_normalization/issue_model.py` for the canonical Python dataclasses.

Every issue carries:

| Field | Description |
|---|---|
| `issue_id` | Unique deterministic ID |
| `category` | `rhythm`, `structure`, `divisions`, `notation`, `voice` |
| `check` | Specific check name |
| `status` | `omr_error`, `safe_fix_applied`, `needs_review`, `info` |
| `severity` | `high`, `medium`, `low`, `info` |
| `edit_safety` | `blocking_for_edit`, `non_blocking`, `informational` |
| `part_id` | Affected part |
| `measure_number` | Affected measure |
| `voice_id` | Affected voice (if applicable) |
| `description` | Human-readable explanation |
| `evidence` | Structured data supporting the finding |
| `fix` | Description of any deterministic fix applied |
| `provenance` | Which detector produced the issue and on what input |

## 5. Detectors

### 5.1 Rhythm Detector

Parses MusicXML using real `<divisions>` values per measure.

Detects:
- `measure_overflow`: voice total > time signature expected duration.
- `measure_underflow`: voice total < time signature expected duration.
- `missing_rest`: explicit `<forward>` elements representing silent time.
- `multi_voice_backup_anomaly`: backup durations inconsistent with measure duration.

Auto-fixes:
- `<forward>` → explicit `<rest>` when the conversion does not itself create overflow.

### 5.2 Structure Detector

Detects:
- `missing_measure`: measure number gaps within a part.
- `empty_measure`: measure exists but contains no events.
- `part_measure_count_mismatch`: different parts have different measure counts.

No auto-fixes.

### 5.3 Divisions Detector

Detects:
- `divisions_change`: `<divisions>` value changes mid-part.
- `divisions_missing`: measure lacks divisions and cannot inherit.

No auto-fixes (informational / review).

### 5.4 Notation Detector

Detects:
- `tie_unterminated_start`: tie start without matching stop.
- `tie_dangling_stop`: tie stop without matching start.
- `slur_unterminated_start`: slur start without matching stop.
- `slur_dangling_stop` / `dangling_continue`: slur stop/continue without open slur.
- `tuplet_unterminated_start`: tuplet start without matching stop.
- `tuplet_dangling_stop`: tuplet stop without matching start.

No auto-fixes (reported for AI/human review).

## 6. Normalization Output

The normalizer produces:

- `<project>_normalized.musicxml`: a MusicXML with only safe deterministic fixes applied.
- `OMR_ISSUE_REPORT.json`: the full issue list.
- `OMR_NORMALIZATION.md` (optional): human-readable summary.

## 7. OMR Quality Gate

Before a normalized score is imported into ScoreIR, `OMRQualityGate` classifies every remaining issue by edit safety and returns a verdict:

- `blocking_for_edit`: unresolved issues that make deterministic editing (transposition, part extraction, orchestration) unsafe. Includes overflow, underflow, missing measures, empty measures, and part measure count mismatches.
- `non_blocking`: issues that affect visual or playback semantics but do not endanger deterministic note/rhythm edits. Includes unpaired ties, slurs, tuplets, glissandi, octave shifts, and hairpins.
- `informational`: observations that are not defects. Includes divisions changes and divisions variety.

### 7.1 Modes

- **STRICT**: any unresolved `blocking_for_edit` issue blocks deterministic editing. The gate returns `allowed=False` and `allows_deterministic_edit=False`.
- **PERMISSIVE**: all remaining issues become warnings. The gate returns `allowed=True` and `allows_deterministic_edit=True`, but status is `degraded` when warnings exist.

### 7.2 Usage

```python
from omr_normalization import OMRNormalizer, OMRQualityGate, OMRGateMode

report = OMRNormalizer().normalize(raw_path, normalized_path)
result = OMRQualityGate().check(report, OMRGateMode.STRICT)

if result.allows_deterministic_edit:
    score = MusicXMLImporter().import_file(normalized_path)
else:
    # route to human / AI review
    pass
```

## 8. Integration with Score Engine

The normalizer is used as an optional wrapper:

```python
from score_engine.musicxml import MusicXMLImporter
from omr_normalization import OMRNormalizer

normalizer = OMRNormalizer()
report = normalizer.normalize(raw_path, normalized_path)

importer = MusicXMLImporter()
score = importer.import_file(normalized_path)
```

The existing direct import path remains valid:

```python
score = importer.import_file(raw_path)
```

## 9. Testing Strategy

All detectors are tested against synthetic MusicXML fixtures generated in code. No fixture depends on a real score. Colores is used only as an integration fixture to confirm the normalizer runs on real OMR output without crashing and produces plausible issue counts.

Quality Gate tests cover:
- Clean scores pass in STRICT mode.
- Informational-only reports pass in STRICT mode.
- Unresolved overflow, underflow, and missing measures block in STRICT mode.
- Safely fixed issues do not block.
- Non-blocking notation issues allow editing with degraded status.
- PERMISSIVE mode allows severe issues with warnings.
- Gate summary counts are consistent with the report.

The Score Engine regression test compares the set of overflows detected in raw OMR MusicXML with the set of overflows present after ScoreIR import, asserting that the Score Engine introduces no new overflows (`processed_output_overflows - raw_input_overflows == set()`).
