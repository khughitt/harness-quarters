---
id: hq-3b9c4c
title: Require verified obs readiness before session-archive pruning
status: doing
priority: 2
size: m
complexity: mid
process: planned
owner: fix/hq-3b9c4c-strict-readiness
created: 2026-10-15T18:47:21Z
updated: 2026-10-27T22:51:13Z
started: 2026-10-27T21:06:37Z
depends: [obs-c7d924]
parent: hq-401088
tags: [obs]
source: obs-c7d924
agent: codex
spec: docs/specs/2026-09-30-session-archive-design.md
---

Why: obs-c7d924 verified that the existing retention consumer accepts stale extractor evidence, inode replacement and unfinished no-newline tails, and ignores additive ready/version fields. A same-size rewrite preserving inode/mtime also passes existing checks, so live/archive hash equality does not prove equality with the bytes obs indexed. Capture remains independent; prune rollout must remain gated.

Bound: revise the retention design and implementation plan for human review, then update tools/session_archive/inputs.py, decide.py and connected prune facts/tests to consume the coordinated obs-0bc168 readiness contract. Require its explicit contract version, ready/reasons, complete read/no partial tail, source-scoped inode/device evidence, and indexed-span length/SHA-256. Reject absent, malformed, stale, conflicting or unsupported evidence; compare exported version/digest against the consumer's fresh file observation and existing archive read-back. Retain inactivity and writer-exclusion checks. Remove the current incomplete-tail exception. Codex filename/metadata identity disagreement must block eligibility rather than silently choosing a deletion identity.

Rollout: install the strict consumer first while pruning is gated, so it fails closed against the old producer; an additive version field cannot protect an old consumer that ignores it. Coordinate final field names and semantics with obs-0bc168. No live capture, deletion or timer enablement belongs in this task; hq-624351 continues to own prune rollout.

Where: obs docs/notes/2026-10-03-transcript-index-readiness-brief.md, its saved 2026-10-15 evidence, and tools/retention_readiness.py; existing hq docs/specs/2026-09-30-session-archive-design.md and docs/plans/2026-09-30-session-archive.md. The runnable probe accepts the hq checkout path and exercises the actual input parser/eligibility decision with temporary data.

Done: reviewed design and plan, implementation and focused checks proving valid complete evidence passes while old/missing contract fields, stale extractors, partial tails, changed inode, changed indexed-byte digest and identity conflicts are retained; existing capture and archive safeguards pass their regression checks. Record the strict-consumer-first deployment requirement on hq-624351. No duplicate obs readiness or archive-alias implementation.

## Notes

