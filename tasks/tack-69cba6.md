---
id: tack-69cba6
title: "Where-am-I: task notes and reads diverge between the main checkout and a worktree"
status: done
priority: "2"
size: s
complexity: low
process: direct
owner: main
created: 2026-09-24T14:36:14Z
updated: 2026-09-24T15:01:19Z
started: 2026-09-24T14:54:20Z
completed: 2026-09-24T15:01:19Z
depends: []
tags: [flow]
source: ai-c78706
model: "claude-opus-5-5[1m]"
agent: "claude-code/claude-opus-5-5[1m]"
---

Why: three instances across three efforts — notes written from two checkouts diverged ai-f5da3a's record into a rebase conflict and a reviewer's failed cd wrote into the main checkout (2026-09-15); a cwd-dependent tasks show made the retros listing differ per checkout (ai-bdff6f, fixed by routing to the registered root); on 2026-09-24 the ai-99ea5d implementing gate was written in the main checkout right after its worktree was created and had to be moved. tasks routes an id whose prefix matches the current project to this checkout, so the tool does what it is told; the rule is missing. Done: the flow skill states where the record lives: from the worktree's creation to the merge, every tasks write for the task and its children runs in the worktree (tasks -C .worktrees/<name> or from inside it), and the main checkout's copy is left alone; a reviewer or implementer brief names absolute worktree paths and tells the agent to stop on a failed cd rather than fall back. Where: agents/skills/flow/SKILL.md rule 1 or a short 'Where the record lives' paragraph beside the closing sequence. Not here: a tasks-side warning when a record is written in one checkout while another worktree holds a modified copy — filed as tool feedback. Check: the paragraph is present; the next flow task's gate notes all land in its worktree commit. Source: retro curation pass ai-c78706.

## Notes

- 2026-09-24T14:50:06Z (main): scope: scoped; body rewritten with the third instance (ai-99ea5d, 2026-09-24), todo P2 s low direct; the tool-side warning goes to tasks as feedback; associated with ai-756baa via ai-c78706, not parented
- 2026-09-24T14:50:21Z (main): tool feedback filed as tasks-bb53e5
- 2026-09-24T14:54:20Z (main): started
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T14:54:28Z (feat/flow-promotions): gate: scoped — adopted
- 2026-09-24T14:54:28Z (feat/flow-promotions): gate: implementing — worktree .worktrees/flow-promotions (feat/flow-promotions), landing with the other three retro promotions
- 2026-09-24T15:01:07Z (feat/flow-promotions): gate: verified tree:e90a6fca17648a0041164c866d8ebba42ddc163c — checks: pytest agents/bin 382 passed and tasks check clean and skill row read against spec 3.2 row; review: important addressed rule covered writes but not reads, important addressed start and park read as safe from the main checkout, minor addressed path rule applied to reviewer briefs only, minor addressed planned child worktree was ambiguous, minor addressed parent invalidation note had no home; reviewer: claude-code/claude-opus-5-5[1m]
- 2026-09-24T15:01:18Z (feat/flow-promotions): retro: the rule I wrote covered the failure I had today (a write) and missed the one in the retro that motivated it (a read); stating the rule from all three instances rather than the freshest took a second review round.
- 2026-09-24T15:01:19Z (feat/flow-promotions): done
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T15:01:19Z (feat/flow-promotions): flow skill and spec carry the promotion from the ai-c78706 retro pass
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
