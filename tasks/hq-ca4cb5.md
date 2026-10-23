---
id: hq-ca4cb5
title: Tool runner requires unavailable approval after explicit user authorization
status: dropped
priority: 2
created: 2026-10-23T01:34:33Z
updated: 2026-10-23T11:33:31Z
closed: 2026-10-23T11:33:31Z
depends: []
parent: hq-62c3b1
tags: [feedback, friction, "from:ops"]
agent: codex
---

The user explicitly authorized a narrowly scoped repository restore and separate path commit. Retrying the authorized restore was rejected before execution with approval required by policy, but AskForApproval is set to Never. The runner cannot surface the required approval and the agent cannot proceed without bypassing the rejection. Provide a supported route for authorized actions or a clear actionable policy error.

## Notes

- 2026-10-23T11:21:24Z (main): scope: drop; Codex session log (ops, rollout 2026-10-22T19-17-20-01a165e7…) shows the refused command was git restore --source=0fe87a6 --worktree -- identity-mirror.toml instructions/fragments/projects.md in worktree ops-bfeddd, rejected 2026-10-23T01:19Z and 01:34Z with 'approval required by policy, but AskForApproval is set to Never': default.rules:45 again, before the 09:25Z titan apply that turned it into forbidden with an actionable justification; parented under goal hq-62c3b1; the missing approval route for user-authorized commands under never is upstream openai/codex#41068; the restore-from-commit form the justification does not yet name is added to hq-48c5c6; brief: docs/notes/2026-10-10-codex-never-rejections-brief.md; proposal: drop as a duplicate of hq-48c5c6 (same rule), covered by the applied fix and hq-48c5c6
- 2026-10-23T11:33:31Z (main): dropped
  provenance: {"harness_session":"claude-code:9a8197f4-c7dd-451c-8e5e-9fb7dab61421","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T11:33:31Z (main): Duplicate of hq-48c5c6: same default.rules:45 refusal, before the titan apply; the restore-from-commit form is added to hq-48c5c6, the approval route under never is upstream openai/codex#41068. Drop approved by the user 2026-10-23.
  provenance: {"harness_session":"claude-code:9a8197f4-c7dd-451c-8e5e-9fb7dab61421","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
