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
updated: 2026-10-25T17:45:31Z
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
