---
id: hq-1adbfe
title: Claude root-session location queries no longer see phantom parent rows from child request records
status: dropped
priority: 2
created: 2026-10-20T20:17:51Z
updated: 2026-10-22T17:45:42Z
closed: 2026-10-22T17:45:42Z
depends: []
parent: hq-cff824
tags: [feedback, positive, "from:obs"]
agent: codex
---

After the child-request routing fix and successful live index renewal, the count of subagent=0 session rows in child transcript files is zero (previously 150). A Claude root ID's subagent=0 rows now live only in its root transcript file; agentId request records without isSidechain route to the child.

## References

- brief (context, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — incorporates the completed root-row fix and retained candidate contract

## Notes

- 2026-10-22T17:41:59Z (main): scope: drop; positive result already delivered by obs-b99310, fix 54ce9e187b825dc7ace6ff23ba9820e172b1f89c. Its completion records successful live renewal of 6432 Claude files and zero subagent=0 rows in child transcript paths (previously 150); 1179 tests and independent review accepted. Incorporated this dated outcome in the existing store-reach brief, preserving the historical O10 counterexample and candidate-level availability requirement; associated with hq-cff824; original source body unchanged. No new implementation or research; brief: docs/notes/2026-10-20-session-store-reach-brief.md; proposal: drop as delivered by obs-b99310 and its fix commit
- 2026-10-22T17:45:42Z (main): dropped
  provenance: {"harness_session":"codex:01a16498-3bbd-7173-9be1-15d1de967c6f","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-22T17:45:42Z (main): User approved drop: delivered by obs-b99310, fix 54ce9e187b825dc7ace6ff23ba9820e172b1f89c. Dated verification and brief reference retained.
  provenance: {"harness_session":"codex:01a16498-3bbd-7173-9be1-15d1de967c6f","harness_session_source":"CODEX_THREAD_ID"}
