---
id: tack-ae8196
title: Path mistakes in worktrees and stale skill paths drive most file-not-found errors
status: dropped
priority: "2"
created: 2026-09-26T20:51:42Z
updated: 2026-09-27T13:06:25Z
depends: []
parent: tack-e2ed51
tags: [rules, skills, obs]
source: "obs:docs/reports/2026-09-26-tool-failure-modes.md"
agent: claude-code/claude-opus-5-5
---

Measured in obs (docs/reports/2026-09-26-tool-failure-modes.md §2–3 in the obs checkout): 112 of 395 Claude Code Read errors are a worktree session reading the main-checkout path of a file that exists only on the branch (28% failure rate against 0.6% for its own worktree; mostly Opus 4.7, top-level sessions). 88 more, plus 75 Bash errors, come from headless sdk-py reviewer sessions started in a worktree already removed; the launcher is not in ai, ops, relay or tasks and is still unknown. In Codex, 35% of file-not-found failures are reads of plugin skill files at stale paths (missing subdirectory, old version numbers). Question: does the worktree path rule need restating for the agent (not just the user-facing path convention), who launches the sdk-py reviewers and removes their worktree first, and how skills should reference their own files so Codex resolves them.

## Notes

- 2026-09-27T11:21:15Z (main): scope: briefed; the sdk-py reviewer is the security-guidance plugin (all Claude Code worktree Read failures in the store are its sessions, so the worktree rule needs no restating), and Codex misreads come from alias expansion over the nested agents/skills layout; parented under goal ai-e2ed51 with research ai-3b2222 (reviewer keep or disable) and ai-929d4f (flat skill layout); brief: docs/notes/2026-09-27-path-mistakes-brief.md
- 2026-09-27T12:00:27Z (main): finding (ai-3b2222): the security reviewer ran 1,335 sessions (~$556 list) for one delivered finding, fixed as ops 64fddd4; recommendation disable, awaiting the user's decision. Codex layout research ai-929d4f still open.
- 2026-09-27T12:10:30Z (main): finding (ai-929d4f): the Codex misreads trace to the nested agents/skills layout and a duplicate, drifting superpowers copy; fix filed as ai-cea269. Remaining alias and skill-relative misreads are upstream Codex.
- 2026-09-27T13:05:54Z (main): scope: drop; all three questions answered and fixed — worktree rule needs no restating (every worktree Read failure was the security reviewer), reviewer disabled (8d701d6), skills flattened and superpowers de-duplicated (f4f1a94, 86c3c77); brief: docs/notes/2026-09-27-path-mistakes-brief.md; proposal: drop as covered by ai-3b2222, ai-929d4f and ai-cea269
- 2026-09-27T13:06:25Z (main): dropped
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:06:25Z (main): covered by ai-3b2222, ai-929d4f, ai-cea269
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
