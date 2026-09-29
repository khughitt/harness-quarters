---
id: skill-tasks-invoked-on-trigger
title: The tasks skill is invoked before the first tasks command in a repository that has tasks/.config.toml
subject:
  kind: skill
  name: 'tasks (description: "Use when working in a repository that contains tasks/.config.toml or tasks/*.md task records")'
  version: [tasks@9191141 skills/tasks/SKILL.md]
inputs:
  - kind: session
    ref: claude-code:f94bce47-700f-4fdb-8122-6f38b7f103dd
    session_cwd: ai checkout (tasks/.config.toml present)
  - kind: fixture
    ref: first tasks CLI call
    value: toolu_01RGwYFjHwbRPke6jyoEDC2H at 2026-09-22T00:15:05.881Z (at_ms 1790036105881)
expected:
  type: boolean
  claim: the session invoked the tasks skill natively before its first tasks CLI call
  value: true
observed:
  value: true
  at: the subject version above
judge:
  kind: check
  command: >-
    sqlite3 ~/.local/state/obs/index.sqlite "select count(*) > 0 from skill_calls
    where session_id = 'f94bce47-700f-4fdb-8122-6f38b7f103dd' and skill = 'tasks'
    and kind = 'native' and at_ms < 1790036105881"
  pass: prints 1
source: [obs-e52980]
evidence: observed
---

A positive case from obs's skill telemetry (obs-e52980): the `skill_calls` row
`toolu_01SUKTG44aSJ5ywLDzzANohe` records a native Skill call for `tasks` at
00:15:02.170, 3.7 seconds before the session's first `tasks prime`.

The index says when the skill ran, not when its trigger applied. The trigger
condition (the cwd holds `tasks/.config.toml`) and the first CLI call come from
the transcript, so they are inputs here, not part of the check. A negative
case would need the same two facts and a missing or later row.
