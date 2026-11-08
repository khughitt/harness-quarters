---
id: hq-adfed6
title: Keep a recoverable second copy of the session archive on another physical drive
status: doing
priority: 1
size: m
complexity: mid
process: planned
owner: feat/hq-adfed6-archive-replica
created: 2026-10-29T19:10:37Z
updated: 2026-11-08T02:08:31Z
started: 2026-11-08T02:03:40Z
depends: []
tags: []
source: ops-7b325c
agent: codex
origin: agent
spec: docs/specs/2026-11-07-session-archive-replica-design.md
---

Why: ops-7b325c preserves the P1 request for a second copy of the coding-agent session archive on a different physical drive. Hq owns session-archive and its user units. Scope evidence on 2026-10-29: hq c88e5c5; tools/session_archive/cli.py takes config.archive_lock for capture, prune, promote and probe-codex; config.py uses an exclusive flock on the archive .lock; the capture timer is 04:00, not 04:01. The primary archive contains the five source trees, versions/ and manifest.sqlite. The candidate secondary mount is a separate physical disk with about 2.3 TiB available; its proposed agent-sessions destination does not exist. Its host-specific location is in the source task's preserved capture.

Approach: prepare the second copy in hq, reusing the archiver's consistency boundary. Prefer a daily incremental copy coordinated with the same archive lock over a clock-only rsync after capture. Copy the manifest and the bytes it describes as one consistent generation, including versions/ and linked Claude transcript dependencies. Prefer the existing secondary drive over buying or requiring removable storage. These are scoping recommendations for the written design, not permission to activate a host timer.

Done: reviewed design and implementation plan; a recoverable second copy on a verified different physical device; explicit source and destination mount checks that refuse absent or wrong mounts; interruption, lock contention and copy failure cannot report an incomplete replica as verified or damage the primary archive; a defined daily schedule with observable failure reporting; and a documented periodic restore check that opens a copied manifest and checks representative transcript hashes and readability in scratch, never in live harness homes. Prove the small fixture route end to end before a full archive copy. Preserve the last verified recovery state across failed copies. Prepare the exact host activation and rollback commands for approval before enabling units or making the first live replica. Keep the separate historical-import task hq-ef1cb3 independent: replication must include any later imported source without waiting for that import.

Where: tools/session_archive/{cli,config,manifest,capture}.py, tools/test_session_archive_*.py, systemd/user/session-archive-capture.{service,timer}, README.md, and [ref:archive-design] for the existing archive invariants. Add the design and plan in this project's declared locations. Follow its current focused test and hygiene routes; do not infer broad-suite policy from another checkout. No new CLI option is authorized without the shared cli.toml-first workflow.

Boundary: this is archive redundancy, not a new retention engine, changes to prune eligibility, an off-site backup service, or the historical import. No host activation is authorized by this scope pass.

## References

- archive-design (input, required, kind=spec): docs/specs/2026-09-30-session-archive-design.md — existing archive consistency and restore invariants

## Notes

- 2026-10-29T19:10:37Z (add): created
  provenance: {"harness_session":"codex:01a1890f-0da2-7732-a4ba-e64c6a17d627","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-08T02:03:40Z (main): started
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T02:04:04Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-08T02:04:06Z (main): arm: flow-trial-1 — unit tack-adfed6 — flow on
- 2026-11-08T02:04:24Z (main): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T02:04:41Z (feat/hq-adfed6-archive-replica): resumed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T02:08:31Z (feat/hq-adfed6-archive-replica): origin: stage 1 matched — user request at claude-code:77c3552c-2013-4e7a-a286-520748289fe9 L940 (2026-10-28): store copies of the archive on a second drive, daily rsync?, in case of hard drive failures; lock coordination, consistent manifest, mount checks, verified-state retention and restore check were added by the filing and scope agents (ops-7b325c, hq-adfed6); origin mixed confirmed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
