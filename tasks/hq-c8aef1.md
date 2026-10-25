---
id: hq-c8aef1
title: "No session-logs command answers 'which session created task X, and what did the human say just before it'"
status: idea
priority: 2
created: 2026-10-25T11:03:11Z
updated: 2026-10-25T14:58:49Z
depends: []
tags: [feedback, gap, "from:obs"]
agent: claude-code/claude-opus-5-5
---

Action: recovering the user's original ask behind an agent-held task. Worked around with a grep for the id across Codex rollouts, picking the file whose first hit matches the task's created time (a bare id grep also returns later readers, a title grep missed the creating file), then a hand-written scan applying the skill's human-vs-injected prefix rules over a time window. Expected: one command taking a task id that returns the creating session and the human turns preceding the add call, using a creation stamp when present and the time-matched search otherwise.

## Notes

- 2026-10-25T14:58:49Z (main): input now exists: tasks main 7c3b9d2 (goal tasks-053e89) writes a stamped 'created' note on every new record (harness_session names the creating session; root_session for a Codex worker; origin_session when the ask came from an older session), from rollout tasks-c96737 on. The scope skill's §2 gives the manual two-stage retrieval this command would automate; demonstration report attached to tasks-4d39db, gaps filed as hq-4d77cc and hq-34163a.
