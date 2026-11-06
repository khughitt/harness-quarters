---
id: hq-13dc2d
title: Declare distillation-review on both harness skill surfaces
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-11-06T01:13:01Z
updated: 2026-11-06T01:16:14Z
depends: []
tags: []
source: lore-591a09
agent: codex
origin: agent
---

Why: lore-591a09 builds skills/distillation-review/SKILL.md; it needs the same delivery as curate-docs. Done: add required home link ~/.agents/skills/distillation-review and harness.claude.links entry skills/distillation-review, both targeting lore:skills/distillation-review in links.toml; validate declarations, obtain approval for live link activation, apply through the supported link command, and verify both surfaces resolve the landed lore skill. Where: links.toml. This is the delivery follow-up explicitly permitted by lore-591a09; wait until the skill branch is integrated before activation.

## Notes

- 2026-11-06T01:13:01Z (add): created
  provenance: {"harness_session":"codex:01a1ae66-81e4-75c2-a389-9e357fceb318","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-06T01:16:14Z (main): Prerequisite available: lore skill landed locally on main at ff06d8bd5d5405ce363e9eeb4dfac36b5af2ef59, skills/distillation-review/SKILL.md. Independent review accepted with no findings and paired RED/GREEN dry run passed its scenario. Lore has not been pushed; confirm revision availability on the activation host. Both home declarations and authorized activation remain this task.
