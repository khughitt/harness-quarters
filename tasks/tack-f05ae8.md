---
id: tack-f05ae8
title: "External-PR rule: --body discards the template; search existing PRs and issues first"
status: done
priority: "2"
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

Two clauses for the external-repo PR rule in AGENTS.md (landed in ai-b9dd14):

1. `gh pr create --body` replaces the repository's PR template, so the body must reproduce the template's sections; prefer `--body-file` from a filled copy of the template.
2. Before opening the PR, search the repository's open and closed PRs and issues for the same problem (`gh pr list --state all --search`, `gh issue list --state all --search`). If a duplicate or a prior closed attempt exists, stop and tell the user rather than opening another; otherwise reference what was found and link the issue the PR fixes.

## Notes

- 2026-09-14T14:26:29Z (gh-rules): External-PR rule extended: --body replaces the template (prefer --body-file); search open and closed PRs and issues first, stop on a duplicate, link the fixed issue.
