---
id: hq-a45dd8
title: Add a two-turn task-evidence fixture so the session-level task_evidence label is tested
status: idea
priority: 2
size: xs
created: 2026-10-23T17:40:19Z
updated: 2026-10-23T17:52:52Z
depends: []
parent: hq-cff824
tags: []
agent: claude-code
---

Why: SL11's CT1 and CT3 each hold one turn, so spec section 9.4's task_evidence: session label (a session's turns outside the evidence span) has no fixture, and obs step 9's assertion of it is vacuous (hq-c411df integration review, noted on obs-d98663). Approach: a second CT1 turn after the stamped note's span in tools/fixtures/session-logs/turns, a self-check, and a cases-document row. Re-vendor into obs after. Verification: the new self-check fails before the fixture exists.

## Notes

- 2026-10-23T17:52:52Z (main): fold in two deferred minors from hq-bb90ca's round-3 review while touching the same files: the ordinal loop in test_sl11_codex_statuses_by_closing_event passes vacuously if its glob matches nothing (bind the paths and assert there are three, or move it into its own test), and the turns/ paragraph near line 76 of docs/notes/session-log-acceptance-cases.md is wrapped short (reflow it).
