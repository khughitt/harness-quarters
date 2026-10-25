---
id: hq-c1fecb
title: Tighten session-log acceptance fixture fidelity
status: doing
priority: 3
size: s
complexity: low
process: direct
owner: test/hq-a45dd8-two-turn-evidence
created: 2026-10-20T19:10:17Z
updated: 2026-10-25T17:53:57Z
started: 2026-10-25T17:45:09Z
depends: []
parent: hq-cff824
tags: [session-logs]
agent: claude-code/claude-opus-5-5
---

Why: hq-6e5d88's review rounds deferred minor fidelity gaps between the fixtures and live store bytes. A reader built to the fixtures could still mis-handle real records.

Do: in [ref:cases]' fixtures, write Codex spawn_agent arguments and outputs as compact JSON. Give failing Bash results the live harness prefixes (Exit code N, PreToolUse:Bash hook error:), and keep the SL6 expectation valid with an unanchored duration match. Add Claude's separate session_id field where live records diverge from sessionId, once its meaning is checked. Add a depth-2 Codex child, whose session_id names the root rather than the controller, and a forked child with an inherited second session_meta and copied history. Update the document's references and the self-check.

Check: the self-check and just test pass, each new assertion fails under a targeted fixture break, and no fixture holds private text.

## References

- cases (input, required, kind=report): docs/notes/session-log-acceptance-cases.md — cases whose fixtures this refines

## Notes

- 2026-10-25T17:45:09Z (test/hq-a45dd8-two-turn-evidence): started
  provenance: {"harness_session":"codex:01a1741c-4199-7e10-a98e-cef25f7966ed","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T17:45:25Z (test/hq-a45dd8-two-turn-evidence): arm: flow-trial-1 — unit tack-cff824 — flow on
- 2026-10-25T17:45:30Z (test/hq-a45dd8-two-turn-evidence): gate: scoped — adopted
  provenance: {"harness_session":"codex:01a1741c-4199-7e10-a98e-cef25f7966ed","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T17:45:31Z (test/hq-a45dd8-two-turn-evidence): gate: implementing — .worktrees/hq-a45dd8 shared acceptance and research corrections for hq-cff824
  provenance: {"harness_session":"codex:01a1741c-4199-7e10-a98e-cef25f7966ed","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T17:50:41Z (test/hq-a45dd8-two-turn-evidence): scope: reuse the existing XK fork fixture (SL11) for the inherited second session_meta and copied-history distinction; add only the missing depth-2 XG control. Live checks: depth-2 native metadata at codex:archived_sessions/rollout-2026-09-17T08-58-41-01a0af72-a423-7260-ad53-53a548b0330b.jsonl#L1 names root 01a0af3b-105a-7002-9860-567f02bf1862 in session_id and controller 01a0af6a-2653-70a0-ad30-8ebb8571b4bd in thread_spawn.parent_thread_id. Fork 01a16802-9f56-7e63-b5a6-49d3bad551e3 has own metadata at L1 and inherited parent metadata at L2. Claude source e5097cef-41ee-472d-b7bc-b8f42fbc01de has 663 records with session_id cd92ab9a-72bc-456d-a09a-a2805bbd58c2 while native sessionId is e5097cef-41ee-472d-b7bc-b8f42fbc01de; that other transcript has no shared uuids. The secondary field does not identify this native transcript; its allocation mechanism remains unqualified. Preserve this negative without guessing a resume or parent relationship. Workspace shares the completed 1668-test baseline for hq-a45dd8.
- 2026-10-25T17:53:57Z (test/hq-a45dd8-two-turn-evidence): verification before full suite: four new self-checks failed on the missing secondary Claude field, noncompact spawn JSON, missing Bash prefixes and absent depth-2 fixture; all 38 fixture checks now pass. SL6 failed with 4 instead of 5 matching outputs after adding the exit prefix, then passed after its duration search became unanchored. The combined mutation pass detected 25 targeted fixture breaks, including both compact JSON fields, both native error prefixes, missing spawn, wrong depth-2 identity/root/controller/depth/path/model and the two-turn evidence boundaries. No reader or live-store files changed.
