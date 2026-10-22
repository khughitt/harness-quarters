---
id: hq-b13db3
title: Validate parked walkthrough guidance in two private harness runs
status: todo
priority: 2
size: m
complexity: high
process: planned
created: 2026-10-22T20:35:06Z
updated: 2026-10-22T20:35:06Z
depends: [ops-e4d678, tasks-d8823c, lore-a071ae, flows-47f205]
tags: []
source: ops-e4d678
agent: codex
---

Accepted design: [ref:design], frozen ops e21ea75 (sha256 df835af8428626da6284972352edeffa749429e1c209fc183e62a3801f30c70a), accepted in spec round 10. Reuse that design; prepare the bounded implementation plan for review before execution. Design acceptance does not authorize live instruction, hook or harness activation.

Prepare the accepted manual validation: one supervised five-item walkthrough per Claude Code and Codex, using reviewed Tasks/Lore/Flows candidate guidance. Check native-interface/event applicability first with evidence-backed not-applicable dispositions for optional interfaces only. Core root Stop evidence cannot be waived; unchanged worker episodes stay out. No scripted matrix, prior-guidance arm, automatic repetitions or new metering service.

Freeze fixture/items/answers and revisions. Exercise evidence notes while parked, item-two fix with rounds n/revise and n+1 against a newly frozen revision, one controlled restart, and final-answer acquisition/work in the same turn without a nudge. Hq's recording session, separate from the walkthrough agent, judges the complete task record, claim snapshots, trace and captured native Stop inputs/outputs; request Tasks policy review of the result. One completed passing run per route, every applicable core criterion met, gates activation. Preserve failures and arrange any rerun separately.

Private setup: share scratch HOME, XDG_CONFIG_HOME and XDG_STATE_HOME among harness, hooks and restart, with one disposable tasks registry in persistent per-run storage. Clear inherited GIT_* variables; isolate GIT_CONFIG_GLOBAL and set GIT_CONFIG_NOSYSTEM=1; verify fixture git top level and git directory before writes. Never repoint live launchers, config includes or symlinks. Put the recorded fixture trial-arm stub at scratch ~/.agents/bin/trial-arm: print "not enrolled", exit 0, read no live trials and invoke no tasks. Use it after every start, restart included.

Round-10 Minor 1 (carried here by accepted review): link the real installed harness-facts reader into scratch ~/.agents/bin/harness-facts next to the stub, so a wrongly held claim exercises the usual facts path instead of a missing-reader error. Resolve and record the actual reader target/revision and private link; verify it is readable in the private environment without altering the live link.

Round-10 Minor 2 (carried here by accepted review): log in to each private harness with the user present. Keep any credential files created under scratch HOME out of saved evidence and task attachments. Retain only what restart needs during the run, then delete those credential files when the run ends, including failed or aborted runs; record cleanup without logging secret contents. Login behavior remains unprobed and must be checked during setup.

Use 15-minute/30-request reporting checkpoints under the supervising user's control, not automatic failure caps; choose a tracked timeout with headroom before launch and obey any hard user limit. Disclose selected model/billing mode, actual usage and dollar cost when exposed, otherwise unavailable. Existing authorized interactive access only; extra paid use requires concrete approval. Two walkthroughs, at most two controlled restarts/four session launches. No launch authorized by filing this task.

Done: retained sanitized evidence and independent per-route verdicts, credential cleanup recorded, session/turn manifests handed to Obs. After private passes, obtain separate approval before live guidance activation and verify each delivered harness route; record the approved activation and delivered check before closing this task and releasing the source feedback. Obs reconciliation gates cost publication only, never activation.

## References

- design (input, required, kind=spec): ops:docs/specs/2026-10-22-interactive-walkthrough-design.md — accepted frozen ops e21ea75
