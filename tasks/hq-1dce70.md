---
id: hq-1dce70
title: Tighten weak and brittle assertions left in the harness manifest tests
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-11-01T19:26:19Z
updated: 2026-11-01T19:26:19Z
depends: []
tags: [tests]
origin: agent
---

Deferred from hq-2eba07's reviews. (1) The clean-only refresh test asserts no local/live-picks file has 'extra' in its name; assert the set of local/live-picks* names is unchanged instead. (2) The harness-state-clean runpy test builds its scratch manifest by splitting harnesses.toml on a literal header string; build it from parsed data. (3) Pre-commit-level tests cover filter.harness-state.required unset but not 'false' (unit and CLI tests cover false). (4) test_refresh_refuses_when_filter_required_is_unset_or_false now also covers smudge cases; rename it. (5) The live-picks CLI broken-manifest test does not prove the checkout lock was never taken. (6) just test's agents/bin run prints 'WARNING in core: flasgger is not installed'; find its source and silence or satisfy it so gate output is clean.

## Notes

- 2026-11-01T19:26:19Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
