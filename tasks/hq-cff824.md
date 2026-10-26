---
id: hq-cff824
title: "Agents can find and read any session's evidence, wherever it is stored"
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-20T16:04:22Z
updated: 2026-10-26T09:47:17Z
depends: [obs-d98663, obs-f5710b, hq-19580c, obs-081ded]
tags: [session-logs]
source: docs/notes/2026-10-20-session-store-reach-brief.md
agent: claude-code
---

Why: Scope and audit agents need a supported way to find a session behind a report, follow its parent thread, recover its runtime model and read retained live or archived evidence. The original coverage gap still exists in the installed session-episodes reader and skill, but research and reader design are complete. This goal now coordinates delivery and verifies the result; it does not commission another reader design.

Established:
- hq-de3e4c, hq-a1c591 and hq-6e5d88 completed the question survey, location study and portable acceptance corpus. hq-c411df completed the reviewed design at ae0f8ee and plan at 1fea7bf; hq-bb90ca delivered SL11 fixtures. Both reviewed documents are unchanged in hq main at 3c73287.
- obs owns content parsing and the search/show reader. obs-d98663 owns Stage A under [ref:reader-spec] and [ref:reader-plan], including the corrections in its task notes. No session_logs implementation files were found in obs main at 9fda68a.
- The first release is local-first: six local roots, the read-only obs index, indexed replay copies and explicitly supplied files. Missing, unreadable, not-indexed or otherwise incomplete evidence must remain explicit; the title does not promise automatic remote access or archive materialization. The studies did not qualify those capabilities.
- hq main still has two default roots in agents/bin/session-episodes::_roots and no general final-message query or runtime-model recipe in the usage skill. hq-a60cf5 and hq-7b131a retain that work. Spec section 11.4 supersedes any reading that either is automatically safe to ship now: the model recipe changes treatment, while root alignment needs its own trial-gate assessment.
- obs-f5710b owns Stage B1/B2: usage skill, link/README handoff, one classifier and first-seen coverage stamp. hq-19580c and obs-081ded own Stage B3's home registry and consumer switch. Changes affecting enrolled sessions or measurement wait for the 2027-02-16 readout and must pass the gate on their date; a deferral date alone is not authorization.

Done:
- Existing hq children are completed or explicitly disposed of, including the two-turn task-evidence case in hq-a45dd8, fixture fidelity in hq-c1fecb and annotation corrections in hq-edf5de. hq-b95324 already has a pending drop proposal because obs-d98663 covers final-message retrieval; do not create a duplicate implementation.
- obs-d98663 has landed with its acceptance replay and live six-root verification, covering source references, call/result pairing, roles, turns/finals, parent/model evidence and honest coverage/unavailability outcomes. Include its fork-boundary decision and handoff corrections; no unqualified claim of retrieval from every host or pruned store.
- The recorded Stage B owners have delivered the skill/discovery integration under the trial gate. The parent depends on those existing tasks so hq-only completion cannot hide the remaining delivery elsewhere.
- At closeout, record the delivering commits and acceptance/rollout evidence on this task and reconcile the existing children against the delivered contracts. Rate this parent's remaining verification s/low/direct; implementation complexity stays on its existing tasks. Preserve priority 2.

Where to look: [ref:reader-spec] is the reviewed contract (especially sections 3, 11 and 14); [ref:reader-plan] is the frozen implementation handoff, read together with obs-d98663's later correction notes. [ref:brief] preserves the studies and original alternatives, but its statements that design remains open are historical and superseded by hq-c411df. Current code: agents/bin/session-episodes, agents/skills/session-logs/SKILL.md, tools/test_session_log_cases.py and tools/fixtures/session-logs/.

## Original captured scope

Scope and audit agents need to reach a session's evidence: the session behind a feedback report, its parent thread, the model that ran it, its archived or pruned copy. Today the session-logs reader covers two of the six stores obs indexes and names no route to a Codex child's runtime model. Brief: docs/notes/2026-10-20-session-store-reach-brief.md.

## References

