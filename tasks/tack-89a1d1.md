---
id: tack-89a1d1
title: "Turn-boundary gate spec: the guard allows a stop while the harness lists a running child, and the reason is a few lines"
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: docs/gate-spec-children
created: 2026-09-28T10:40:59Z
updated: 2026-09-29T12:57:09Z
started: 2026-09-29T12:48:31Z
completed: 2026-09-29T12:57:09Z
depends: []
tags: []
source: ops-0633a8
model: claude-fable-5-1
agent: claude-code/claude-opus-5-5
---

ops-ed76fe (2026-09-29) changed claim-guard, superseding the ops-0633a8 text fix this task first covered. On a harness whose CHILD_WAKES is true the guard allows a stop when the Stop input's background_tasks lists a running or pending item, without the claims read; a missing or malformed list blocks and says the guard could not look. The reason is a few lines and points at the instructions; the Claude Code reason has no subagent paragraph. Evidence: ops-552425 (388 of 1,144 turn ends blocked over five days, 355 on a correct running-child report) and the 2026-09-29 probe of the Stop input on Claude Code 2.1.284.

Update docs/specs/2026-09-24-turn-boundary-gate-design.md: section 2 (the probe's finding), 3.2 (the decide order), 3.3 (the reason text and the child sentence), 4 (why transcript parsing stays rejected, and the accepted limit of a background command that never exits), 5 (the unit cases), 6 (what the five-day count showed).

## Notes

- 2026-09-29T12:48:31Z (docs/gate-spec-children): started
  provenance: {"harness_session":"claude-code:6746c17e-0983-404a-ace6-bc9e1b1462ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T12:57:09Z (docs/gate-spec-children): done
  provenance: {"harness_session":"claude-code:6746c17e-0983-404a-ace6-bc9e1b1462ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T12:57:09Z (docs/gate-spec-children): spec sections 2, 3.2, 3.3, 4, 5 and 6 follow ops-ed76fe: the Stop input's running children, the new decide step, the three child sentences, the rejected alternatives, the unit cases and the five-day count
  provenance: {"harness_session":"claude-code:6746c17e-0983-404a-ace6-bc9e1b1462ac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
