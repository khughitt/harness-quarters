---
id: hq-d59a7b
title: "Survey live Claude stores and obs's index for successor links: count, form, age, and link-path rows"
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: survey-successor-links
created: 2026-10-23T00:09:52Z
updated: 2026-10-23T01:30:19Z
started: 2026-10-23T01:19:12Z
completed: 2026-10-23T01:30:19Z
closed: 2026-10-23T01:30:19Z
depends: []
parent: hq-401088
tags: []
agent: claude-code/claude-opus-5-5
---

Question: What successor links exist in the current Claude stores (count, form, age and resolution), and would current obs index-state rows trigger load_obs_state's realpath conflict?

Where to start: [ref:brief] covers relative and absolute links because the form Claude writes is unrecorded, and its gates rest on "pairs exist in history" without a current count. The obs-reader halt (hq-3b9c4c) depends on obs still emitting rows for link paths, which was taken from obs-396637's record, not checked.

Bound: Read-only. List symlinks under ~/.claude/projects and ~/.claude-work/projects (find -type l, readlink, no following beyond lstat/stat), with each link's form (relative/absolute), whether it resolves, and the mtimes of both units, so it is clear whether any pair is already past 30 days. Query obs index-state --json for rows whose path is currently a symlink or that load_obs_state's realpath would fold onto another row. No prune, no writes to either store.

Expected result: Record counts and a short table on hq-1639fd and hq-3b9c4c and in the brief; say whether the realpath conflict would fire against today's index. Separate unavailable stores or command failures from an observed zero count.

Ideas it wakes: On completion, run `tasks note hq-1639fd --no-reviewed "<survey finding and current index conflict verdict>"` before this result's branch merges. Also record the reader finding on hq-3b9c4c.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — findings, rules 1-3 and the open questions

## Notes

- 2026-10-23T01:19:12Z (main): started
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T01:19:22Z (main): arm: flow-trial-1 — unit tack-401088 — not enrolled
- 2026-10-23T01:20:38Z (survey-successor-links): resumed
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T01:30:19Z (survey-successor-links): done
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T01:30:19Z (survey-successor-links): Surveyed both Claude stores and obs index-state: 2 absolute, resolving successor links (beliefs pair 46 days old, past the 30-day horizon; hq pair fresh), none in claude-work; the realpath conflict fires against today's index. Brief updated (Live survey); findings noted on hq-1639fd and hq-3b9c4c.
  provenance: {"harness_session":"claude-code:38f3b682-ef1d-4f4a-a80b-80579e770420","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