- 2026-10-15T18:47:30Z (main): concerns: hq-56ef18 extension — Enforce the stronger readiness contract established by obs-c7d924; the completed input reader implemented the earlier schema-only contract.
- 2026-10-17T12:38:31Z (main): obs-0bc168 landed (obs c18e0cb): the field contract is obs docs/specs/2026-10-16-index-state-readiness-design.md rev 3 (§3 contract 2, §9 consumer duties: require contract == 2, ready, non-null indexed_span; compare device/inode with its own fstat; require indexed_span.length == live size; hash live file and archive copy against indexed_span.sha256; drop the partial-tail exception; block Codex identity codes; never reject an unfamiliar reason code). Acceptance: run obs tools/retention_readiness.py <hq> --strict-rev <landing commit>; it asserts the strict reader accepts only current/claude_current.
- 2026-10-22T23:56:11Z (cbcc14-prune-links): From hq-cbcc14 review: load_obs_state keys rows by os.path.realpath, so an obs row for a link path (obs keeps them, missing_since_ms stamped) folds onto its target's key and raises a conflict -> ObsUnavailable, stopping dry runs and applies. The strict reader should key by exact path (or by device/inode only with link-path and missing rows dropped: pre-obs-396637 link rows carry the target's identity). Hard gate for hq-624351.
- 2026-10-23T01:30:14Z (survey-successor-links): hq-d59a7b: the obs-reader halt fires against today's index. obs index-state (schema 15, 25,475 rows) keeps rows for both live link paths (missing_since 2026-10-21 06:00) beside their targets' rows (missing_since null); load_obs_state folds them by realpath and raises ObsUnavailable on the beliefs target, so every dry run and apply on this host halts now. See the brief's 'Live survey'.
- 2026-10-27T21:06:37Z (main): started
  provenance: {"harness_session":"codex:01a17f2d-dfcc-7ac3-a3d0-4496340daaf2","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T21:06:50Z (main): arm: flow-trial-1 — unit tack-401088 — not enrolled
- 2026-10-27T21:07:06Z (fix/hq-3b9c4c-strict-readiness): resumed
  provenance: {"harness_session":"codex:01a17f2d-dfcc-7ac3-a3d0-4496340daaf2","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T21:08:19Z (fix/hq-3b9c4c-strict-readiness): Origin recovered from codex:01a140bd-8e8d-7782-8ce2-1adc69d9a580, human turn at rollout line 455: user asked whether follow-ups should be created. The assistant proposed and filed the strict consumer at lines 469/478; detailed scope is agent-derived from obs-c7d924. Producer contract 2 is implemented in obs index_state.py and revision-3 design. Current hq still permits incomplete tails and keys rows by realpath. Recommendation: extend the existing reader, facts and decision path; preserve deletion protocols and separate rollout ownership. Planned work: just setup completed; baseline deferred to execution Setup before first code change.
- 2026-10-27T21:17:24Z (fix/hq-3b9c4c-strict-readiness): Design-phase verification: just test passed in hydrated .worktrees/hq-3b9c4c, segments 231 + 1051 + 391 + 1 = 1674 tests (154 deselected only in final isolated-test segment). tools/harness-facts check, tasks check and git diff --check passed. No runtime code changed. Execution still re-enters Setup and records its baseline before its first code change.
- 2026-10-27T21:18:03Z (fix/hq-3b9c4c-strict-readiness): retained: {"host": "titan", "kind": "worktree", "path": ".worktrees/hq-3b9c4c", "state": "kept", "verification": "verified", "purpose": "Frozen strict-readiness design review, then implementation-plan review and execution; branch fix/hq-3b9c4c-strict-readiness, design revision e07e23c3a32d15ff288c0846ab6a53444dc63347", "next_owner": "task:hq-3b9c4c", "cleanup_trigger": "After reviewed implementation integrates, inspect ignored evidence, harvest timings and check host pointers before considering removal"}
- 2026-10-27T21:18:58Z (fix/hq-3b9c4c-strict-readiness): review: spec round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
- 2026-10-27T21:19:00Z (fix/hq-3b9c4c-strict-readiness): attached: builder-check-report.md (335 bytes): Full read-only builder check of frozen strict consumer design revision e07e23c; reviewer codex/gpt-6.1-sol; no findings.
- 2026-10-27T21:19:02Z (fix/hq-3b9c4c-strict-readiness): retained: {"host": "titan", "kind": "evidence", "path": ".worktrees/hq-3b9c4c/.superpowers/sdd/hq-3b9c4c", "state": "kept", "verification": "verified", "purpose": "Full builder-check report for frozen design e07e23c, also attached as builder-check-report.md; no findings or deferred minors", "next_owner": "task:hq-3b9c4c", "cleanup_trigger": "After implementation integrates, verify attachment preservation and reassess this duplicate report with the worktree", "manifest": ".worktrees/hq-3b9c4c/.superpowers/sdd/hq-3b9c4c/manifest.sha256", "sha256": "4a0f33575b7232fee78f13340af6205b600833d284aa0225980bc5247df00794"}
- 2026-10-27T21:19:19Z (fix/hq-3b9c4c-strict-readiness): parked (waiting on user, review): User reviews hq design revision 2 at e07e23c3a32d15ff288c0846ab6a53444dc63347, docs/specs/2026-09-30-session-archive-design.md in .worktrees/hq-3b9c4c (especially section 3.4.0 and rollout). Builder check accepted with no findings; full just test passed 1674 tests. After approval, agent resumes here and revises the existing implementation plan for separate user review, including coordinated acceptance-probe adapter changes if needed. Runtime unchanged; no host pointers repointed.
  provenance: {"harness_session":"codex:01a17f2d-dfcc-7ac3-a3d0-4496340daaf2","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T22:43:02Z (fix/hq-3b9c4c-strict-readiness): resumed
  provenance: {"harness_session":"codex:01a17f2d-dfcc-7ac3-a3d0-4496340daaf2","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-27T22:43:05Z (fix/hq-3b9c4c-strict-readiness): review: spec round 2 — verdict: accept; findings: minor 8; reviewer: claude-code/claude-opus-5-5
- 2026-10-27T22:45:04Z (fix/hq-3b9c4c-strict-readiness): Round-2 review received via user, reviewer claude-code/claude-opus-5-5; recommendation accept with minor 8, not human approval. Full returned text saved in .superpowers/sdd/hq-3b9c4c/spec-round-2-report.md; portable attachment substitutes <obs-checkout> for /mnt/ssd/Dropbox/obs. Raw evidence remains under the retained worktree. All eight findings accepted and corrected in design revision 3; no deferred minors. Keep diagnostic counts non-blocking with mandatory archive preservation/replay: this matches producer policy and avoids indefinite retention of deliberately skipped record kinds. No live actions or source enablement.
- 2026-10-27T22:45:06Z (fix/hq-3b9c4c-strict-readiness): attached: spec-round-2-portable-report.md (5966 bytes): Portable derivative of full spec round 2 review (claude-code/claude-opus-5-5), accept with minor 8; <obs-checkout> mapping and retained raw report are recorded on the task.
- 2026-10-27T22:45:07Z (fix/hq-3b9c4c-strict-readiness): attached: review-ledger.md (3178 bytes): Round 2 dispositions for all eight minor design findings; each includes Why and Cost; none deferred. Revision 3 awaits human approval.
- 2026-10-27T22:51:13Z (fix/hq-3b9c4c-strict-readiness): retained: {"host": "titan", "kind": "evidence", "path": ".worktrees/hq-3b9c4c/.superpowers/sdd/hq-3b9c4c/spec-round-2-report.md", "state": "kept", "verification": "verified", "purpose": "Exact relayed round-2 review containing host paths; portable derivative attached as spec-round-2-portable-report.md, mapping in task note", "next_owner": "task:hq-3b9c4c", "cleanup_trigger": "After implementation integrates, verify preservation and decide whether to attach raw bytes under a shipped layout exemption before removal", "sha256": "b21b514137908a3ce234856d0a71fa910b527082e267ae2369ddf88d149e27b5"}
