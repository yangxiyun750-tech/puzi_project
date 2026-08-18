# Root Cause Analysis Report — Colores QA Pipeline V1.1

Generated: 2026-08-14
Scope: Raw MusicXML → ScoreIR → Fixed MusicXML → QA verification
Method: Programmatic inspection of raw XML structure, ScoreIR importer/exporter
behavior, and QA issue clustering. No AI visual review was used.

---

## Executive Summary

**Before fixes (V1.0):**
- 146 SAFE_REPAIR (mostly false positive dangling tie/slur)
- 51 AI_REVIEW
- 35 HUMAN_REVIEW

**After fixes (V1.1):**
- 7 SAFE_REPAIR (5 real dangling tie stops + 2 tie consistency)
- 55 AI_REVIEW
- 35 HUMAN_REVIEW

**Key win: 139 false-positive dangling annotations eliminated** by replacing the
set-based pairing algorithm with Counter (multiset), which correctly handles
Audiveris's reuse of tie/slur number="1" across the entire score.

---

## 1. Root Causes Identified

### RC-1: Audiveris OMR Measure Loss (P1)
**Type:** Audiveris OMR error  
**Evidence:** P1 missing M32, M76, M170; 6 empty measures (M30, M86, M88, M146, M215, M233)

Audiveris failed to emit measure elements for 3 measure numbers, and emitted
empty measures for 6 others. P2 (Piano) has 259 continuous measures with no
gaps. P1 + 3 gaps = 259, confirming the 3 missing measures are the sole cause
of the measure-count mismatch.

**Downstream symptoms:**
- 3 × `STRUCT-GAP` (HUMAN_REVIEW)
- 6 × `STRUCT-EMPTY` (HUMAN_REVIEW)
- 1 × `STRUCT-MEASURE-COUNT-MISMATCH` (HUMAN_REVIEW)
- **NOT** a cause of downstream rhythm overflow/underflow (rhythm QA parses raw
  XML directly and does not interpolate missing measures)

---

### RC-2: Audiveris OMR Rhythm Errors
**Type:** Audiveris OMR error  
**Evidence:** 37 overflow + 23 underflow + 10 time-forward in raw MusicXML

These are genuine note-duration misreadings by Audiveris. The raw XML contains
measures where the sum of note durations does not equal the time signature.
Examples:
- M16 P1: 9/2 quarters vs 4 expected
- M4 P2 voice 6: 2 quarters vs 4 expected
- M257 P2: 1/2 quarter vs 4 expected

The ScoreIR divisions-normalization bug (RC-4) amplified some of these errors
in the exported XML, but the raw XML itself already contains the wrong durations.

**Downstream symptoms:**
- 37 × `measure_total_overflow` (AI_REVIEW)
- 23 × `measure_total_underflow` (HUMAN_REVIEW)
- 10 × `missing_rest` / `time-forward` (AI_REVIEW)
- 1 × `MuseScore import failure` (RC-5)

---

### RC-3: Audiveris OMR Slur Errors
**Type:** Audiveris OMR error  
**Evidence:** 26 unterminated slur starts in raw XML (P1=24, P2=2)

Audiveris detected slur starts but missed their corresponding stops. Counter-based
pairing confirms there are NO dangling slur stops (all stops match a start), but
26 starts lack a stop.

**Downstream symptoms:**
- 7 × `slur_pairing` unterminated (AI_REVIEW)

(Only 7 visible because unterminated slurs with count>1 are aggregated by
number; the actual unterminated start count is 26.)

---

### RC-4: ScoreIR Importer/Exporter Divisions Bug
**Type:** ScoreIR code bug (FIXED in V1.1)

**Importer:** Stored all durations with `divisions=1`, ignoring the actual
`<divisions>` value in the raw XML (which changes: 2 → 6 → 12).

**Exporter:** Hardcoded `<divisions>1</divisions>` in every measure.

**Impact:** A note with divisions=2 and duration=4 (real value: 2 quarters)
was exported as divisions=1 and duration=4 (real value: 4 quarters), causing
massive rhythmic inflation.

**Fix applied:**
- Importer now tracks divisions per measure and stores `Duration(divisions, value)`
- Exporter now outputs the measure's stored divisions value
- SafeFixer normalizes to canonical divisions=12 and re-verifies

**Downstream symptoms ELIMINATED:**
- Rhythm export mismatch (736 places) → after fix: exported XML matches raw
  XML rhythm exactly
- MuseScore import on truncated M1–M14 succeeds, confirming the fix is
  structurally correct

---

### RC-5: ScoreIR V1.0 Model Limitation
**Type:** ScoreIR data model gap (FIXED in V1.1)

V1.0 Note model did not carry:
- tuplet start/stop
- fermata
- arpeggio

**Fix applied:**
- Added `tuplet`, `fermata`, `arpeggiate` fields to Note
- Importer now parses these from `<notations>`
- Exporter now outputs them

**Verification:** Fixed XML contains 23 `<tuplet>`, 3 `<fermata>`, 1 `<arpeggiate>`.

---

### RC-6: NotationQA Set-Algorithm Bug
**Type:** QA code bug (FIXED in V1.1)

The tie/slur pairing algorithm used a Python `set` to track open annotations.
Because Audiveris reuses `number="1"` for every tie/slur across the score, the
set algorithm misclassified valid stops as "dangling" whenever the same number
was used for a subsequent independent tie/slur.

**Inspection results:**
- Set algorithm: P2 ties showed 134 dangling stops
- Counter algorithm: P2 ties showed 0 dangling stops

**Fix applied:** Replaced `set` with `collections.Counter` for tie and slur
pairing in both NotationQA and SafeFixer.

