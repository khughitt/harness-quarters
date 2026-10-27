---
id: hq-3b9c4c
title: Require verified obs readiness before session-archive pruning
status: doing
priority: 2
size: m
complexity: mid
process: planned
owner: main
created: 2026-10-15T18:47:21Z
updated: 2026-10-27T21:06:37Z
started: 2026-10-27T21:06:37Z
depends: [obs-c7d924]
parent: hq-401088
tags: [obs]
source: obs-c7d924
agent: codex
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
