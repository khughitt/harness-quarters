---
id: tack-e8dcc5
title: Record explicit process on children created by the shared writing-plans skill
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-13T17:29:59Z
updated: 2026-09-13T18:42:47Z
started: 2026-09-13T18:42:11Z
completed: 2026-09-13T18:42:47Z
depends: [tasks-61cc5c]
tags: [skills]
source: tasks-61cc5c
---

Why: explicit process has no inheritance, so plan step creation must record it alongside complexity. After tasks-61cc5c lands and the installed CLI accepts --process, update the canonical writing-plans skill (agents/skills/superpowers/skills/writing-plans/SKILL.md) and its distributed copies through the existing source/install workflow. The current skill does not contain a tasks add example: add one with --parent, --plan, --step, --complexity and --process direct when the reviewed plan supplies the decisions. Do not default every child blindly; planned remains possible when further design is required. Keep this aligned with tasks skills/tasks/SKILL.md. Done: both instructions show explicit assignment; a sample plan child stores process and complexity; the skill works with the installed CLI. No plugin cache edits as source changes.

## Notes

- 2026-09-13T18:42:47Z (main): Premise corrected: there is no locally owned writing-plans skill. Claude Code loads superpowers 6.3.0 from the official-marketplace plugin cache, and agents/skills/superpowers is a pristine untracked upstream clone with no local commits or install flow, so editing it would fork upstream and still not reach the primary harness. The integration is the tasks skill's writing-plans child command (--complexity <level> --process <value>, landed in tasks 38b060e), the same adapter --complexity used. Verified with the installed CLI in a scratch project: a plan child stores complexity: low and process: direct, check is clean, ready exposes both. No skill fork made.
