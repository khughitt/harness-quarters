---
id: hq-c411df
title: Design the session evidence reader and usage skill from completed studies
status: doing
priority: 2
size: m
complexity: high
process: planned
owner: session-evidence-reader
created: 2026-10-20T11:19:18Z
updated: 2026-10-23T16:11:27Z
started: 2026-10-23T12:40:18Z
depends: [hq-a1c591, hq-de3e4c]
parent: hq-cff824
tags: [feedback, gap, "from:lore"]
agent: claude-code
spec: docs/specs/2026-10-23-session-evidence-reader-design.md
plan: docs/plans/2026-10-23-session-evidence-reader.md
---

Why: Agents need evidence outside the baseline reader's two default roots, including historical tool outputs, parent context and explicit unavailable results. The user proposed a session-log CLI and usage skill; the existing record owns its design.

Established: hq-de3e4c completed a 183-episode / 1,093-call survey; 64 episodes require historical outputs, eight require child-to-parent and twelve parent-to-child links (two both). hq-a1c591 located 20 sampled origins and six child links to five parents using existing obs metadata. Replay-copy retrieval and general cross-host retrieval were not qualified. obs-b99310 fixed the phantom parent rows (54ce9e187b825dc7ace6ff23ba9820e172b1f89c); alternate files and per-file availability still require an explicit candidate contract. hq-6e5d88 delivered ten portable acceptance cases; hq-c1fecb owns their remaining fidelity corrections.

Done:
- Produce a design spec and implementation plan, each reviewed before the next phase. This task scopes the design and handoff; implementation tasks follow the reviewed plan.
- Specify a bounded search + show reader and usage skill: home/harness/date/session/role selection, normalized and raw record inspection, paired calls/results, block-level source references, recorded parent relationships, per-turn runtime model and coverage/unavailable results.
- Define the supported obs consumer interface and its owner. Reuse existing location metadata without treating the research SQL as an approved API. Respect ops-630a87 / obs-f5710b: obs owns content parsing and session-logs; hq owns location/lifecycle and harness-version samples. State the flow-trial-1 readout gate and assess effects on enrolled sessions and measurement before any rollout.
- Incorporate hq-b95324's final-message retrieval requirement through the same search/show surface: listing and printing by session, task or time window; final versus commentary across harnesses; injected records; interrupted/incomplete turns and absent final responses; source references; and task attribution that distinguishes ownership evidence from mentions. Map a focused acceptance case. On completion, run `tasks note hq-b95324 --no-reviewed "<reviewed contract and remaining work>"` before this result's branch merges so that idea is re-scoped against the reviewed design/plan.
- Map the design to the existing acceptance cases and location counterexamples, explicitly distinguishing synthetic coverage, fixture limitations and unobserved replay/remote cases. Settle local-first lookup versus explicit remote/archive operations in the design. Keep interactive resume selection separate.
- Use the brief's supported search/show recommendation. A second picker, a new transcript index, specialized aggregate verbs and automated trace precision claims are not established requirements. Later trace composition must retain typed evidence instead of treating mentions as work ownership. Leave hq-a60cf5, hq-7b131a, hq-c1fecb and hq-edf5de as their existing work.

Where: [ref:brief] consolidates the current lean, ownership constraints and remaining decisions; [ref:survey] provides the measured questions and limits; [ref:location-probe] provides candidate/read-path evidence; [ref:cases] supplies portable semantic acceptance. Relevant existing surfaces: agents/bin/session-episodes (_roots and store parsing), tools/hq_cli/sessions.py (resume discovery/selection), tools/session_archive/config.py (capture sources), and the session-logs skill.

## Original captured report

Found while checking whether stamped friction reports can be traced to their origin sessions: the reader's default roots are the primary Claude projects store and the primary Codex sessions store, each overridable by one environment variable, so one run covers one store per harness. A report whose origin is in another home, an archived rollout or the post-prune archive, or on the other host, gives no result and no explicit unavailable status. Acceptance for the friction-context work needs retrieval from a live transcript, its archived copy and another host, or an explicit unavailable result.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — completed findings, design direction and remaining decisions
- survey (input, required, kind=report): docs/notes/2026-10-20-session-log-survey.md — completed question and evidence survey
- location-probe (input, required, kind=report): docs/notes/2026-10-20-session-index-reach.md — file candidates, archive coverage and limits
- cases (input, required, kind=report): docs/notes/session-log-acceptance-cases.md — portable semantic acceptance and fixture limits

## Notes

