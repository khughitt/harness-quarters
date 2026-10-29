---
id: hq-d33cdc
title: Adopt shared broad-test policy and remote verification
status: todo
priority: 2
size: m
complexity: mid
process: planned
created: 2026-10-29T13:45:47Z
updated: 2026-10-29T13:45:47Z
depends: [ops-68729d]
tags: []
source: "tt-policy:hq"
agent: codex
origin: agent
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

## Notes

- 2026-10-29T13:45:47Z (add): created
  provenance: {"harness_session":"codex:01a1874f-c2d8-7320-ae81-7114e37e343f","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
