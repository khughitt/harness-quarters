---
id: hq-d59a7b
title: "Survey live Claude stores and obs's index for successor links: count, form, age, and link-path rows"
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-23T00:09:52Z
updated: 2026-10-23T00:09:52Z
depends: []
parent: hq-401088
tags: []
agent: claude-code/claude-opus-5-5
---

Why: [ref:brief] covers relative and absolute links because the form Claude writes is unrecorded, and its gates rest on 'pairs exist in history' without a current count. The obs-reader halt (hq-3b9c4c) depends on obs still emitting rows for link paths, which was taken from obs-396637's record, not checked.

Bound: read-only. List symlinks under ~/.claude/projects and ~/.claude-work/projects (find -type l, readlink, no following beyond lstat/stat), with each link's form (relative/absolute), whether it resolves, and the mtimes of both units, so it is clear whether any pair is already past 30 days. Query obs index-state --json for rows whose path is currently a symlink or that load_obs_state's realpath would fold onto another row. No prune, no writes to either store.

Done: counts and a short table noted on hq-1639fd and hq-3b9c4c; say whether the realpath conflict would fire against today's index.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — findings, rules 1-3 and the open questions