- 2026-10-20T11:41:10Z (main): Audit evidence, 2026-10-20: locating the origins of 72 feedback reports needed three reader capabilities session-episodes lacks. (1) Anchoring on a CLI call's output when the command text differs from the stored record (9 of 72). (2) Following a Codex subagent to its parent thread, since the child's dispatch brief is stored as encrypted_content (6 of 72). (3) Searching the work homes and archived_sessions as well as the default stores. Every origin found was on one host; the other host held none.
  provenance: {"harness_session":"claude-code:737a5757-83af-4e31-9fdd-4ce70dd9e6f1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-20T16:05:27Z (main): scope: briefed; framed which tool owns report-origin lookup across stores (lean: an obs locate query over its index, which already covers all six roots, archive read_path, parent_session and missing state; rejected a new locate surface in hq, which would add a fifth store list); parented under goal hq-cff824; waits on research hq-a1c591; store-list alignment filed independently as hq-a60cf5; brief: docs/notes/2026-10-20-session-store-reach-brief.md
- 2026-10-20T16:34:45Z (main): scope addendum 2026-10-20: the user proposed an hq logs / hq trace CLI with a usage skill; survey hq-de3e4c now precedes the locate-owner decision, which folds into that CLI's design; hq-a1c591 (obs index coverage) remains an input
- 2026-10-20T17:30:21Z (docs/logs-survey): hq-de3e4c research input: docs/notes/2026-10-20-session-log-survey.md and the brief section 7 classify 183 episodes. Formats/behavior dominate; 64 need historical tool outputs, 32 parent links. Recommend search+show with metadata/raw streams, role filtering, paired results and coverage; trace composes typed evidence. No new find verb justified. Location ownership still depends on hq-a1c591; incorporate both results in the CLI design.
- 2026-10-20T17:45:51Z (docs/logs-survey): correction to hq-de3e4c preliminary parent count: raw re-audit confirms18 relationship episodes, including8 child-to-parent and12 parent-to-child (2 both). Only6 combine reverse binding with historical outputs. The corrected sample is183 episodes /1093 calls;64 need historical outputs. Use final report section Roles/evidence, not the earlier32 preliminary parent flags.
- 2026-10-20T18:09:23Z (main): Follow-up review: hq-6e5d88 now derives portable semantic acceptance cases from the completed survey; use them for search/show and evidence-link requirements. Avoid a duplicate CLI design task: this idea already owns that design after hq-a1c591. Reconcile it with the accepted boundary work ops-630a87 and obs-f5710b: obs is to own content parsing and session-logs, hq location/lifecycle and harness-version store samples. The transfer is deferred to 2027-02-17 after flow-trial-1 readout; parser ownership, the consumer interface and any effect on enrolled sessions or measurement are explicit design checks. The new corpus is data-only and does not execute that transfer. Automated trace precision still needs evaluation before a precision claim; a single surveyed batch is insufficient.
- 2026-10-20T19:31:48Z (docs/index-reach): hq-a1c591 research input: docs/notes/2026-10-20-session-index-reach.md and brief sections2/4–6. Existing obs index resolves20 sampled origin files and6 child-parent links to5 parents; content/output anchoring still requires a reader. Preserve per-file candidates and actual readability: O10 root-ID query returns root plus3 child files whose empty parent-ID rows all have subagent=0, while separate agent rows are correctly classified; gap obs-b99310. M01 missing file has a readable alternate under the same ID. Native archive/missing controls pass, but zero read_path rows means replayed-copy retrieval unobserved. Europa has no index at configured path. Recommend search+show using existing local metadata and accepted obs parsing ownership; no new index. Both research inputs are now available; fresh corrective review and final task closure precede branch integration.
- 2026-10-22T17:41:57Z (main): scope: scoped; both studies and the ten-case corpus are complete (686e160, 228f751, 03af2f4); obs-b99310 resolved the phantom-parent defect in 54ce9e187b825dc7ace6ff23ba9820e172b1f89c. Promoted this existing idea to the design-and-plan handoff, P2/m/high/planned, with required evidence refs, explicit parsing/location ownership and trial rollout gates; original captured body preserved. No new research or duplicate design task; brief: docs/notes/2026-10-20-session-store-reach-brief.md
- 2026-10-23T12:40:18Z (main): started
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T12:40:29Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-23T12:40:29Z (main): arm: flow-trial-1 — unit tack-c411df — flow on
- 2026-10-23T12:40:49Z (main): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T12:41:03Z (session-evidence-reader): resumed
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T13:05:46Z (session-evidence-reader): Draft spec committed ce66d61 (docs/specs/2026-10-23-session-evidence-reader-design.md): obs hosts a new read-only session-logs entry point (search/show, typed JSONL, coverage outcome found/not_found/unknown) over obs store_roots and a read-only index; Stage A adds files only before readout, skill and link after readout (D5); proposes moving this task to obs after approval so its plan steps live with the code (D6). Fresh-context agent review dispatched before the human review.
- 2026-10-23T13:35:18Z (session-evidence-reader): review: spec round 1 — verdict: revise; findings: critical 1, important 12, minor 14; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T14:13:12Z (session-evidence-reader): review: spec round 2 — verdict: revise; findings: important 5, minor 12; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T14:42:18Z (session-evidence-reader): review: spec round 3 — verdict: revise; findings: important 5, minor 10; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T14:45:11Z (session-evidence-reader): Spec revision 4 at 87b7fcb (sha256 c9f40e908bccac1cdf36a7d10772b91909c0b51f29b3dfb1e1f0841f406abc02) addresses agent review rounds 1-3 (round 3 findings fixed per the reviewer's suggested fixes; no agent re-review of revision 4). Handed to the user for the designed gate.
- 2026-10-23T14:45:12Z (session-evidence-reader): parked (waiting on user, review): User reviews docs/specs/2026-10-23-session-evidence-reader-design.md at hq 87b7fcb (worktree .worktrees/session-evidence-reader), chiefly D1 obs hosts the reader, D5 skill after readout, D6 no task move and a separate obs build task; then the agent records gate: designed and writes the plan
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:03:29Z (session-evidence-reader): resumed
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:03:30Z (session-evidence-reader): review: spec round 4 — verdict: revise; findings: important 4; reviewer: codex/gpt-6.1-sol
- 2026-10-23T15:05:48Z (session-evidence-reader): Spec revision 5 at ae0f8ee (sha256 93e10418abbce4db8a5e7e29e608ae91de4dd0ccfb59a371a348f408f6b074f9) addresses round 4's four findings: prefilter removed with the escape counterexample as a test, single-segment rule for unsuccessful task commands, missing-parent fork range wholly ambiguous with no finals, Codex completed requires task_complete. Not re-reviewed by an agent.
- 2026-10-23T15:05:48Z (session-evidence-reader): parked (waiting on user, review): User reviews docs/specs/2026-10-23-session-evidence-reader-design.md at hq ae0f8ee (worktree .worktrees/session-evidence-reader), round 4's four fixes first; then the agent records gate: designed and writes the plan
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:15:40Z (session-evidence-reader): resumed
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:15:40Z (session-evidence-reader): review: spec round 5 — verdict: accept; findings: minor 1; reviewer: human
- 2026-10-23T15:15:41Z (session-evidence-reader): Deferred to the plan (spec round 5 minor): casefold() applies to literal matching only; --regex uses Python re flags (IGNORECASE unless --case) and never folds the expression, since folding \S+ gives \s+.
- 2026-10-23T15:15:50Z (session-evidence-reader): gate: designed docs/specs/2026-10-23-session-evidence-reader-design.md — user approved revision 5 at ae0f8ee after five review rounds (round 5 accept, one minor deferred to the plan)
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:24:46Z (session-evidence-reader): Plan committed 525dff8 (docs/plans/2026-10-23-session-evidence-reader.md, sha256 09ef5dbdcb22534949f4d1037a9dee45a3b082caf3f945dbb269e5039a76df3b): hq Task 1 (SL11 fixtures, child) and obs steps 1-12 for one new obs task; deviation ruled in obs step 1 (obs's scratch and INGEST_STUB harness instead of the real tasks CLI of spec 14.5). Children and the obs task are filed after plan approval, then gate: planned.
- 2026-10-23T15:24:47Z (session-evidence-reader): parked (waiting on user, review): User reviews docs/plans/2026-10-23-session-evidence-reader.md at hq 525dff8 (worktree .worktrees/session-evidence-reader) and picks Task 1's execution method; then the agent files the Task 1 child and the obs build task, writes the Stage B and hq-b95324 notes, records gate: planned, and runs Task 1
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:35:37Z (session-evidence-reader): resumed
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T15:35:37Z (session-evidence-reader): review: plan round 1 — verdict: revise; findings: important 4, minor 1; reviewer: codex/gpt-6.1-sol
- 2026-10-23T15:36:50Z (session-evidence-reader): Plan revision 2 at 1fea7bf (sha256 3127dcfb9b83c603f3b0d9620809843ff9838d135a4a6ee449ea8100c0c0529d) addresses plan round 1: listing validator widened to turns/, harness TASKS_STUB answers every show form (INGEST_STUB kept for list/projects/resolve), private _flags/_prompt_id/_source_tool_use_id carried to the turn parser and never emitted, inherited_turn_ids returns every physical turn id with a nested-fork test, absent term in the missing-file test.
- 2026-10-23T15:36:51Z (session-evidence-reader): parked (waiting on user, review): User reviews docs/plans/2026-10-23-session-evidence-reader.md at hq 1fea7bf (worktree .worktrees/session-evidence-reader) and picks Task 1's execution method; then the agent files the Task 1 child and the obs build task, writes the Stage B notes, records gate: planned, and runs Task 1
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T16:11:27Z (session-evidence-reader): resumed
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
