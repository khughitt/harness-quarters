---
id: hq-07e3bf
title: Wire the capture notice hook into Claude Code and Codex SessionStart
status: done
priority: 2
size: s
complexity: low
process: direct
owner: feat/capture-notice-hook
created: 2026-10-09T17:59:17Z
updated: 2026-10-10T12:05:11Z
started: 2026-10-10T11:27:30Z
completed: 2026-10-10T12:05:09Z
depends: [ops-1aa710]
tags: [hooks]
source: "ops:docs/specs/2026-10-09-capture-triage-design.md#8"
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Register ops's hooks/capture-notice as a SessionStart hook in the Claude Code settings and in codex/hooks.json (personal; leave hooks.work.json alone), refreshing Codex's trusted hash through hq's usual path. Done when a fresh Claude Code session and a fresh Codex session each show the notice line for a known nonzero pending count, and nothing when it is zero. Piece of ops-2bad69; spec ops docs/specs/2026-10-09-capture-triage-design.md §8.

## Notes

- 2026-10-10T11:27:30Z (main): started
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T11:27:34Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-10T11:27:34Z (main): arm: flow-trial-1 — unit tack-07e3bf — flow off
- 2026-10-10T11:28:22Z (feat/capture-notice-hook): resumed
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T11:42:17Z (feat/capture-notice-hook): Wired in 47d9193 (ff-merged to main, live): claude/settings.json and codex/hooks.json SessionStart (appended at codex index 2 so existing trust keys hold); work homes untouched. Claude Code verified: fresh claude -p session's SessionStart:startup hook_response carried 'captures: 2 awaiting triage, oldest 2026-10-09' and the model quoted it. Codex 0.162.1 exec ran only 3 SessionStart hooks: session_start:2:0 untrusted until /hooks. Zero/no-store path checked at hook level only (empty stdout under a store-less HOME).
- 2026-10-10T11:42:17Z (feat/capture-notice-hook): parked (waiting on user, approval): User: in an interactive Codex session in the personal home, run /hooks and trust the SessionStart entry ~/d/ops/hooks/capture-notice (session_start:2:0). Agent then: commit the new trusted_hash in codex/config.toml from main (chore(codex)), rerun codex exec to confirm the captures line, tasks done in the worktree's record, merge the record, remove .worktrees/capture-notice-hook (unlock, tt-report first).
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T12:05:09Z (feat/capture-notice-hook): resumed
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T12:05:09Z (feat/capture-notice-hook): review: impl round 1 — verdict: accept; findings: none; reviewer: human
- 2026-10-10T12:05:09Z (feat/capture-notice-hook): done
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T12:05:09Z (feat/capture-notice-hook): capture-notice runs at SessionStart in the personal Claude Code and Codex homes (47d9193; trust hash committed on main). Fresh claude -p and codex exec sessions each carried 'captures: 2 awaiting triage, oldest 2026-10-09'. The zero case was checked only at hook level (empty stdout under a store-less HOME) plus ops's tests; no live zero queue.
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
