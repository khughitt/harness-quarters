---
id: hq-3b9c4c
title: Require verified obs readiness before session-archive pruning
status: todo
priority: 2
size: m
complexity: mid
process: planned
created: 2026-10-15T18:47:21Z
updated: 2026-10-15T18:47:21Z
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