- brief (context, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — historical studies and alternatives; design-open wording superseded by hq-c411df
- reader-spec (input, required, kind=spec): docs/specs/2026-10-23-session-evidence-reader-design.md — reviewed contract at ae0f8ee, delivery boundaries and trial gates
- reader-plan (input, required, kind=plan): docs/plans/2026-10-23-session-evidence-reader.md — reviewed plan at 1fea7bf; read with obs-d98663 correction notes

## Notes

- 2026-10-25T17:11:29Z (main): scope: rescoped; checked hq 3c73287 and obs 9fda68a, merged reviewed spec ae0f8ee and plan 1fea7bf (unchanged), completed hq-c411df/study notes, current two-root extractor and unchanged usage skill, and existing Stage A/B owners. Narrowed parent to delivery closeout, s/low/direct with P2 unchanged; recorded obs-d98663, obs-f5710b, hq-19580c and obs-081ded as dependencies, preserved original scope/source and all children, linked reviewed contract/plan, and marked the old brief historical. Local-first retrieval includes explicit unavailable/unknown evidence, not automatic remote/archive recovery; trial gates remain binding, including the model-skill treatment gate and root-alignment assessment. No duplicate research, new handoff, child edits or implementation. origin: filing event unavailable because this record has no creation occurrence note or harness_session stamp; no origin_session identifies an older request, so stage 2 is not applicable and origin remains unset (no transcript lookup failure claimed). Validation: tasks check clean before writes; just test passed 1668 tests (231 agents, 1047 hooks/tools, 389 parallel relay and 1 isolated relay).
  provenance: {"harness_session":"codex:01a17401-db00-7090-899a-ca387cde5be3","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T17:31:44Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-25T17:31:45Z (main): arm: flow-trial-1 — unit tack-cff824 — flow on
- 2026-10-25T18:24:41Z (main): delivery checkpoint: merged hq corrections 30717ad locally into main with merge a569687. hq-a45dd8, hq-c1fecb and hq-edf5de are done; hq-b95324 is dropped as covered by obs-d98663, not delivered. hq-7b131a and hq-a60cf5 are explicitly deferred to 2027-02-17 with required reader-spec gate references; the scoped root-alignment skill edit is treatment regardless of the unresolved episodes-measurement classification. No skill, runtime reader, links, roots or measurement implementation changed. Final branch just test passed 1672 tests (231 agents, 1051 hooks/tools, 389 parallel relay, 1 isolated relay), focused fixture suite passed 38, 35 targeted breaks were detected, and all 73 E008/E037 source refs matched hashes. Baseline was 1668 passed; two intermediate suites were intentionally aborted after review required corrections. Independent implementation review accepted after two corrective rounds, no deferred findings; stale brief deferral regraded Important with Why/Cost on hq-edf5de. Main had a concurrent unrelated brief and task-record update, preserved by merge; all 18 branch files match their tested blobs and merge ops-check/ops-docs/harness-facts/tasks checks passed. Exact CT1 turn refs, XG, prefix/identity changes and re-vendor/nonvacuous reader assertions were handed to obs-d98663 before merge. Its existing fork-boundary decision and live six-root acceptance remain required. At inspection obs main 1124c7d had no session_logs*.py; obs-d98663 and the three Stage B dependencies remain open. This goal is not complete: Stage B still waits for the 2027-02-16 readout and its date-specific gates. Session resources: worktree removed and released on each child, no scratch or off-tree evidence copies retained. No push or live-surface activation; concurrent harness picks and unrelated work preserved.
- 2026-10-25T18:24:42Z (main): parked (waiting on agent, dependency): Next agent resumes delivery verification in hq after obs-d98663, obs-f5710b, hq-19580c and obs-081ded deliver: record their commits, acceptance replay, fork-boundary ruling and live six-root coverage, then reconcile the deferred children and close this goal. Stage B must first pass the gate after the 2027-02-16 readout; existing obs-d98663 is the next implementation owner. The three immediate hq correction children are merged and no session worktree remains.
  provenance: {"harness_session":"codex:01a1741c-4199-7e10-a98e-cef25f7966ed","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T18:26:53Z (main): Concurrent-work correction: the brief added on main during this session is linked to new child hq-c8aef1 (idea), so it is related goal work, separate from the three correction children reviewed and implemented here. It and its brief were preserved without edits; this session did not scope, review or implement that new child. Parent closeout must also reconcile hq-c8aef1, alongside the deferred children and four delivery dependencies. The earlier checkpoint description of the concurrent brief as unrelated is superseded by this observation.
- 2026-10-25T18:26:55Z (main): parked (waiting on agent, dependency): Next agent resumes delivery verification in hq after obs-d98663, obs-f5710b, hq-19580c and obs-081ded deliver: record their commits, acceptance replay, fork-boundary ruling and live six-root coverage, then reconcile deferred children plus concurrent idea hq-c8aef1 and close the goal only when all are settled. Stage B first needs the gate after the 2027-02-16 readout; existing obs-d98663 owns the next implementation. Three immediate hq corrections are merged; no session worktree or process remains.
  provenance: {"harness_session":"codex:01a1741c-4199-7e10-a98e-cef25f7966ed","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-26T09:47:17Z (main): obs-d98663 delivered Stage A: merged into obs main at 062b73e (2026-10-26). Acceptance replay SL1-SL10B passes by ref (tests/test_session_logs_cases.py) and SL11 through the turn and task tests; obs gate 1614 tests OK on the merged tree. Fork-boundary ruling: spec §8.3 as reviewed (native subagent_history_start_ordinal not honoured); live it agreed on 269/269 forks carrying it, so hq-28baf9 takes the amendment. Live six-root run: 25,563 files, 33.0 GiB, 0 exceptions; coverage starts claude roots 2026-09-18, codex roots 2026-10-20; all four §14.4 live cases pass. Remaining before this goal closes: hq-28baf9, then Stage B (obs-f5710b, obs-081ded, hq-19580c) after the 2027-02-16 readout.
