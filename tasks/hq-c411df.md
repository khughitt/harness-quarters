---
id: hq-c411df
title: "session-episodes reads only the default Claude projects store and Codex sessions store, so a scoping or audit agent cannot reach a report's origin session in a second harness home, Codex archived sessions, the backup archive or another host"
status: idea
priority: 2
created: 2026-10-20T11:19:18Z
updated: 2026-10-20T19:31:48Z
depends: [hq-a1c591, hq-de3e4c]
parent: hq-cff824
tags: [feedback, gap, "from:lore"]
agent: claude-code
---

Found while checking whether stamped friction reports can be traced to their origin sessions: the reader's default roots are the primary Claude projects store and the primary Codex sessions store, each overridable by one environment variable, so one run covers one store per harness. A report whose origin is in another home, an archived rollout or the post-prune archive, or on the other host, gives no result and no explicit unavailable status. Acceptance for the friction-context work needs retrieval from a live transcript, its archived copy and another host, or an explicit unavailable result.

## References

- brief (input, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — context and questions for this work
- survey (input, required, kind=report): docs/notes/2026-10-20-session-log-survey.md — completed question and evidence survey

## Notes

- 2026-10-20T11:41:10Z (main): Audit evidence, 2026-10-20: locating the origins of 72 feedback reports needed three reader capabilities session-episodes lacks. (1) Anchoring on a CLI call's output when the command text differs from the stored record (9 of 72). (2) Following a Codex subagent to its parent thread, since the child's dispatch brief is stored as encrypted_content (6 of 72). (3) Searching the work homes and archived_sessions as well as the default stores. Every origin found was on one host; the other host held none.
  provenance: {"harness_session":"claude-code:737a5757-83af-4e31-9fdd-4ce70dd9e6f1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-20T16:05:27Z (main): scope: briefed; framed which tool owns report-origin lookup across stores (lean: an obs locate query over its index, which already covers all six roots, archive read_path, parent_session and missing state; rejected a new locate surface in hq, which would add a fifth store list); parented under goal hq-cff824; waits on research hq-a1c591; store-list alignment filed independently as hq-a60cf5; brief: docs/notes/2026-10-20-session-store-reach-brief.md
- 2026-10-20T16:34:45Z (main): scope addendum 2026-10-20: the user proposed an hq logs / hq trace CLI with a usage skill; survey hq-de3e4c now precedes the locate-owner decision, which folds into that CLI's design; hq-a1c591 (obs index coverage) remains an input
- 2026-10-20T17:30:21Z (docs/logs-survey): hq-de3e4c research input: docs/notes/2026-10-20-session-log-survey.md and the brief section 7 classify 183 episodes. Formats/behavior dominate; 64 need historical tool outputs, 32 parent links. Recommend search+show with metadata/raw streams, role filtering, paired results and coverage; trace composes typed evidence. No new find verb justified. Location ownership still depends on hq-a1c591; incorporate both results in the CLI design.
- 2026-10-20T17:45:51Z (docs/logs-survey): correction to hq-de3e4c preliminary parent count: raw re-audit confirms18 relationship episodes, including8 child-to-parent and12 parent-to-child (2 both). Only6 combine reverse binding with historical outputs. The corrected sample is183 episodes /1093 calls;64 need historical outputs. Use final report section Roles/evidence, not the earlier32 preliminary parent flags.
- 2026-10-20T18:09:23Z (main): Follow-up review: hq-6e5d88 now derives portable semantic acceptance cases from the completed survey; use them for search/show and evidence-link requirements. Avoid a duplicate CLI design task: this idea already owns that design after hq-a1c591. Reconcile it with the accepted boundary work ops-630a87 and obs-f5710b: obs is to own content parsing and session-logs, hq location/lifecycle and harness-version store samples. The transfer is deferred to 2027-02-17 after flow-trial-1 readout; parser ownership, the consumer interface and any effect on enrolled sessions or measurement are explicit design checks. The new corpus is data-only and does not execute that transfer. Automated trace precision still needs evaluation before a precision claim; a single surveyed batch is insufficient.
- 2026-10-20T19:31:48Z (docs/index-reach): hq-a1c591 research input: docs/notes/2026-10-20-session-index-reach.md and brief sections2/4–6. Existing obs index resolves20 sampled origin files and6 child-parent links to5 parents; content/output anchoring still requires a reader. Preserve per-file candidates and actual readability: O10 root-ID query returns root plus3 child files whose empty parent-ID rows all have subagent=0, while separate agent rows are correctly classified; gap obs-b99310. M01 missing file has a readable alternate under the same ID. Native archive/missing controls pass, but zero read_path rows means replayed-copy retrieval unobserved. Europa has no index at configured path. Recommend search+show using existing local metadata and accepted obs parsing ownership; no new index. Both research inputs are now available; fresh corrective review and final task closure precede branch integration.
