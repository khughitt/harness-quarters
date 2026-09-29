---
id: tack-bb99d4
title: "gh account per checkout: <work-account> only under ~/d/<work>/, khughitt everywhere else"
status: done
priority: "1"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-14T14:25:49Z
updated: 2026-09-14T14:26:29Z
started: 2026-09-14T14:26:00Z
completed: 2026-09-14T14:26:29Z
depends: []
tags: [rules]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

gh is authenticated with two accounts: personal khughitt and work <work-account>. Add a Git rule: <work-account> is used only for repositories under ~/d/<work>/; every other repository uses khughitt. Before any gh write (pr create, issue create, repo fork, comment, review), check `gh auth status` and `gh auth switch --user <account>` when the active account is wrong. At filing time the active account is <work-account>, so the default is currently wrong for personal work. The hook-side check is in the ops task for claude-pretooluse.

## Notes

- 2026-09-14T14:26:29Z (gh-rules): Git rule: <work-account> only under ~/d/<work>/, khughitt elsewhere; check gh auth status and switch before any gh write.
