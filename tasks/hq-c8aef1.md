---
id: hq-c8aef1
title: "No session-logs command answers 'which session created task X, and what did the human say just before it'"
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-10-25T17:46:39Z
created: 2026-10-25T11:03:11Z
updated: 2026-10-25T17:46:39Z
depends: [obs-02e88b, obs-d98663]
parent: hq-cff824
tags: [feedback, gap, "from:obs"]
agent: claude-code/claude-opus-5-5
---

Action: recovering the user's original ask behind an agent-held task. Worked around with a grep for the id across Codex rollouts, picking the file whose first hit matches the task's created time (a bare id grep also returns later readers, a title grep missed the creating file), then a hand-written scan applying the skill's human-vs-injected prefix rules over a time window. Expected: one command taking a task id that returns the creating session and the human turns preceding the add call, using a creation stamp when present and the time-matched search otherwise.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-25-task-origin-lookup-brief.md — existing reader and join research, remaining origin-query decisions

## Notes

- 2026-10-25T14:58:49Z (main): input now exists: tasks main 7c3b9d2 (goal tasks-053e89) writes a stamped 'created' note on every new record (harness_session names the creating session; root_session for a Codex worker; origin_session when the ask came from an older session), from rollout tasks-c96737 on. The scope skill's §2 gives the manual two-stage retrieval this command would automate; demonstration report attached to tasks-4d39db, gaps filed as hq-4d77cc and hq-34163a.
- 2026-10-25T17:46:39Z (main): scope: briefed; checked hq fc2710e, obs 9fda68a and tasks 7c3b9d2: creation stamps now exist, but reviewed reader spec ae0f8ee D2/9.4 provides task evidence rather than creation-call binding or ask attribution. Preserved captured body and P2; reused goal hq-cff824, existing six-case research obs-02e88b (wake instruction added) and reader build obs-d98663, recording both waits; no duplicate study or implementation task. origin: stage 1 unavailable (no creation occurrence stamp); stage 2 not applicable (no origin_session); origin field remains unknown, with no claim that the transcript is absent. brief: docs/notes/2026-10-25-task-origin-lookup-brief.md
  provenance: {"harness_session":"codex:01a1741d-bda8-7d83-9f61-c6d417291bd2","harness_session_source":"CODEX_THREAD_ID"}
