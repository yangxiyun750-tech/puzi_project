# Human Review Dialogue

Use this protocol after a complete original-key MuseScore reconstruction exists and before transposition or final delivery. Its purpose is to spend human attention only where source evidence and deterministic checks cannot settle the music.

## Build evidence before asking

For every page, compare the original render with the rebuilt MuseScore render. Inspect Audiveris warnings, MusicXML duration/count findings, instrument definitions, and nearby staves. For wind band, consult legacy part pages only as secondary evidence for the same passage.

Resolve a finding without asking when the printed source clearly determines the answer. Record what changed and why in the QA report. Never turn uncertainty into an automatic correction.

Create a review issue only when at least one musically meaningful interpretation remains plausible. Each issue must identify page, system when known, measure, instrument/staff, category, severity, source observation, reconstructed value, proposed action, confidence, and available evidence images.

## Severity and interruption policy

- `blocking`: pitch, octave, rhythm, rest, chord membership, voice, measure duration, meter, repeat/ending, instrument identity/transposition, or lyric anchoring that can change musical meaning. It must be resolved and verified before the next dependent gate.
- `important`: dynamics, technique text, articulations, hairpin endpoint, tie/slur anchor, tuplet appearance with structurally valid timing, lyric character, native Arpeggio/Glissando, rehearsal or tempo text. Ask in a page batch and resolve before final sign-off.
- `cosmetic`: ordinary stem/beam/rest placement, collision, spacing, or page layout that does not change musical meaning. Apply standard engraving when safe; ask only when multiple intentional layouts are plausible. A user may explicitly defer these.

Do not interrupt the user for routine engraving or for questions the source already answers.

## Interaction modes

### Guided mode (default)

Present one page and at most three related unresolved issues per turn. Give a one-line page summary, then one compact block per issue. This is the default unless the user requests another mode.

### Fast mode

Present a compact table of related issues. Support answers such as “accept all proposals except M28” or “all source readings are correct.” Expand an issue when the response is ambiguous.

### Expert mode

Present stable IDs, location, evidence paths, reconstructed values, and proposed values for the full requested scope. Do not omit visual evidence merely because the user is expert.

Changing modes changes presentation only; it never weakens the completion gate.

## Question format

Prefer this shape:

```text
Page 3 comparison: 24 measures passed; 2 need confirmation.

P03-M027-CLARINET-PITCH
B-flat Clarinet, measure 27 — pitch
Source: accidental may be sharp; rebuilt score: F5 eighth note.
Proposal: F-sharp 5 eighth note. Confidence: 0.62.
Evidence: source crop | rebuilt crop | comparison crop

A. Accept the proposed source reading
B. Keep the rebuilt value
C. Give a different correction
D. Defer for human review
```

Use ordinary musical language appropriate to the user. The user may reply with an option letter or natural language. Never require the user to run the queue script.

If an answer could refer to more than one issue, ask one short clarification before changing notation. If the user asks for a larger crop, playback, adjacent staves, or a part-page cross-check, provide that evidence and keep the issue open.

## Apply, verify, and resume

1. Translate the answer into a decision with `scripts/review_queue.py answer`.
2. Apply the approved change to native MuseScore/MusicXML notation. A recorded decision alone is not a completed correction.
3. Re-render or structurally validate the affected measure and its boundaries.
4. Mark the issue resolved with `scripts/review_queue.py verify --result passed` and cite the evidence. A failed verification returns the issue to human review.
5. Summarize the next unresolved batch. Never repeat resolved questions unless new evidence invalidates the decision.

At the start of a resumed Agent session, load the queue and decision log before asking anything. Report resolved, awaiting-decision, decision-recorded, and deferred counts.

## Completion states

- `PASS`: every issue is resolved and verified.
- `PASS_WITH_DEFERRED_COSMETIC_ITEMS`: only explicitly deferred cosmetic issues remain. Continue only when the user accepts this state.
- `BLOCKED`: any blocking/important issue is not resolved, or a decision has not yet been applied and verified.
- `REVIEW_REQUIRED`: only non-deferred cosmetic work remains open.

Do not transpose or deliver a final production score while status is `BLOCKED`.
