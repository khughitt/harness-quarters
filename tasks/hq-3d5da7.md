---
id: hq-3d5da7
title: Design cited transcript preservation from the brief
status: todo
priority: 2
size: m
complexity: high
process: planned
created: 2026-10-29T18:40:44Z
updated: 2026-10-29T18:40:44Z
depends: []
parent: hq-cff824
tags: [session-logs]
source: hq-f127d1
agent: codex
origin: agent
---

Why: hq-f127d1 captures a real preservation workaround: resolve session:line citations, retain the cited transcript lines byte for byte, keep the nearest earlier assistant message beside each cited human turn, and emit a row map with each raw line's SHA-256 and the whole store file's hash. The reader already resolves records, identifies roles and pairs calls/results, but its normalized/capped raw display is not a byte-exact export. [ref:brief] preserves the capture and its matched filing evidence.

Done: a user-reviewed design and then a separately reviewed implementation plan define the smallest local excerpt-and-map export that preserves every captured requirement, reusing the obs-owned reader for discovery and classification. Decide command ownership and syntax, citation identity and ambiguity, exact byte/newline and row-map formats, duplicate/overlapping citations, source-file mutation while hashing, and explicit unavailable/changed outcomes. Specify how to keep earlier assistant context and report absent or ambiguous context without asserting that adjacency proves approval. Keep raw private evidence distinct from any portable derivative; settle local destination permissions and safe failure/overwrite behavior before implementation. No automatic publishing, store mutation, pruning, new index or second transcript classifier.

Verification in the plan: small fixture cases compare exported bytes and per-row/source hashes with the source, including non-ASCII or undecodable bytes, missing final newline, duplicate citations, block references sharing one physical line, absent assistant context, changed/missing sources and failed writes. Preserve partial-failure evidence honestly; a normalized raw string cannot stand in for original bytes.

Where to look: [ref:brief]; docs/specs/2026-10-23-session-evidence-reader-design.md sections 3, 4.1, 5.5, 7.3 and 11; obs session_logs_lines.py, session_logs_read.py::shaped/raw_lines and session_logs_show.py. The brief's filing-session evidence describes the hand-written capture; inspect only the needed source inputs. Existing lore-2d31f3 owns reversible placeholder-derivative tooling, so do not duplicate it. Reassess the trial gate before implementation/activation; planning does not authorize skill, home-link or measurement edits.

Ideas it wakes: On completion, run `tasks note hq-f127d1 --no-reviewed "<design decisions, accepted revisions and remaining limits>"` and update [ref:brief] before this result's branch merges.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-25-task-origin-lookup-brief.md — delivered reader, evidence limits and design questions
- reader-spec (input, required, kind=spec): docs/specs/2026-10-23-session-evidence-reader-design.md — ownership boundary, existing stream contract and trial gate

## Notes

- 2026-10-29T18:40:44Z (add): created
  provenance: {"harness_session":"codex:01a188e9-adb7-7061-abd2-4d81fbf33dd1","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
