# Deterministic Transposition Engine V1 — Implementation Report

**Date:** 2026-08-16  
**Scope:** Transposition Engine V1 for ScoreIR / MusicXML pipeline  
**Status:** ✅ COMPLETE — all suites pass

---

## 1. Summary

Implemented the Deterministic Transposition Engine V1 as approved in the final
design review. The engine supports:

- Relative interval transposition by named interval (up/down, simple/compound).
- Written ↔ sounding conversion for transposing instruments using MusicXML
  `<transpose>` semantics.
- Measure-range key signature transposition with restoration of the original
  active key at `end+1`.
- Deep-copy immutability: input `Score` objects are never modified.
- OMR Quality Gate integration via `SafeTranspositionService` (STRICT/PERMISSIVE).

The implementation is deterministic, rule-based, and contains no Colores-specific
or measure-specific special cases.

---

## 2. New / Modified Files

### New transposition package

| File | Purpose |
|------|---------|
| `src/score_engine/transposition/__init__.py` | Public API exports |
| `src/score_engine/transposition/interval.py` | Named interval (`Interval`) and `SpellingError` |
| `src/score_engine/transposition/instrument_map.py` | Instrument→transposition table, provenance resolver, `transposition_to_interval` |
| `src/score_engine/transposition/pitch_spelling.py` | V1 spelling strategy (immutable diatonic step) |
| `src/score_engine/transposition/key_signature.py` | Key signature transposition + timeline + range restoration |
| `src/score_engine/transposition/request.py` | `TransposeRequest` schema / operation enum |
| `src/score_engine/transposition/engine.py` | `TranspositionEngine` |
| `src/score_engine/transposition/service.py` | `SafeTranspositionService` with OMR gate |
| `src/score_engine/transposition/report.py` | `TransposeReport`, `PartReport`, `NoteChange` |

### Modified files

| File | Change |
|------|--------|
| `src/score_engine/score_ir/score_ir.py` | Added `InstrumentTransposition` frozen dataclass; added `Part.transposition_events` and `Part.has_variable_transposition` |
| `src/score_engine/score_ir/__init__.py` | Exported `InstrumentTransposition` |
| `src/score_engine/musicxml/musicxml_to_score_ir.py` | Added `_import_transpose` helper; reads `<transpose>` and flags staff-specific, `<double>`, and mid-part changes |
| `tests/test_transposition.py` | 63 new transposition tests |

---

## 3. ScoreIR Changes

```python
@dataclass(frozen=True, slots=True)
class InstrumentTransposition:
    diatonic: int = 0       # staff-step offset (written → sounding)
    chromatic: int = 0      # semitone offset (written → sounding)
    octave_change: int = 0  # additional octave displacement

@dataclass
class Instrument:
    ...
    transposition: InstrumentTransposition = field(default_factory=InstrumentTransposition)

@dataclass
class Part:
    ...
    transposition_events: list[dict[str, Any]] = field(default_factory=list)
    has_variable_transposition: bool = False
```

Default C instrument is `(0, 0, 0)`. The boolean conversion returns `True` when
any component is non-zero, so piccolo `(0, 0, 1)` and double bass `(0, 0, -1)`
are correctly detected as transposing.

---

## 4. Instrument Transposition Mapping

Mapping follows `sounding_pitch = written_pitch + transposition`.

| Instrument | diatonic | chromatic | octave_change |
|------------|----------|-----------|---------------|
| Bb Trumpet / Clarinet / Soprano Sax / Tenor Sax / Bass Clarinet | -1 | -2 | 0 |
| Eb Alto Sax | -5 | -9 | 0 |
| Eb Baritone Sax | -5 | -9 | -1 |
| F Horn / English Horn | -4 | -7 | 0 |
| A Clarinet | -2 | -3 | 0 |
| Piccolo | 0 | 0 | +1 |
| Double Bass / Guitar / Bass Guitar | 0 | 0 | -1 |

The `transposition_to_interval()` helper converts `(diatonic, chromatic)` to a
named `Interval` (e.g. Bb → `-M2`, Eb alto → `-M6`, F horn → `-P5`). Any
`octave_change` is applied separately by the engine so that the diatonic/chromatic
interval stays in a named quality (`M`, `m`, `P`).

---

## 5. Transposition Provenance

Resolution order for a part:

1. **ScoreIR / MusicXML metadata** — `part.instrument.transposition` non-zero and
   `part.has_variable_transposition == False` → `provenance="musicxml"`.
2. **Instrument identity fallback** — name-based lookup → `provenance="identity"`.
3. **Unknown** → `provenance="unknown"`.

If `has_variable_transposition` is `True` (staff-specific, `<double>`, or mid-part
change), the part is marked `supported=False`.

Behavior:
- Relative interval transposition **always proceeds**, even with unknown or
  unsupported provenance.
- Written ↔ sounding conversion **proceeds only for** `musicxml` / `identity`
  provenance.
- Unknown provenance reports `sounding_audit_available=False` but does not block
  relative transposition.
