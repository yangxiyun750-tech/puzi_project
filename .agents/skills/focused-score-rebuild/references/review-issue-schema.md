# Review Issue Schema

`scripts/review_queue.py` stores UTF-8 JSON with `schema_version: 1`. The queue is private project state and must not be committed when it contains score-derived text or images.

## Queue document

```json
{
  "schema_version": 1,
  "project": {
    "title": "Example work",
    "source_pdf": "source.pdf",
    "review_mode": "guided"
  },
  "issues": []
}
```

`review_mode` is `guided`, `fast`, or `expert`.

## Issue fields

Required fields:

- `issue_id`: stable, unique identifier meaningful in conversation.
- `page`: one-based source PDF page.
- `measure`: printed/MuseScore measure label as text.
- `instrument`: instrument or staff label.
- `category`: `pitch`, `octave`, `rhythm`, `rest`, `chord`, `voice`, `structure`, `instrument`, `transposition`, `lyric`, `tie_slur`, `tuplet`, `dynamic`, `articulation`, `technique`, `harp`, `text`, `metadata`, or `engraving`.
- `severity`: `blocking`, `important`, or `cosmetic`.
- `source_observation`: what can actually be seen or inferred from source evidence.
- `reconstructed_value`: current native-score interpretation.
- `proposed_action`: evidence-backed proposal; may state that no proposal is safe.
- `confidence`: number from 0 through 1, or `null` when it cannot be estimated responsibly.
- `status`: `awaiting_human`, `decision_recorded`, `resolved`, or `deferred`.

Optional fields:

- `system`, `staff`, `voice`, `printed_page`, `rehearsal_mark`.
- `source_image`, `rebuilt_image`, `comparison_image`.
- `secondary_evidence` and `notes`.
- `decision`, `decision_value`, `decision_note`, `decided_by`, `decided_at`.
- `verification_result`, `verification_evidence`, `verified_at`.

Paths may be repository/project relative or absolute within the private workspace. Do not put image bytes in the JSON.

## Decision semantics

- `accept_proposal`: user accepts `proposed_action`.
- `keep_reconstruction`: user accepts the current reconstructed value.
- `custom`: user supplies a different reading; `decision_value` is required.
- `defer`: permitted for any issue while reviewing, but only deferred cosmetic issues can reach a completion state that permits user-authorized continuation.

An accepted decision sets `status` to `decision_recorded`; it does not prove the score was changed. Verification is a separate step. `verify --result passed` sets `resolved`. `verify --result failed` returns the issue to `awaiting_human` and records the failed evidence.

## Decision log

Every answer and verification appends one JSON object to `qa/decisions.jsonl`. The log is append-only audit history. The queue holds current state; the log explains how it reached that state.

Do not edit or truncate the log to hide a superseded decision. Add a new decision and verification event instead.
