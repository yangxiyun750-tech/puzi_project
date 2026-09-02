# Skill ID migration

The canonical user-facing Skill ID is `focused-score-rebuild`.

## Why it changed

The former ID `orchestral-score-rebuild` implied support for orchestral and highly complex notation. The current eligibility contract intentionally supports clear printed monophonic melody, solo voice with basic piano accompaniment, and basic concert band only. The new ID matches that boundary.

## Upgrade

- Replace `$orchestral-score-rebuild` with `$focused-score-rebuild` in saved prompts.
- Replace `.agents/skills/orchestral-score-rebuild/` with `.agents/skills/focused-score-rebuild/` in active configuration.
- Use the updated `SCORE_REBUILD` profile.
- Do not create a duplicate alias Skill; duplicate folders can cause ambiguous discovery and drift.

Historical audits and reproduction records keep the old ID when describing earlier runs. Those references are evidence, not active configuration.
