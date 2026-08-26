# Skill Inventory Appendix — ZCode Plugin Cache

Audit date: 2026-08-25
Root: `<USER_HOME>/.zcode/cli/plugins/cache/zcode-plugins-official`

These user-machine cache entries are mutable external state. The 2026-08-23 ZCode activation audit found no pre-audit ZCode Skill-tool invocation in transcripts; only a later `orchestral-score-rebuild` smoke invocation was recorded. None of the following has evidence of involvement in the historical successful Codex score run.

| Skill | Exact path | Purpose | Classification | Open-source treatment |
|---|---|---|---|---|
| android-dev | `android-emulator\0.1.0\skills\android-dev\SKILL.md` | Android emulator/development | unrelated | exclude |
| control-browser | `browser-use\0.2.1\skills\control-browser\SKILL.md` | Browser automation | unrelated to historical score run | optional only if future UI tests adopt it |
| web-gui-tester | `browser-use\0.2.1\skills\web-gui-tester\SKILL.md` | Browser GUI testing | unrelated | optional development |
| docx | `document-skills\0.1.0\skills\docx\SKILL.md` | Word documents | unrelated | exclude |
| pdf | `document-skills\0.1.0\skills\pdf\SKILL.md` | General PDF work | visible/cache only; no historical invocation | optional convenience, not required |
| pptx | `document-skills\0.1.0\skills\pptx\SKILL.md` | Presentations | unrelated | exclude |
| ios-dev | `ios-simulator\0.1.0\skills\ios-dev\SKILL.md` | iOS simulator/development | unrelated | exclude |
| restore-legacy-sessions | `restore-legacy-sessions\0.1.0\skills\restore-legacy-sessions\SKILL.md` | Restore old ZCode sessions | development/admin only | do not require |
| skill-creator | `skill-creator\0.1.0\skills\skill-creator\SKILL.md` | Skill authoring | no invocation evidence for historical run | development only |
| diagnosing-commands | `zcode-guide\0.1.0\skills\diagnosing-commands\SKILL.md` | ZCode command diagnosis | no score evidence | development only |
| diagnosing-hooks | `zcode-guide\0.1.0\skills\diagnosing-hooks\SKILL.md` | ZCode hook diagnosis | no score evidence | development only |
| diagnosing-mcp | `zcode-guide\0.1.0\skills\diagnosing-mcp\SKILL.md` | ZCode MCP diagnosis | no score evidence | development only |
| diagnosing-plugins | `zcode-guide\0.1.0\skills\diagnosing-plugins\SKILL.md` | ZCode plugin diagnosis | no score evidence | development only |
| diagnosing-skills | `zcode-guide\0.1.0\skills\diagnosing-skills\SKILL.md` | ZCode Skill diagnosis | no score evidence | development only |
| zcode-configuration-guide | `zcode-guide\0.1.0\skills\zcode-configuration-guide\SKILL.md` | ZCode configuration | no score evidence | development only |

Prepend the cache root above to each relative path. These files must not become implicit runtime dependencies. If a future release truly depends on one, copy/version the allowed resource or document an explicit plugin installation and add invocation evidence.