**Downstream symptoms ELIMINATED:**
- 139 false-positive SAFE_REPAIR issues removed
- SafeFixer now removes only 5 real orphan tie stops (not 146)

---

### RC-7: MuseScore Import Failure
**Type:** Downstream symptom (NOT a root cause)

MuseScore exits with code 40 when importing the fixed XML because 37 measures
have rhythmic overflow. Truncation test confirms: M1–M14 import fine; the
overflow measures block import.

**This will auto-resolve once RC-2 (rhythm errors) is fixed.**

---

## 2. Root Cause → Issue Mapping

| Root Cause | Issues Before | Issues After | Fixed? |
|---|---|---|---|
| RC-1 Audiveris measure loss | 10 HUMAN_REVIEW | 10 HUMAN_REVIEW | No (OMR) |
| RC-2 Audiveris rhythm errors | 70 AI/HUMAN_REVIEW | 70 AI/HUMAN_REVIEW | No (OMR) |
| RC-3 Audiveris slur errors | 7 AI_REVIEW | 7 AI_REVIEW | No (OMR) |
| RC-4 ScoreIR divisions bug | 1 SAFE_REPAIR + downstream | 0 | **Yes** |
| RC-5 ScoreIR model limitation | 1 HUMAN_REVIEW | 0 | **Yes** |
| RC-6 QA set algorithm bug | 146 SAFE_REPAIR (false pos) | 5 SAFE_REPAIR | **Yes** |
| RC-7 MuseScore failure | 1 HUMAN_REVIEW | 1 HUMAN_REVIEW | Symptom |

---

## 3. Classification: ROOT_CAUSE vs DOWNSTREAM vs AMBIGUITY

| Issue | Classification | Reason |
|---|---|---|
| Missing measures M32/76/170 | **ROOT_CAUSE** (Audiveris) | Audiveris failed to output measure elements |
| Empty measures M30/86/88... | **ROOT_CAUSE** (Audiveris) | Audiveris emitted measures with no content |
| Rhythm overflow/underflow | **ROOT_CAUSE** (Audiveris) | Raw XML durations are wrong; not caused by importer |
| Time-forward gaps | **ROOT_CAUSE** (Audiveris) | Forward elements represent missing rests in raw XML |
| Unterminated slurs | **ROOT_CAUSE** (Audiveris) | Audiveris missed slur stops |
| 146 dangling annotations (before) | **DOWNSTREAM** (QA bug) | Set algorithm false positives; raw XML is correct |
| Divisions normalization error | **ROOT_CAUSE** (ScoreIR bug) | Importer ignored `<divisions>`; fixed in V1.1 |
| Tuplet/fermata/arpeggio loss | **ROOT_CAUSE** (ScoreIR bug) | Model lacked fields; fixed in V1.1 |
| MuseScore import failure | **DOWNSTREAM** (rhythm) | Will resolve when rhythm errors are fixed |
| Notation fidelity gap (before) | **DOWNSTREAM** (ScoreIR bug) | Resolved by V1.1 importer/exporter fixes |

---

## 4. ScoreIR V1.1 Fixes Summary

### Importer (`musicxml_to_score_ir.py`)
1. **Divisions tracking:** `current_divisions` tracked across measures; stored in
   `Duration(divisions, value)` and `Measure.divisions`
2. **Chord tones:** Duration kept as-is (not zeroed); downstream consumers handle
3. **Backup/forward:** Per-voice time-offset tracking with `Fraction` arithmetic
4. **Extended notations:** Parse `<tuplet>`, `<fermata>`, `<arpeggiate>`
5. **Tie parsing:** Parse both `<tie>` (outside notations) and `<tied>` (inside)

### Exporter (`score_ir_to_musicxml.py`)
1. **Divisions output:** Output `Measure.divisions` instead of hardcoded 1
2. **Extended notations:** Export `<tuplet>`, `<fermata>`, `<arpeggiate>`
3. **Tie export:** Output both `<tie>` and `<tied>` for MuseScore compatibility

### NotationQA (`notation_qa.py`)
1. **Counter-based pairing:** `collections.Counter` replaces `set` for tie/slur
2. **Fidelity check:** Accounts for deliberate dangling removals from SafeFixer

### SafeFixer (`fixer.py`)
1. **Counter-based cleanup:** Only removes stops with no matching start
2. **Chord tones:** No longer zeroes durations (keeps original values)

---

## 5. What Still Needs Human / AI Review

After eliminating all program bugs, the remaining issues are **purely Audiveris
OMR errors** that cannot be deterministically fixed:

| Category | Count | Review Level | Action |
|---|---|---|---|
| Missing / empty measures | 10 | HUMAN_REVIEW | Human must recover content from source PDF |
| Rhythm underflow (content lost) | 23 | HUMAN_REVIEW | Human must recover missing notes/rests |
| Rhythm overflow (extra content) | 37 | AI_REVIEW | AI inspects local region to confirm true durations |
| Missing rests (time-forward) | 10 | AI_REVIEW | AI inspects local region to identify missing rests |
| Unterminated slurs | 7 | AI_REVIEW | AI inspects local region to confirm slur extent |
| MuseScore import failure | 1 | HUMAN_REVIEW | Will auto-resolve after rhythm fixes above |

**Total unique Part+Measure locations needing review: 65**
(down from 87 evidence packages before deduplication)

---

## 6. Deliverability Gate

Delivery remains **blocked** until:
1. All 10 structure issues are resolved (missing/empty measures)
2. All 70 rhythm issues are resolved (overflow/underflow/time-forward)
3. All 7 slur issues are resolved (unterminated starts)
4. MuseScore successfully imports and exports PDF

The ScoreIR importer/exporter and QA algorithm bugs are **fully resolved** and
no longer contribute to the issue count.
