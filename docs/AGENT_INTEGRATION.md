# Coding-Agent Integration

ScoreRebuild's core contract is agent-neutral. The single user-facing workflow is the project-local Skill:

```text
.agents/skills/focused-score-rebuild/SKILL.md
```

Do not require users to invoke `musicxml-qa`, `score-export`, `score-reconstruction-v2`, or development Skills manually. Those may remain available for experiments, but they are not the V0.1 default contract.

The former Skill ID `orchestral-score-rebuild` was retired because its name contradicted the supported focused scope. Update saved prompts to `$focused-score-rebuild`; historical reports retain the old ID as evidence.

## Required agent capabilities

The agent must be able to:

- read the complete Skill and its referenced files;
- execute local Python, Poppler, Audiveris, and MuseScore commands;
- create/edit files inside the project and temporary work directories;
- reason over XML, CLI logs, and QA reports;
- either inspect images or explicitly route visual review to a human;
- stop and request human musical judgment for unresolved notation.

Run `python -m score_rebuild capability-doctor` before production. A model name is not evidence of image input. Visual capability is `AVAILABLE` only after explicit verification; otherwise use the manual visual-review path.

## ZCode

The optional `.zcode/config.json` compatibility profile is `SCORE_REBUILD`. It enables only `focused-score-rebuild`. Other profiles remain disabled unless a developer explicitly selects them.

## Codex

Open the repository root as the project. Confirm that the agent can see the project-local `focused-score-rebuild` Skill, then request it explicitly for score reconstruction. If the installed Codex surface does not discover `.agents/skills`, provide the absolute path to `SKILL.md` or install/copy the Skill using that Codex version's documented project-Skill mechanism. Do not depend on a mutable user-global Skill copy.

Codex/model image support must still be verified by the capability doctor or a manual test; it is not inferred from the product name. Current OpenAI model documentation lists modalities per model, so check the exact configured model rather than assuming all Codex-capable models accept images.

## WorkBuddy-style or other coding agents

Point the agent at the repository root and the exact `SKILL.md` above. Configure its local-command sandbox to permit only the project, the selected source file, installed executables, and temporary output. If it has no native Skill discovery, instruct it to read `SKILL.md` completely before acting. The workflow remains one Skill; do not translate the hidden stage sequence back into ad-hoc prompts.

## Provider-neutral variables

```text
SCORE_REBUILD_CODE_REASONING_PROVIDER
SCORE_REBUILD_CODE_REASONING_VERIFIED
SCORE_REBUILD_VISUAL_REVIEW_PROVIDER
SCORE_REBUILD_VISUAL_REVIEW_VERIFIED
SCORE_REBUILD_HUMAN_REVIEWER
```

Current ZCode-compatible model clients may additionally use `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`. These variables are optional implementation details, not the core Skill interface. Never commit credentials.

## Build installable packages

Build both the generic Skill ZIP and the ZCode marketplace ZIP from the same canonical directory:

```text
python tools/build_agent_packages.py --output-dir dist
```

The builder writes deterministic archives plus `dist/SHA256SUMS.json`. Generated packages remain untracked. Both archives include the repository `LICENSE`, and plugin metadata declares `AGPL-3.0-only`. Third-party binaries and private score materials are never bundled.
