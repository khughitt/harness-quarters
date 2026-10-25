---
id: hq-cff824
title: "Agents can find and read any session's evidence, wherever it is stored"
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-20T16:04:22Z
updated: 2026-10-25T17:11:29Z
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
