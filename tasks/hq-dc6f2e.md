---
id: hq-dc6f2e
title: Shell wrapper cleanup refusal prevents bounded diagnostic capture
status: shelved
priority: 2
created: 2026-10-30T03:24:25Z
updated: 2026-10-31T02:18:34Z
depends: []
parent: hq-40a8d0
tags: [feedback, friction, "from:sun"]
agent: codex
origin: agent
---

A bounded read-only diagnostic wrapper captured stdout and stderr in temporary files and registered cleanup on exit. The shell tool rejected the command before execution because rm -f style commands were disallowed, despite the files being created by that same wrapper. Capturing both streams in memory avoided the cleanup command and completed the authorized single invocation without a retry against the source.

## References

- brief (context, kind=brief): docs/notes/2026-10-15-headless-workers-brief.md — verified memory-capture workaround and wake condition

## Notes

- 2026-10-30T03:24:25Z (feedback): created
  provenance: {"harness_session":"codex:01a18ab4-a56f-7341-8244-8b69059d7b4a","harness_session_source":"CODEX_THREAD_ID","root_session":"codex:01a18943-2b9d-7e50-926f-b74169571349","origin":"agent"}
- 2026-10-31T02:18:32Z (main): shelved: Wake when an authorized bounded diagnostic needs file-backed capture that in-memory capture cannot satisfy, or the refusal recurs without a safe supported capture route; retain the exact rejection and one-executed-invocation evidence. No permission-policy relaxation is implied.
- 2026-10-31T02:18:34Z (main): scope: shelved; wrapper rejection occurred before execution, and bounded in-memory capture completed the sole authorized invocation (stdout done, empty stderr, exit 0); retain report rather than implement a permission-policy change. Wake condition recorded by shelve. origin: filing matched, Codex 0.165.0 worker 01a18ab4-a56f-7341-8244-8b69059d7b4a call/result 295/299, created at 2026-10-30T03:24:25Z; failure 256/259 and replacement 263/274, root 01a18943-2b9d-7e50-926f-b74169571349. Agent-derived tool observation, origin agent retained; no older origin_session named. Upstream screen and its limits are in the brief; brief: docs/notes/2026-10-15-headless-workers-brief.md
  provenance: {"harness_session":"codex:01a18fb8-ef00-7453-afd2-031b4fb7abe9","harness_session_source":"CODEX_THREAD_ID"}
