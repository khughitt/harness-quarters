---
id: hq-d5a56c
title: Register the provenance hook and export codex harness-only
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-13T20:50:23Z
updated: 2026-09-13T21:12:09Z
started: 2026-09-13T20:55:32Z
completed: 2026-09-13T21:12:09Z
depends: [ops-a405cc]
tags: [skills]
source: tasks-dc599b
---

Piece B of the tasks plan docs/plans/2026-09-13-creation-provenance.md (spec docs/specs/2026-09-13-creation-provenance-design.md). claude/settings.json: add ~/d/ops/hooks/claude-provenance under SessionStart (matcher startup|resume) and under a new PostModelSwitch entry. codex/config.toml [shell_environment_policy] set: add TASKS_AGENT = "codex" (harness only; the effective model is not knowable from config). Acceptance, live, in a scratch project (mktemp dir, git init, XDG_CONFIG_HOME=$(mktemp -d), tasks init --prefix prb): under model A tasks add shows agent claude-code/<A>; /model to B; tasks add shows claude-code/<B>; tasks start then tasks done shows model <B>; delete the scratch dirs (done cannot be dropped). If the second add still shows A, apply the spec's harness-only fallback and note why in the spec. Codex session: tasks add shows agent codex and no model. Record the result here.

## Notes

- 2026-09-13T20:56:02Z (main): parked (waiting on user, review): Live acceptance in a NEW Claude Code session: D=$(mktemp -d) && cd $D && git init -q && export XDG_CONFIG_HOME=$(mktemp -d) && tasks init --prefix prb; then: tasks add 'probe A' -p 2 and show → agent claude-code/<A>; /model to B; tasks add 'probe B' -p 2 → claude-code/<B>; tasks start <B>; tasks done <B> x → model <B>; rm -rf the two dirs. Pass: tasks done ai-d5a56c with the two model ids. Fail (second add still A): apply the spec's harness-only fallback in ops hooks/claude-provenance and note why in the tasks spec. Codex: same recipe, tasks add → agent codex, no model.
- 2026-09-13T21:12:09Z (main): Live acceptance passed in a fresh session: probe A agent claude-code/claude-opus-5[1m]; after /model, probe B agent claude-code/claude-sonnet-5 and done stamped model claude-sonnet-5 — the env-file preamble is re-evaluated per Bash call, no fallback needed. Hook registered for SessionStart and PostModelSwitch; codex exports TASKS_AGENT=codex (Codex-side probe not yet run).
