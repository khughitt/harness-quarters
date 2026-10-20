---
id: hq-7efef3
title: Refresh Claude guard evidence for 2.1.304 before operator cutover
status: doing
priority: 1
size: m
complexity: mid
process: direct
owner: feat/relay-cutover
created: 2026-10-20T01:37:42Z
updated: 2026-10-20T01:41:11Z
started: 2026-10-20T01:40:58Z
depends: []
parent: hq-539508
tags: []
source: hq-33116d
agent: codex
---

The operator updated Europa Claude from 2.1.280 to 2.1.304 as runbook section 0 directs. Existing shared Claude evidence is valid for 2.1.302, so the version gate correctly refuses. Titan currently remains 2.1.302; operator update to the newly probed version is pending.

Repeat the reviewed Task 3 procedure for Claude only at 2.1.304 using the actual Europa installation, isolated disposable harness homes and relay v0.1.1 commit 4ceec5d2ad22b136b37ee360e7a4ed00949f28d9. Use locked, hydrated ops and detached relay worktrees; preserve unrelated main changes. Run the replay pilot then real allow/context/deny probe; retain native records and timing; keep optional/nested surfaces explicitly unproven.

Update only the Claude evidence and current-evidence paragraph in ops, verify real disposable installer plan acceptance, test and obtain review before local integration. Codex evidence is unchanged. Refresh the hq runbook's evidenced Claude version and recorded observations so operator commands use the accepted version. Check both hosts' exact versions before claiming readiness. No live hook application, timer/service/desktop changes, host-pointer repoints, or harness updates by the agent. No private settings, full inherited environments or credentials in outputs.

Done: new Claude evidence proves the required routes at the exact installed version and pinned relay; candidate evidence is accepted by the real installer without mutating copied targets; relevant gates and review pass, evidence/docs integrated as authorized, both hosts pass the evidence gate (no-live may still refuse), operator handoff remains intact.

## Notes

- 2026-10-20T01:38:43Z (feat/relay-cutover): concerns: hq-33116d change — Europa's operator update installed Claude 2.1.304; evidence for the formerly installed 2.1.302 must be refreshed before cutover.
- 2026-10-20T01:40:58Z (feat/relay-cutover): started
  provenance: {"harness_session":"codex:01a156f7-6259-7d63-93ed-4c23e04ca74c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-20T01:41:11Z (feat/relay-cutover): arm: flow-trial-1 — unit tack-539508 — flow off
