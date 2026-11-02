---
id: hq-87db7d
title: "Add the mid-merge recovery caveat to AGENTS.md, the harness manifest spec and justfile"
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-11-01T19:26:17Z
updated: 2026-11-01T19:26:17Z
depends: []
tags: [docs]
origin: agent
---

Deferred from hq-2eba07's reviews. README and the adding-a-harness runbook say that during a merge or rebase 'git checkout -- harnesses.toml' fails on an unmerged path (resolve the conflict or abort instead, never unset filter.harness-state.required); AGENTS.md Rules and the spec's 5.5.1 recovery line still give only the checkout command. justfile line 1 still says 'after pulling a change to it' (AGENTS.md now says 'to the recipe'). README's broken-manifest paragraph could also note the racy-clean case: while harnesses.toml is broken, an unrelated git add within about a second of an index write can fail because git re-filters racily clean configs.

## Notes

- 2026-11-01T19:26:17Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
