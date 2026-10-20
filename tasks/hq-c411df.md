---
id: hq-c411df
title: "session-episodes reads only the default Claude projects store and Codex sessions store, so a scoping or audit agent cannot reach a report's origin session in a second harness home, Codex archived sessions, the backup archive or another host"
status: idea
priority: 2
created: 2026-10-20T11:19:18Z
updated: 2026-10-20T16:05:26Z
depends: []
parent: hq-cff824
tags: [feedback, gap, "from:lore"]
agent: claude-code
---

Found while checking whether stamped friction reports can be traced to their origin sessions: the reader's default roots are the primary Claude projects store and the primary Codex sessions store, each overridable by one environment variable, so one run covers one store per harness. A report whose origin is in another home, an archived rollout or the post-prune archive, or on the other host, gives no result and no explicit unavailable status. Acceptance for the friction-context work needs retrieval from a live transcript, its archived copy and another host, or an explicit unavailable result.

## References

- brief (input, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — context and questions for this work

## Notes

- 2026-10-20T11:41:10Z (main): Audit evidence, 2026-10-20: locating the origins of 72 feedback reports needed three reader capabilities session-episodes lacks. (1) Anchoring on a CLI call's output when the command text differs from the stored record (9 of 72). (2) Following a Codex subagent to its parent thread, since the child's dispatch brief is stored as encrypted_content (6 of 72). (3) Searching the work homes and archived_sessions as well as the default stores. Every origin found was on one host; the other host held none.
  provenance: {"harness_session":"claude-code:737a5757-83af-4e31-9fdd-4ce70dd9e6f1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