- Unsupported variable transposition blocks written/sounding conversion.

---

## 6. Behavior Descriptions

### 6.1 Relative interval transposition

- Applies the named interval to every `Pitch` in the selected parts/measures.
- Rests are skipped.
- Chord notes are transposed individually.
- The diatonic target step is immutable; out-of-bound accidentals (outside
  `[-2, +2]`) are reported as warnings and the note is left unchanged.
- No enharmonic override: a M3 from C always yields E, never Fb.

### 6.2 Written ↔ sounding conversion

- Uses `InstrumentTransposition` → `Interval` + `octave_change`.
- `WRITTEN_TO_SOUNDING`: add the transposition.
- `SOUNDING_TO_WRITTEN`: subtract the transposition (inverse interval + opposite
  octave shift).

### 6.3 Key signature handling

- A per-part `KeyTimeline` records explicit key-change locations.
- For every measure in the selected range, the *active* key (inherited or
  explicit) is transposed by the interval and stored on that measure.
- At `end+1`, the original active key is restored, **unless**:
  - the range reaches the part end, or
  - `end+1` is already an explicit original key-change location.

### 6.4 Immutability

- `TranspositionEngine.transpose()` deep-copies the input `Score` when
  `preserve_original=True` (default).
- Tests verify the original score snapshot is unchanged, not equality with the
  original.

---

## 7. Test Counts

| Suite | Tests | Result |
|-------|-------|--------|
| `tests/test_transposition.py` | 63 | ✅ PASS |
| `tests/test_score_engine.py` | existing | ✅ PASS |
| `tests/test_omr_normalization.py` | existing | ✅ PASS |
| `tests/test_omr_quality_gate.py` | existing | ✅ PASS |
| `tests/test_musicxml_voice_cursor.py` | existing | ✅ PASS |
| **Total** | **126** | **✅ PASS** |

---

## 8. Full Project PASS / FAIL

```
Ran 126 tests in 2.223s
OK
```

All OMR, Quality Gate, MusicXML voice-cursor, Score Engine, and Transposition
regression tests pass.

---

## 9. Export → Re-import Results

### 9.1 Relative transposition round-trip

Operation: transpose Colores `P1`/`P2` up a major second, export to MusicXML,
re-import, validate against the in-memory transposed score.

```
Imported: 2 parts, 515 measures
Transposed: 735 notes changed in P1
Exported to colores_v2/omr/colores_transposed_M2.musicxml
Round-trip status: PASS
Errors: 0, Warnings: 0
```

Sample pitches after transposition:

| Original | Transposed |
|----------|------------|
| D♭3 | E♭3 |
| E♭3 | F3 |
| B♭3 | C4 |
| C4 | D4 |

### 9.2 OMR / Quality Gate semantic preservation

- Existing OMR normalization tests: unchanged, all pass.
- Quality Gate STRICT/PERMISSIVE tests: unchanged, all pass.
- `SafeTranspositionService` blocks deterministic editing in STRICT mode when
  the gate reports blocking issues; PERMISSIVE allows with warnings.

---

## 10. Readiness for NL → TransposeRequest

The `TransposeRequest` schema is designed as the stable interface for a future
natural-language layer:

```python
@dataclass(frozen=True, slots=True)
class TransposeRequest:
    operation: TranspositionOperation      # INTERVAL | WRITTEN_TO_SOUNDING | SOUNDING_TO_WRITTEN
    interval: Interval | None = None       # for INTERVAL
    part_ids: list[str] | None = None      # None = all parts
    measure_start: int = 1                 # 1-based, inclusive
    measure_end: int | None = None         # None = to end
    preserve_original: bool = True
```

NL intent examples that map directly:

| Utterance | Mapped request |
|-----------|----------------|
| "Transpose the flute part up a major third" | `INTERVAL`, `interval=M3`, `part_ids=[flute_id]` |
| "Convert the score to concert pitch" | `WRITTEN_TO_SOUNDING` |
| "Transpose measures 5–10 down a minor second" | `INTERVAL`, `interval=-m2`, `measure_start=5`, `measure_end=10` |

The engine returns a `TransposeReport` with `status`, per-part summaries,
note-level changes, and warnings — sufficient for NL explanation generation.

---

## 11. Known V1 Limitations (by design)

- Augmented (`A`) and diminished (`d`) interval qualities are rejected.
- Out-of-bound accidentals (beyond double-sharp/flat) are not respelled; they
  produce warnings and the note is left unchanged.
- Staff-specific `<transpose number="...">`, `<double/>`, and mid-part
  transposition changes are detected and reported as unsupported.
- Absolute target-key transposition is not implemented in V1 (schema leaves room
  for it).

---

## 12. Conclusion

The Deterministic Transposition Engine V1 is fully implemented, tested, and
integrated. It satisfies all hard constraints from the approved design,
preserves existing OMR/Quality Gate/Score Engine behavior, and is ready for a
future NL layer to generate `TransposeRequest` objects.
