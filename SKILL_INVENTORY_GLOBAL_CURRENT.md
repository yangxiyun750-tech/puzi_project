# Skill Inventory Appendix — Current User/Global Codex Skills

Audit date: 2026-08-25

| Skill | Exact path | Purpose | Historical successful-run evidence | Classification | Open-source treatment |
|---|---|---|---|---|---|
| imagegen | `<CODEX_HOME>/skills/.system/imagegen/SKILL.md` | Raster image generation/editing | visible, not injected/called | unrelated | exclude |
| openai-docs | `<CODEX_HOME>/skills/.system/openai-docs/SKILL.md` | Codex/OpenAI documentation | visible, not injected in production | unrelated to score runtime | exclude |
| plugin-creator | `<CODEX_HOME>/skills/.system/plugin-creator/SKILL.md` | Codex plugin scaffolding | visible, not invoked | development only/unrelated | exclude |
| review-agent | `<CODEX_HOME>/skills/.system/review-agent/SKILL.md` | Code-review agent guidance | not present in historical successful catalog evidence; no call | development only | optional, not runtime |
| skill-creator | `<CODEX_HOME>/skills/.system/skill-creator/SKILL.md` | Create/update Skills | injected once to create the orchestral Skill | **DEVELOPMENT ONLY** | document, do not require at runtime |
| skill-installer | `<CODEX_HOME>/skills/.system/skill-installer/SKILL.md` | Install Skills | visible, not invoked | development only | optional |
| open-design | `<CODEX_HOME>/skills/open-design/SKILL.md` | Design artifacts/web UI | visible, not invoked | unrelated | exclude |
| video-spec-builder | `<CODEX_HOME>/skills/video-spec-builder/SKILL.md` | Video requirements/specification | visible, not invoked | unrelated | exclude |

`<USER_HOME>/.agents/skills` is empty in the current filesystem scan. A 2026-08-23 ZCode audit recorded `<USER_HOME>/.agents/skills/open-design` as a symlink to the Codex user Skill; it is no longer present and had no score invocation evidence.

Global directories are mutable machine state. The reproducible runtime must use the tracked project-local `focused-score-rebuild` rather than depend on any of these paths.
