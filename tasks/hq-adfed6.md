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
updated: 2026-11-08T11:09:46Z
started: 2026-11-08T02:03:40Z
depends: []
related: [hq-c58737, hq-405212]
tags: []
source: ops-7b325c
agent: codex
origin: agent
spec: docs/specs/2026-11-07-session-archive-replica-design.md
plan: docs/plans/2026-11-08-session-archive-replica.md
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
- 2026-11-08T02:08:33Z (feat/hq-adfed6-archive-replica): design draft committed 1a09a6e3 on feat/hq-adfed6-archive-replica: docs/specs/2026-11-07-session-archive-replica-design.md; manifest-driven Python replicate into hard-linked dated generations under the archive lock, monthly full-hash verify-replica, status staleness; rsync in place and rsync --link-dest rejected (spec 3.3); no new CLI options, session-archive is outside ops cli.toml inventory; read-only host facts: archive on sdc 38G 37135 rows journal_mode delete, candidate replica mount on sdb 2.2T free
- 2026-11-08T02:08:38Z (feat/hq-adfed6-archive-replica): parked (waiting on user, review): User reviews the design at .worktrees/hq-adfed6/docs/specs/2026-11-07-session-archive-replica-design.md (commit 1a09a6e3); on approval the agent records gate designed and writes the implementation plan
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:06:56Z (feat/hq-adfed6-archive-replica): resumed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:06:58Z (feat/hq-adfed6-archive-replica): review: spec round 1 — verdict: revise; findings: important 3, minor 3; reviewer: agy
- 2026-11-08T10:08:14Z (feat/hq-adfed6-archive-replica): spec revision 2 at e46d5e87bdda51a54b3279661cfe20a6de2053c1 addresses round 1: I1 main skips check_sources for replicate and verify-replica, I2 load_config parses replica_root only and status reports replica health without raising (receipt finished_at age, failed last replicate unhealthy at once, no row on restored archive tolerated), I3 disks_of resolver injected via cli module attribute, in-process CLI fixture route, real resolver refuses same-filesystem fixtures in subprocess; minors: microsecond stamps from injected clock with collision refusal, connection closed and lstat before link, per-line bytes json.loads on every .jsonl row incl versions
- 2026-11-08T10:08:16Z (feat/hq-adfed6-archive-replica): parked (waiting on user, review): User (or a reviewer the user names) reviews spec revision 2 at .worktrees/hq-adfed6/docs/specs/2026-11-07-session-archive-replica-design.md, commit e46d5e87bdda51a54b3279661cfe20a6de2053c1; on approval the agent records gate designed and writes the implementation plan
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:23:16Z (feat/hq-adfed6-archive-replica): resumed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:23:18Z (feat/hq-adfed6-archive-replica): review: spec round 2 — verdict: accept; findings: none; reviewer: agy/gemini-4-argon
- 2026-11-08T10:23:20Z (feat/hq-adfed6-archive-replica): gate: designed docs/specs/2026-11-07-session-archive-replica-design.md — user approved revision e46d5e87 for planning on 2026-11-08 after agy review rounds 1 and 2
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:25:50Z (feat/hq-adfed6-archive-replica): plan draft committed 27d32f4aed2955cf165556146cf4a7c9cb97c4a1: docs/plans/2026-11-08-session-archive-replica.md, eight tasks filed as children hq-4bff46 hq-dba11e hq-a16a3a hq-f3d66a hq-98889c hq-d1a549 hq-82694d hq-405212 (Task 8 is live activation after merge, each step approval-gated); tasks check clean apart from pre-existing hq-c58737 growth warning
- 2026-11-08T10:25:52Z (feat/hq-adfed6-archive-replica): parked (waiting on user, review): User (or a reviewer the user names) reviews the plan at .worktrees/hq-adfed6/docs/plans/2026-11-08-session-archive-replica.md, commit 27d32f4aed2955cf165556146cf4a7c9cb97c4a1; on approval the agent records gate planned and starts Task 1 (hq-4bff46) under execution Setup
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:37:40Z (feat/hq-adfed6-archive-replica): resumed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:37:42Z (feat/hq-adfed6-archive-replica): review: plan round 1 — verdict: revise; findings: important 1, minor 3; reviewer: agy
- 2026-11-08T10:38:45Z (feat/hq-adfed6-archive-replica): plan revision 2 at 35c43a9f477d9b8aabe5803743e4ea5446679388: Task 8 becomes the separate rollout task hq-405212 (unparented, depends on hq-adfed6; ops-7b325c dep added after merge), sysfs realpath of slaves and fake-tree symlinks, explicit fsync_dir of every partial directory before publish, fixture route builds the archive with cli capture so status has its capture run
- 2026-11-08T10:38:47Z (feat/hq-adfed6-archive-replica): parked (waiting on user, review): User (or a reviewer the user names) reviews plan revision 2 at .worktrees/hq-adfed6/docs/plans/2026-11-08-session-archive-replica.md, commit 35c43a9f477d9b8aabe5803743e4ea5446679388; on approval the agent records gate planned and starts Task 1 (hq-4bff46) under execution Setup
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:48:14Z (feat/hq-adfed6-archive-replica): resumed
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:48:16Z (feat/hq-adfed6-archive-replica): review: plan round 2 — verdict: accept; findings: none; reviewer: agy
- 2026-11-08T10:48:19Z (feat/hq-adfed6-archive-replica): gate: planned docs/plans/2026-11-08-session-archive-replica.md — user accepted revision 35c43a9f on 2026-11-08 after agy plan review rounds 1 and 2, seven step children filed scoped, rollout hq-405212 separate
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T10:48:21Z (feat/hq-adfed6-archive-replica): parked (waiting on agent, session): Next agent, in a fresh session: open .worktrees/hq-adfed6 (branch feat/hq-adfed6-archive-replica, plan 35c43a9f), run execution Setup (plan workspace under WORK_ROOT/hq/hq-adfed6/plans/session-archive-replica/, focused baseline just test-one over tools/test_session_archive_*.py per the policy-off checkout), then tasks start hq-4bff46 and execute Tasks 1-7 per the plan; rollout hq-405212 waits for the merge. Retained: only this worktree; no scratch, process or host pointer.
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T11:09:46Z (feat/hq-adfed6-archive-replica): resumed
