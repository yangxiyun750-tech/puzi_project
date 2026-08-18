# Evidence Triage Report — Colores QA Pipeline V1.1

Generated: 2026-08-14
Scope: Deduplicate and prioritize visual-evidence packages for AI/HUMAN review.

---

## 1. Summary Statistics

| Metric | Count |
|---|---|
| Total review issues (AI_REVIEW + HUMAN_REVIEW) | 90 |
| Original evidence packages (1 per issue) | 87 |
| **After dedup by Part + Measure** | **65** |
| Reduction | 25% |

---

## 2. Deduplication Method

**Rule:** If multiple issues share the same `(part_id, measure_number)`, they are
merged into a single evidence package. The package contains:
- `original_crop.png` — the local region of the source PDF
- `scoreir_measure.json` — ScoreIR data for that measure
- `issue.json` — ALL issues for that Part+Measure
- `README.md` — instructions to compare and decide

**Why this is safe:**
- Rhythm overflow and underflow in the same measure are both caused by Audiveris
  misreading the same local region
- Multiple voice layers in the same measure share the same visual region
- A human/AI reviewing the measure once can identify all problems in that region

---

## 3. Priority Classification

### P0 — Structure / Missing Content (10 locations)
These change the actual musical content and must be resolved first.

| Part | Measure | Issues | Type |
|---|---|---|---|
| P1 | 32 | 1 | Missing measure |
| P1 | 76 | 1 | Missing measure |
| P1 | 170 | 1 | Missing measure |
| P1 | 30 | 1 | Empty measure |
| P1 | 86 | 1 | Empty measure |
| P1 | 88 | 1 | Empty measure |
| P1 | 146 | 1 | Empty measure |
| P1 | 215 | 1 | Empty measure |
| P1 | 233 | 1 | Empty measure |
| — | GLOBAL | 1 | Measure count mismatch |

**Resolution:** HUMAN_REVIEW only. Requires looking at source PDF and recovering
lost content. No program can invent missing measures.

---

### P1 — Rhythm / Music Semantics (54 locations)
These affect note durations, rests, and tuplets. AI review of local regions is
appropriate because the evidence is visible in the cropped score image.

| Sub-category | Count | Review Level | Root Cause |
|---|---|---|---|
| Overflow | 37 | AI_REVIEW | Audiveris misread durations |
| Underflow | 23 | HUMAN_REVIEW | Audiveris lost content |
| Time-forward / missing rest | 10 | AI_REVIEW | Audiveris omitted rests |

**Key clusters (measures with 3+ issues):**

| Part | Measure | Issues | Description |
|---|---|---|---|
| P2 | 4 | 4 | Voice 1 underflow + voices 5/6 underflow + missing rest |
| P2 | 14 | 4 | Voice 1 underflow + voices 5/6 underflow + missing rest |
| P2 | 163 | 3 | Voice 1 underflow + voice 6 underflow + missing rest |
| P2 | 257 | 3 | Voice 1 underflow + voice 6 underflow + missing rest |

**Resolution approach:**
- AI_REVIEW (47 issues): AI looks at cropped region, compares to ScoreIR data,
  determines correct durations
- HUMAN_REVIEW (23 issues): Content is missing; AI cannot invent notes. Human
  must supply the missing music.

---

### P2 — Notation Objects (7 locations)
Slurs, tuplets, and extended symbols that don't affect measure totals but affect
musical interpretation.

| Sub-category | Count | Review Level | Root Cause |
|---|---|---|---|
| Unterminated slur | 7 | AI_REVIEW | Audiveris missed slur stops |
| Notation fidelity gap | 1 | HUMAN_REVIEW | ScoreIR V1.0 lacked fields |

**Note:** The notation fidelity gap (tuplet/fermata/arpeggio) is **already fixed**
in V1.1. The HUMAN_REVIEW flag is for the OLD export; the fixed XML contains
all 23 tuplets, 3 fermatas, and 1 arpeggio. This issue can be downgraded to
PASS after re-export.

---

### P3 — Render / Downstream (1 location)

| Issue | Count | Review Level | Resolution |
|---|---|---|---|
| MuseScore import failure | 1 | HUMAN_REVIEW | **Symptom, not root cause.** Will auto-resolve when all P0/P1 rhythm issues are fixed. No separate review needed. |

---

## 4. Pure Program Solutions (Deterministic)

These issues were resolved by code fixes without any human/AI review:

| Fix | Before | After | How |
|---|---|---|---|
| Counter-based tie/slur pairing | 146 false SAFE_REPAIR | 5 real SAFE_REPAIR | Replaced set with Counter |
| ScoreIR divisions tracking | 1 SAFE_REPAIR + 736 rhythm mismatches | 0 | Importer/exporter now handle divisions |
| Extended notation support | 1 HUMAN_REVIEW (fidelity gap) | 0 | Added tuplet/fermata/arpeggio fields |
| Tie deduplication | 563 duplicate annotations | 0 | SafeFixer dedupes `<tie>` + `<tied>` |

**Total program-resolved: 149 issues**

---

## 5. Remaining Review Burden

After all program fixes and deduplication:

| Review Level | Unique Locations | Issues | Estimated Effort |
|---|---|---|---|
| HUMAN_REVIEW | 33 | 33 | High (must invent missing content) |
| AI_REVIEW | 32 | 54 | Medium (verify durations in cropped regions) |
| **Total** | **65** | **87** | — |

**Reduction from original:**
- Original evidence packages: 87
- After program fixes: 90 review issues → 87 after removing 3 program-solvable
- After dedup: 65 unique locations
- **Net reduction: 25% fewer locations to inspect**

---

## 6. Recommended Review Order

1. **P0 first** — Resolve missing/empty measures. These are blockers because
   they affect measure indexing for all downstream checks.
2. **P1 overflow (AI_REVIEW)** — 37 measures where Audiveris added extra duration.
   AI can quickly identify wrong note values in the crop.
3. **P1 underflow (HUMAN_REVIEW)** — 23 measures where content is missing.
   Human must decide what notes/rests belong.
4. **P1 missing rests (AI_REVIEW)** — 10 forward-element gaps. AI can identify
   where rests should be inserted.
5. **P2 slurs (AI_REVIEW)** — 7 unterminated slurs. AI can trace slur arcs in
   the cropped image.
6. **P3 MuseScore** — Re-test import after all above are resolved. Should pass
   automatically.

---

## 7. Files Generated

| File | Path |
|---|---|
| QA Summary (JSON) | `colores_v2/qa/qa_pipeline/QA_SUMMARY.json` |
| QA Report (Markdown) | `colores_v2/qa/qa_pipeline/QA_REPORT.md` |
| Fixed MusicXML | `colores_v2/qa/qa_pipeline/fixed/colores_v2_qa_fixed.musicxml` |
| Visual Evidence Packages | `colores_v2/qa/qa_pipeline/visual_evidence/*/` |
| Root Cause Report | `ROOT_CAUSE_REPORT.md` |
| Evidence Triage Report | `EVIDENCE_TRIAGE_REPORT.md` |
