---
id: hq-d33cdc
title: Adopt shared broad-test policy and remote verification
status: doing
priority: 1
size: m
complexity: mid
process: planned
owner: feat/hq-d33cdc-test-policy
created: 2026-10-29T13:45:47Z
updated: 2026-11-03T10:27:41Z
started: 2026-11-03T10:19:41Z
depends: [ops-68729d]
tags: []
source: "tt-policy:hq"
agent: codex
origin: agent
spec: docs/specs/2026-11-03-test-execution-policy-design.md
---

Adopt the approved shared test execution policy for this personal project after the ops pilot. Owner: the next hq implementer; Keith approves external activation. State: pending preparation, not offloaded. Shared authority: ops-8bfa85 (read its approved spec and plan with tasks doc); pilot prerequisite ops-68729d.

Observed 2026-10-29: code checkout is its own Git top level; records kind in-tree; profile personal. Current policy file: absent (enabled). Wrapper: {}. Commands: setup, test. Read [ref:front-door] for actual commands and setup. Workflows: None found..

Current command/ref declarations:
```
No shared command variables; inspect the direct recipe bodies.
```

Prepare a reviewed project-specific design/plan and isolated worktree. Adopt the published wrapper only after ops and obs readers are live. Keep test-one/focused implementation checks and mandatory hygiene on; split broad lint/type/test work into explicit targets. Preserve current selectors and argument forwarding. Add the forced test-full route. Verify branch/ref coverage against workflow triggers and use explicit TT_FORCE=1 for the full remote suite, including nested recipes. One suite per push, latest-ref cancellation, no duplicate internal-PR run. Keep local policy enabled until an approved hosted invocation finishes with a nonzero test count and accepted coverage.

Inventory capability omissions and private sibling checkouts from actual workflow/setup; none are presumed equivalent to local verification.

Prepare the activation packet with current private-repository allowance and enforced no-paid-overage setting, setup, exact refs, executed tests, excluded modules and skipped-test/module counts. Publishing workflows, live global instruction/hook delivery and account changes require explicit approval. Existing work/external/shared Git roots are not independent opt-ins. Reuse host/profile proof only for identical setup paths. Detached records remain separate from code policy lookup.

After approved activation, commit .tt.toml with real broad target names, verify focused execution/recorded skip/forced failure/covered remote push, and retire each disabled timing obligation explicitly without claiming performance verification. Record the actual activation revision/time here. On hook-split integration and rollback write exactly: policy: enabled at <RFC3339-UTC> revision <full-sha>. This record's source tt-policy:hq is the latency floor lookup key. Keep remaining diagnosis and unrelated obligations. Report status to ops-39bff6; never label pending work as offloaded. The first actual activation files the 30-day regret review under ops; no scheduler and no invented date.

## References

- front-door (input, required, kind=configuration): justfile
- builder-review (context, kind=review): docs/notes/2026-11-03-hq-d33cdc-builder-report.md

## Notes

- 2026-10-29T13:45:47Z (add): created
  provenance: {"harness_session":"codex:01a1874f-c2d8-7320-ae81-7114e37e343f","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-01T23:43:21Z (main): related: hq-b01c0f wraps hq's just test xdist step in host-budget and adds a budgeted test-one route (ops-4adbbe); keep the recipe split here compatible with it.
- 2026-11-03T10:13:26Z (main): raised to P1 at the user's request (2026-11-03) so a following session picks it up; hq-414f8a skipped its full-suite baseline at the user's direction
- 2026-11-03T10:19:41Z (main): started
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T10:20:05Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-03T10:20:07Z (main): arm: flow-trial-1 — unit tack-d33cdc — flow on
- 2026-11-03T10:20:48Z (feat/hq-d33cdc-test-policy): resumed
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T10:21:04Z (feat/hq-d33cdc-test-policy): gate: scoped — adopted
  provenance: {"harness_session":"codex:01a1a0e6-b178-7e10-aacc-34aa3af75b7c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-03T10:21:07Z (feat/hq-d33cdc-test-policy): Workspace: .worktrees/hq-d33cdc on feat/hq-d33cdc-test-policy, locked and hydrated with just setup. User explicitly waived baseline tests for this task, including implementation Setup; no baseline run or pass is claimed. Flow trial assigned flow on. Design/spec preparation only until human review; no code or external activation yet.
- 2026-11-03T10:23:33Z (feat/hq-d33cdc-test-policy): Intent recovered with session-logs from codex:01a1874f-c2d8-7320-ae81-7114e37e343f: human ask at transcript line 15 preserves focused tests while reducing broad contention; line 108 asks for hosted suites, tt ownership, lore changes and latency disposition; lines 294 and 538 approve shared spec/plan with the hosted-refusal correction. This adoption task is agent-filed execution scope, not a new human request. Public hq and tasks/relay visibility observed via gh read-only; ops remains a private sibling dependency for two existing integration cases. Current main has no .tt.toml, tools/tt, CI workflow or pre-push hook. No test-latency or halt rows found. Design choices are the agent’s calls; human design review remains required.
- 2026-11-03T10:23:36Z (feat/hq-d33cdc-test-policy): Coordination: hq-b01c0f owns budgeted local test/test-one recipes; hq-0d26dc owns the explicit system-interpreter fix needed by pidfd paths. This design must preserve/reuse their resulting behavior and coordinate any shared justfile edits before implementation. Neither record is closed by this preparation. Ops tt is version 10 at landed 646c7cf7c08e11e8adcf43ddf844a3f059162735; obs skip reader delivery is recorded on done obs-a171dd and present in its current tree. Live tt-report and tt-latency resolve to ops main. Baseline waiver does not waive focused implementation tests or mandatory hygiene.
- 2026-11-03T10:26:37Z (feat/hq-d33cdc-test-policy): Frozen design 366e89c2f56cee6b9cd8918d62cb088960206bdc:docs/specs/2026-11-03-test-execution-policy-design.md dispatched for a fresh read-only builder check. Mandatory document checks passed: ops-check, ops-docs check and diff whitespace; tasks check has zero errors and four pre-existing undefined-tag warnings on unrelated records. No code or baseline tests ran. Design proposes shared tt, budget-preserving local routes, explicit hosted route, shared pre-push coverage handling, and acceptance of two named sibling-dependent skips subject to actual remote counts. Human spec review follows; no implementation plan written yet.
- 2026-11-03T10:27:37Z (feat/hq-d33cdc-test-policy): review: spec round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
