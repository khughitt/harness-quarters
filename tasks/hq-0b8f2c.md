---
id: hq-0b8f2c
title: Probe whether a resumed Claude successor session reads its linked subagent transcript
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: probe-successor-link
created: 2026-10-23T00:09:51Z
updated: 2026-10-23T02:27:14Z
started: 2026-10-23T01:33:10Z
depends: []
parent: hq-401088
tags: []
agent: claude-code/claude-opus-5-5
---

Question: Does Claude Code, on resuming a successor session or reading its history, open <new>/subagents/agent-<id>.jsonl through its link, and what happens when the link dangles?

Where to start: [ref:brief] records rules 2–3 (keep a unit another session links into), which are a policy gate resting on this unknown. If Claude never reads it, a dangling link may cost nothing and rule 2 can be dropped; if it does, the 30-versus-90-day retention argument stands. Keep this separate from the proven linking-unit quarantine-release failure.

Bound: An isolated Claude Code home only (no live store). Create a predecessor/successor pair the way the harness does (hand a running background agent to a successor) or, if that cannot be driven, a hand-made link of the same shape; then resume the successor and observe reads of the linked path (strace -e openat, or the transcript/UI) with the link resolving and dangling. Record the result as a capability fact through tools/harness-facts, with the probe under claude/probes/. No live-home changes or retention implementation.

Expected result: Record a fact naming whether resume reads the linked transcript and what happens when it dangles, cite it on hq-1639fd and update the brief. Distinguish a harness-created pair from a hand-made fixture and identify any observation limit; recommend whether the target-retention policy is justified by the result.

Ideas it wakes: On completion, run `tasks note hq-1639fd --no-reviewed "<finding and capability fact>"` before this result's branch merges.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — findings, rules 1-3 and the open questions

## Notes

- 2026-10-23T01:33:10Z (main): started
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T01:33:20Z (main): arm: flow-trial-1 — unit tack-401088 — not enrolled
- 2026-10-23T01:38:27Z (probe-successor-link): resumed
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T01:38:27Z (probe-successor-link): static read of Claude Code 2.1.304 (also 2.1.296/2.1.302): an [adopt] handoff hard-links agent-<id>.jsonl/.meta.json into the successor (copy fallback), and a 'relink sweep' on resume converts symlinked agent-* names in the session's subagents/ to hard links or copies, gated on storageV5 (z() && storageV5). The live hq pair was linked under 2.1.304 yet is a symlink, so the sweep/adopt path is not what ran here. Session listing filters subagents/ entries with Dirent.isFile(), skipping symlinks.
- 2026-10-23T02:06:55Z (probe-successor-link): attached: successor-link-probe-2026-10-22.jsonl (3345 bytes): Final successor-link-probe run on Claude Code 2.1.304 at 7107937: four resumes (headless and interactive, link resolving and dangling), outcome false
- 2026-10-23T02:07:02Z (probe-successor-link): probe at 7107937: hand-made pair (O finished background agent, N --fork-session copy, absolute link + regular meta in N/subagents), 4 resumes per run (headless -p --resume and TUI --resume in private tmux; link resolving and O's unit moved aside) under strace -ff -y: no syscall named anything under N/subagents, no io_uring ring, all exited 0 and replied, link unchanged; 3 runs agreed, outcome false. Harness-made pair not reproduced: claude --bg --resume of a running O started a copy without the agent; /background offered to stop it. Live pairs are bg-session takeovers (sessionKind bg, session_cron_carry). just test: 228, 1017, 389, 1 passed. Review dispatched.
- 2026-10-23T02:14:13Z (probe-successor-link): review: impl round 1 — verdict: revise; findings: Critical 1, Important 3, Minor 13; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T02:27:13Z (probe-successor-link): detached: successor-link-probe-2026-10-22.jsonl: superseded: that run was of a draft revision (7107937); the recorded run is now the one at a942426
- 2026-10-23T02:27:13Z (probe-successor-link): attached: successor-link-probe-a942426.jsonl (3610 bytes): successor-link-probe run on Claude Code 2.1.304 with the probe at a942426: four resumes (headless and interactive, link resolving and dangling), outcome false
