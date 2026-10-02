---
id: tack-c437b4
title: "Subagent-driven workers force-staged ignored reports, and per-task reviews accepted these scratch artifacts as repository changes."
status: idea
priority: 2
created: 2026-09-30T13:34:48Z
updated: 2026-10-02T14:53:46Z
depends: []
tags: [feedback, gap, "from:sci"]
agent: codex
---

Subagent-driven workers force-staged their ignored report files (the SDD workspace under `.superpowers/sdd/` is self-ignored by `sdd-workspace`), and per-task reviews accepted those scratch artifacts as repository changes.

Proposed fix (upstream, obra/superpowers): the implementer report contract (`skills/subagent-driven-development/implementer-prompt.md`, "write your report to your report file") should forbid staging or committing the report, and the task reviewer should check every changed path against the brief's file list. tack cannot change vendored skills locally (`docs/notes/2026-09-29-cross-harness-review-brief.md` §3). No matching upstream issue found on 2026-10-02.

## Open questions

- File this upstream as an obra/superpowers issue (draft shown first, posted from `khughitt`)? If not, shelve until a second report.

## Notes

- 2026-10-02T14:53:45Z (main): scope: question; body rewritten with cause, upstream-only fix location, and one question: file it upstream as an issue (draft first)
