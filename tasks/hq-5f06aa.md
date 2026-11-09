---
id: hq-5f06aa
title: Move harness-remap from ops into hq as hq remap
status: todo
priority: 3
size: s
complexity: mid
process: direct
defer: 2026-11-09
created: 2026-10-19T11:56:10Z
updated: 2026-11-09T10:15:13Z
depends: []
related: [ops-630a87, ops-8a43e3, ops-65687f]
tags: []
source: ops-630a87 boundary-proposal-r3.md A7
agent: claude-code/claude-opus-5-5
---

Why: rewriting session stores after a checkout move is part of their file lifecycle, which hq owns (revision 3, A7). Interface unchanged; it also learns every declared home instead of the fixed defaults. Deferred past enrollment: hq is enrolled and obs indexes the stores it rewrites. Before landing, pass the flow-trial-1 gate (revision 3, change 5): judge the step's effect on what enrolled sessions see and what obs and the verdict tools measure; a step that changes either waits for readout (2027-02-16).

## Notes

- 2026-10-19T12:06:42Z (main): The 2026-11-30 deferral is the date to reassess this step against flow-trial-1, not an authorization: nothing that affects treatment or measurement lands before readout (2027-02-16) (owner review 2026-10-19).
- 2026-11-08T16:16:23Z (main): Trial gate re-scoped 2026-11-08 at the user's request (flows records docs/notes/2026-11-08-flow-trial-1-gate-scope.md, superseding ops-630a87 change 5's wait-for-readout for flow-trial-1): no readout wait for treatment, since the change reaches both randomized arms alike. It sits on or near the verdict's measurement path, so before landing run the record's outcome-blind equivalence check (old vs new code, trial-arm census flow-trial-1 and obs --json outcomes report --cohort --units each piped straight to sha256sum, unread); equal digests land, unequal ones wait for read_on.
- 2026-11-08T21:13:27Z (main): ops-8a43e3 changed bin/harness-remap in ops (e5dfbe1): claude_transcript_fields covers wireIngestContext.<tool>.cwd, and verify checks it; carry that and its three tests in the move.
  provenance: {"harness_session":"claude-code:31eb8590-d28f-4885-a5b3-20f85ab8da59","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-09T10:15:13Z (main): Follow-up found by a scope pass on ops-65687f: real_paths()/directory_mapping() currently explain Claude project directories only from extant moved trees, claude.json and history. Removed worktrees can leave directories whose own transcripts still contain the real top-level cwd. After the ownership move, assess using that evidence, validating encode(cwd) against the containing directory and rejecting conflicting/ambiguous paths rather than inverting the lossy slug. The existing report observed seven such directories after the ops-8a43e3 fix. This is a future enhancement to assess in hq, not an expansion of this move task or authorization to rewrite live stores. ops-65687f stays shelved until this move closes or its dated checkpoint.
  provenance: {"harness_session":"codex:01a1bfca-1554-7a42-bafc-4e9671c90fad","harness_session_source":"CODEX_THREAD_ID"}
