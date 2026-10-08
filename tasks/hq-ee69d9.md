---
id: hq-ee69d9
title: Reject restrictive claim-guard matchers in both Codex wiring regressions
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-08T23:10:34Z
updated: 2026-10-08T23:10:35Z
depends: []
tags: []
source: "tasks-56b450:deferred-minor:matcher"
agent: codex/gpt-6.1-sol
---

Why: the accepted wiring/full reviews deferred a minor: tools/test_claim_guard_wiring.py counts guard commands but still passes if a future matcher restricts delivery. Current personal/work registrations correctly have no matcher and their native source smokes passed.

Bound: strengthen the existing regression for both codex/hooks.json and codex/hooks.work.json. Identify the unique guard group for Stop and SubagentStop and assert the approved unrestricted registration contract; show an intentionally restrictive matcher fails the check. Preserve existing unrelated-hook and links.toml route checks. No live hook or trust change.

Where to start: tools/test_claim_guard_wiring.py test_both_codex_homes_guard_root_and_worker. Evidence: tasks-56b450 and tasks docs/notes/2026-10-08-claim-guard-acceptance.md, Fresh final review.

Done: both real source files pass; a controlled restrictive matcher mutation fails the regression; the hq front-door suite passes.

## Notes

- 2026-10-08T23:10:34Z (main): concerns: tasks-56b450 extension — protect the verified unrestricted worker registration against future matcher regressions.
